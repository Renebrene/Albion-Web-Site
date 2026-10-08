from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from backend.services.data_service import (
    load_env_file,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_DIR = PROJECT_DIR / "input"
PREVIOUS_DIR = INPUT_DIR / ".previous"
ARCHIVE_UPLOADS_DIR = (
    PROJECT_DIR
    / "archive"
    / "constructions"
    / "_previous"
)

TMP_DIR = PROJECT_DIR / "tmp"
STATUS_FILE = TMP_DIR / "update_status.json"
LOG_FILE = TMP_DIR / "update_log.txt"
LOGS_DIR = TMP_DIR / "update_logs"

STEP_MARKERS = {
    1: "Excel → JSON",
    2: "SQLite staging",
    3: "Медиа (download)",
    4: "Превью (large/card/thumb)",
    5: "PostgreSQL (новый импорт)",
    6: "Архивация",
    7: "Очистка",
}

_LOCK = threading.Lock()
_PROCESS: Optional[subprocess.Popen] = None


# ---------------------------------------------------------------- утилиты


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _empty_status() -> dict:
    return {
        "state": "idle",
        "dry_run": False,
        "started_at": None,
        "finished_at": None,
        "exit_code": None,
        "commit_key": None,
        "input_file": None,
        "current_step": 0,
        "steps": [
            {
                "num": num,
                "name": name,
                "state": "pending",
            }
            for num, name in STEP_MARKERS.items()
        ],
        "media": {
            "tasks": None,
            "reuse": None,
            "download": None,
            "downloaded": None,
            "errors": None,
        },
        "preview": {
            "ok": None,
            "errors": None,
        },
        "log_tail": [],
        "errors": [],
    }


def _read_status() -> dict:
    if not STATUS_FILE.exists():
        return _empty_status()

    try:
        payload = json.loads(
            STATUS_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return _empty_status()

    for key, value in _empty_status().items():
        payload.setdefault(key, value)

    return payload


def _write_status(status: dict) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    STATUS_FILE.write_text(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------- upload


def save_uploaded_file(
    filename: str,
    content: bytes,
) -> dict:
    """Сохраняет Excel в input/ — в папке всегда ровно один файл.

    Предыдущий файл перемещается в input/.previous/ и попадает
    в archive/constructions/_previous/ только после успешного
    обновления базы (см. archive_previous_after_success).
    """
    suffix = Path(filename or "").suffix.lower()

    if suffix not in {".xlsx", ".xls"}:
        raise ValueError(
            "Поддерживаются только файлы .xlsx / .xls"
        )

    if len(content) == 0:
        raise ValueError("Файл пустой")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIOUS_DIR.mkdir(parents=True, exist_ok=True)

    moved_previous = None

    # Переносим текущий файл (если есть) в .previous
    for item in INPUT_DIR.iterdir():
        if (
            item.is_file()
            and item.suffix.lower() in {".xlsx", ".xls"}
        ):
            stamp = _dt.datetime.now().strftime(
                "%Y%m%d-%H%M%S"
            )
            destination = (
                PREVIOUS_DIR
                / f"{stamp}_{item.name}"
            )

            shutil.move(str(item), str(destination))
            moved_previous = destination.name

    destination = INPUT_DIR / Path(filename).name

    destination.write_bytes(content)

    return {
        "success": True,
        "filename": destination.name,
        "size": len(content),
        "saved": str(
            destination.relative_to(PROJECT_DIR)
        ),
        "moved_previous": moved_previous,
    }


def archive_previous_after_success() -> list[str]:
    """После успешного коммита .previous-файлы уходят в архив."""
    if not PREVIOUS_DIR.exists():
        return []

    ARCHIVE_UPLOADS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    archived = []

    for item in sorted(PREVIOUS_DIR.iterdir()):
        if not item.is_file():
            continue

        destination = ARCHIVE_UPLOADS_DIR / item.name

        if destination.exists():
            item.unlink()
        else:
            shutil.move(str(item), str(destination))

        archived.append(item.name)

    return archived


# ---------------------------------------------------------------- сбор ошибок


def collect_staging_errors(import_key: str) -> list[str]:
    """Ошибки/предупреждения из SQLite staging + пропущенные поля."""
    staging_db = (
        TMP_DIR
        / "import"
        / import_key
        / "staging.sqlite"
    )

    if not staging_db.exists():
        return []

    lines: list[str] = []
    conn = sqlite3.connect(staging_db)

    try:
        # Лог импорта (warning/error) — уже пишутся staging.py
        rows = conn.execute(
            """
            SELECT level, code, message, source_row
            FROM import_log
            WHERE level IN ('warning', 'error')
            ORDER BY id
            """
        ).fetchall()

        for level, code, message, row_number in rows:
            lines.append(
                f"[{level}] {code}: {message}"
                + (
                    f" (строка {row_number})"
                    if row_number
                    else ""
                )
            )

        # Нет фото и карты одновременно
        rows = conn.execute(
            """
            SELECT c.address, s.side
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            WHERE (
                    s.photo_url IS NULL
                 OR TRIM(s.photo_url) = ''
                 OR s.map_url IS NULL
                 OR TRIM(s.map_url) = ''
                )
              AND (
                    (s.photo_url IS NULL OR TRIM(s.photo_url) = '')
                AND (s.map_url IS NULL OR TRIM(s.map_url) = '')
              )
            ORDER BY c.address, s.side
            """
        ).fetchall()

        for address, side in rows:
            lines.append(
                f"[нет фото] {address}"
                + (f" сторона={side}" if side else "")
            )

        # Нет координат
        rows = conn.execute(
            """
            SELECT c.address, s.side
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            WHERE s.latitude IS NULL
               OR s.longitude IS NULL
            ORDER BY c.address, s.side
            """
        ).fetchall()

        for address, side in rows:
            lines.append(
                f"[нет координат] {address}"
                + (f" сторона={side}" if side else "")
            )

        # Нет цены (поверхность и/или ни один месяц)
        rows = conn.execute(
            """
            SELECT c.address, s.side
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            WHERE s.price IS NULL OR TRIM(s.price) = ''
            ORDER BY c.address, s.side
            """
        ).fetchall()

        for address, side in rows:
            lines.append(
                f"[нет цены] {address}"
                + (f" сторона={side}" if side else "")
            )

        # Ошибки скачивания медиа
        plan_file = (
            TMP_DIR / "import" / import_key / "media_plan.json"
        )

        if plan_file.exists():
            try:
                plan = json.loads(
                    plan_file.read_text(encoding="utf-8")
                )

                for entry in plan.get("entries", []):
                    if entry.get("status") != "error":
                        continue

                    lines.append(
                        f"[media] {entry.get('address')} "
                        f"сторона={entry.get('side')} "
                        f"{entry.get('media_type')}: "
                        f"{entry.get('url')} — "
                        f"{entry.get('error')}"
                    )
            except (json.JSONDecodeError, OSError):
                pass
    finally:
        conn.close()

    return lines


# ---------------------------------------------------------------- запуск


def _is_running() -> bool:
    return _PROCESS is not None and _PROCESS.poll() is None


def start_update(
    *,
    dry_run: bool = False,
) -> dict:
    """Запускает полный конвейер обновления базы в подпроцессе."""
    global _PROCESS

    with _LOCK:
        if _is_running():
            raise RuntimeError(
                "Обновление уже выполняется"
            )

        # В input/ должен быть ровно один Excel
        sources = [
            item
            for item in INPUT_DIR.iterdir()
            if item.is_file()
            and item.suffix.lower() in {".xlsx", ".xls"}
        ]

        if len(sources) != 1:
            raise RuntimeError(
                "В папке input/ должен быть ровно один Excel: "
                f"найдено {len(sources)}"
            )

        status = _empty_status()
        status["state"] = "running"
        status["dry_run"] = dry_run
        status["started_at"] = _now()
        status["input_file"] = sources[0].name

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("", encoding="utf-8")
        _write_status(status)

        command = [
            sys.executable,
            "-m",
            "backend.importer.import_pipeline",
        ]

        if not dry_run:
            command.append("--commit")

        env = os.environ.copy()

        # Без буферизации stdout подпроцесса — иначе прогресс
        # приходит только по завершении (блочная буферизация файла).
        env["PYTHONUNBUFFERED"] = "1"

        for line in (
            (PROJECT_DIR / ".env")
            .read_text(encoding="utf-8")
            .splitlines()
            if (PROJECT_DIR / ".env").exists()
            else []
        ):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")

            env.setdefault(key, value)

        log_handle = LOG_FILE.open("a", encoding="utf-8")

        _PROCESS = subprocess.Popen(
            command,
            cwd=PROJECT_DIR,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )

        threading.Thread(
            target=_monitor,
            args=(_PROCESS, dry_run, log_handle),
            daemon=True,
        ).start()

    return {
        "success": True,
        "state": "running",
        "dry_run": dry_run,
        "status_file": str(
            STATUS_FILE.relative_to(PROJECT_DIR)
        ),
        "log_file": str(
            LOG_FILE.relative_to(PROJECT_DIR)
        ),
    }


# ---------------------------------------------------------------- мониторинг


def _parse_step(line: str) -> int | None:
    for num, name in STEP_MARKERS.items():
        if f"STEP {num}:" in line or (
            f"===== STEP {num}" in line
        ):
            return num

    return None


def _apply_line(
    status: dict,
    line: str,
) -> tuple[str | None, bool]:
    """Парсинг одной строки лога. Возвращает (commit_key?, touched)."""
    commit_key: Optional[str] = None
    touched = False

    step = _parse_step(line)

    if step:
        status["current_step"] = step

        for step_item in status["steps"]:
            num = step_item["num"]

            if num < step:
                step_item["state"] = "done"
            elif num == step:
                step_item["state"] = "current"

        touched = True

    if "Import key:" in line:
        commit_key = line.split(":", 1)[1].strip()

    if "Решения REUSE:" in line:
        parts = line.split(":")

        if len(parts) > 1:
            status["media"]["reuse"] = parts[-1].strip()
            touched = True

    if "Решения DOWNLOAD:" in line:
        parts = line.split(":")

        if len(parts) > 1:
            status["media"]["download"] = parts[-1].strip()
            touched = True

    if line.startswith("Downloaded:"):
        status["media"]["downloaded"] = (
            line.split(":", 1)[1].strip()
        )
        touched = True

    if line.startswith("Errors:"):
        status["media"]["errors"] = (
            line.split(":", 1)[1].strip()
        )
        touched = True

    if line.startswith("OK:"):
        status["preview"]["ok"] = (
            line.split(":", 1)[1].strip()
        )
        touched = True

    if line.startswith("ERROR:"):
        status["preview"]["errors"] = (
            line.split(":", 1)[1].strip()
        )
        touched = True

    return commit_key, touched


def _monitor(
    process: subprocess.Popen,
    dry_run: bool,
    log_handle,
) -> None:
    import time

    status = _read_status()
    commit_key: Optional[str] = None
    collected = False
    seen_lines = 0

    while process.poll() is None:
        time.sleep(0.5)

        if not LOG_FILE.exists():
            continue

        try:
            lines = LOG_FILE.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            continue

        # Обрабатываем только новые строки, но не теряем
        # прогресс, если лог пишется порциями.
        new_lines = lines[seen_lines:]

        if not new_lines:
            continue

        seen_lines = len(lines)

        touched = False

        for line in new_lines:
            key, line_touched = _apply_line(status, line)

            if key:
                commit_key = key

            if not touched and line_touched:
                touched = True

            # Стадия 5 начинается — staging + media_plan ещё на месте.
            # Дальше cleanup удалит артефакты, собираем ошибки здесь.
            if (
                commit_key
                and not collected
                and _parse_step(line) is not None
                and status["current_step"] >= 5
            ):
                errors = collect_staging_errors(commit_key)

                if errors:
                    status["errors"] = errors

                collected = True
                touched = True

        status["log_tail"] = lines[-60:]
        _write_status(status)

    _finish(status, process, dry_run, commit_key, collected, seen_lines)


def _finish(
    status: dict,
    process: subprocess.Popen,
    dry_run: bool,
    commit_key: Optional[str],
    collected: bool,
    seen_lines: int,
) -> None:
    exit_code = process.poll()

    if LOG_FILE.exists():
        try:
            lines = LOG_FILE.read_text(
                encoding="utf-8"
            ).splitlines()
        except OSError:
            lines = [str(exit_code or "ошибка")]
    else:
        lines = []

    # Финальный проход: даже если строка с Import key потерялась
    # из-за порционной записи — ищем её по всему логу.
    for line in lines:
        if not commit_key and "Import key:" in line:
            commit_key = line.split(":", 1)[1].strip()

        _apply_line(status, line)

    status["exit_code"] = exit_code
    status["finished_at"] = _now()
    status["commit_key"] = commit_key
    status["log_tail"] = lines[-100:]

    # Ошибки собираем из staging + media_plan (если ещё на месте;
    # иначе — только.. журнал). Всегда обновляем, если нашли.
    if commit_key and not collected:
        errors = collect_staging_errors(commit_key)

        if errors:
            status["errors"] = errors

        collected = True

    if exit_code == 0:
        status["state"] = "success"

        if not dry_run:
            archived = archive_previous_after_success()

            if archived:
                status["archived_previous"] = archived
    else:
        status["state"] = "error"

    _archive_run_log(commit_key)

    _write_status(status)

    try:
        log_handle.close()
    except Exception:
        pass


# ---------------------------------------------------------------- чтение


def get_update_status() -> dict:
    """Текущий статус обновления (для индикаторов фронта)."""
    status = _read_status()

    if _is_running() and status.get("state") != "running":
        status["state"] = "running"

    return status


def get_update_log() -> str:
    """Полный текст лога последнего обновления."""
    if not LOG_FILE.exists():
        return ""

    return LOG_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------- история логов


def _safe_log_name(name: str) -> bool:
    return ".." not in name and "/" not in name and "\\" not in name


def _archive_run_log(import_key: str | None = None) -> str | None:
    """Сохраняет лог прошедшего обновления в update_logs/ с именем
    log_<ключ>.txt. Возвращает имя файла или None."""
    if not LOG_FILE.exists():
        return None

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if import_key:
        stamp = import_key
    else:
        stamp = _dt.datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )

    name = f"log_{stamp}.txt"
    destination = LOGS_DIR / name

    destination.write_text(
        LOG_FILE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    return name


def list_update_logs() -> list[dict]:
    """Список сохранённых логов обновлений (свежие первыми)."""
    if not LOGS_DIR.exists():
        return []

    logs = []

    for item in sorted(LOGS_DIR.glob("log_*.txt"), reverse=True):
        stat = item.stat()
        created = _dt.datetime.fromtimestamp(stat.st_mtime)

        logs.append(
            {
                "name": item.name,
                "label": "Лог " + created.strftime("%Y-%m-%d %H:%M:%S"),
                "created_at": created.isoformat(
                    timespec="seconds"
                ),
                "size": stat.st_size,
                "url": f"/api/admin/base/update/logs/{item.name}",
            }
        )

    return logs


def get_update_log_by_name(name: str) -> str:
    """Текст лога по имени файла."""
    if not _safe_log_name(name):
        raise ValueError("Недопустимое имя лога")

    path = LOGS_DIR / name

    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Лог не найден")

    return path.read_text(encoding="utf-8")