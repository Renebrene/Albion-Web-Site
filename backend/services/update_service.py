from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from backend.services.data_service import (
    get_base_stats,
    get_connection,
    invalidate_data_cache,
)
from typing import Optional

from backend.services.data_service import (
    load_env_file,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]

INPUT_DIR = PROJECT_DIR / "input"
PREVIOUS_DIR = INPUT_DIR / ".previous"


def _input_files() -> list[Path]:
    """Excel-файлы в input/ — кандидаты на обновление базы."""
    if not INPUT_DIR.exists():
        return []

    return [
        item
        for item in INPUT_DIR.iterdir()
        if item.is_file() and item.suffix.lower() in {".xlsx", ".xls"}
    ]


# Кэш проверки файла (путь+mtime+размер), чтобы не открывать Excel на
# каждый опрос статуса.
_input_check_cache: dict = {"key": None, "result": (True, None)}


def _validate_input(path: Path) -> "tuple[bool, Optional[str]]":
    """Пригоден ли Excel: есть лист и распознаётся ли строка заголовков."""
    try:
        from openpyxl import load_workbook
    except Exception:
        return True, None

    try:
        book = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        return False, f"не удалось открыть файл: {exc}"

    try:
        if not book.worksheets:
            return False, "в книге нет листов"

        from backend.importer.constructions_excel_to_json import (
            find_header_row,
        )

        try:
            find_header_row(book.worksheets[0])
        except Exception as exc:
            return False, str(exc)
    finally:
        try:
            book.close()
        except Exception:
            pass

    return True, None


def check_input_file(path: Path) -> "tuple[bool, Optional[str]]":
    """Валидность файла с кэшем по (путь, mtime, размер)."""
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return False, "файл недоступен"

    if _input_check_cache.get("key") == key:
        return _input_check_cache["result"]

    result = _validate_input(path)
    _input_check_cache["key"] = key
    _input_check_cache["result"] = result

    return result
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

# Факт последнего восстановления базы из архива (для отображения в админке).
RESTORE_FILE = TMP_DIR / "last_restore.json"

# Факт последнего восстановления «всего остального» (часть site).
SITE_RESTORE_FILE = TMP_DIR / "last_site_restore.json"

_RESTORE_FILES = {
    "constructions": RESTORE_FILE,
    "site": SITE_RESTORE_FILE,
}

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

# Advisory-lock, чтобы обновление не запустилось дважды из разных воркеров
# uvicorn: in-process _LOCK защищает только внутри одного процесса.
# Идентификатор не пересекается с авто-бекапом сайта (815223001).
_UPDATE_LOCK_ID = 815_223_002

# Соединение, удерживающее advisory-lock на время прогона. Advisory-lock
# сессионный, поэтому соединение держим открытым, пока идёт обновление.
_LOCK_CONN = None

# Пользователь запросил остановку — чтобы монитор пометил прогон как
# «остановлен», а не «ошибка».
_STOP_REQUESTED = False


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


def _convert_excel_to_xlsx(
    filename: str,
    content: bytes,
) -> tuple[str, bytes] | None:
    """Пересохраняет Excel в стандартный OOXML .xlsx через LibreOffice.

    Сырые выгрузки 1С часто не читаются openpyxl (старый .xls и др.);
    LibreOffice (headless) приводит файл к формату, который импортёр
    понимает. Возвращает (имя, байты) либо None, если конвертация
    недоступна или не удалась — тогда файл сохраняется как есть.
    """
    binary = shutil.which("soffice") or shutil.which("libreoffice")

    if binary is None:
        return None

    with tempfile.TemporaryDirectory(prefix="xlsx-convert-") as work:
        work_dir = Path(work)
        source = work_dir / Path(filename).name
        source.write_bytes(content)

        out_dir = work_dir / "out"
        out_dir.mkdir()

        command = [
            binary,
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation=file://{work_dir / 'profile'}",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(out_dir),
            str(source),
        ]

        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except Exception:
            return None

        produced = sorted(out_dir.glob("*.xlsx"))

        if not produced:
            return None

        return (
            f"{Path(filename).stem}.xlsx",
            produced[0].read_bytes(),
        )


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

    # Приводим файл к «чистому» OOXML .xlsx через LibreOffice: сырые
    # выгрузки 1С бывают в форматах, которые openpyxl не читает.
    converted = _convert_excel_to_xlsx(Path(filename).name, content)

    if converted is not None:
        file_name, file_bytes = converted
    else:
        file_name, file_bytes = Path(filename).name, content

    destination = INPUT_DIR / file_name
    destination.write_bytes(file_bytes)

    return {
        "success": True,
        "filename": destination.name,
        "size": len(file_bytes),
        "saved": str(
            destination.relative_to(PROJECT_DIR)
        ),
        "moved_previous": moved_previous,
        "converted": converted is not None,
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


def _acquire_update_lock() -> bool:
    """Взять advisory-lock обновления (межпроцессная защита).

    Возвращает True, если этот процесс получил блокировку. Соединение
    держим открытым (в _LOCK_CONN) до конца прогона: при закрытии
    соединения advisory-lock снимается сам.
    """
    global _LOCK_CONN

    if _LOCK_CONN is not None:
        return True

    conn = get_connection()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (_UPDATE_LOCK_ID,))
            locked = cur.fetchone()[0]
    except Exception:
        conn.close()
        raise

    if not locked:
        conn.close()
        return False

    _LOCK_CONN = conn
    return True


def _release_update_lock() -> None:
    global _LOCK_CONN

    if _LOCK_CONN is None:
        return

    try:
        with _LOCK_CONN.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_UPDATE_LOCK_ID,))
    except Exception:
        pass

    try:
        _LOCK_CONN.close()
    except Exception:
        pass

    _LOCK_CONN = None


def start_update(
    *,
    dry_run: bool = False,
) -> dict:
    """Запускает полный конвейер обновления базы в подпроцессе."""
    global _PROCESS, _STOP_REQUESTED

    with _LOCK:
        if _is_running():
            raise RuntimeError(
                "Обновление уже выполняется"
            )

        _STOP_REQUESTED = False

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

        # Межпроцессная защита: in-process _LOCK защищает только внутри
        # одного воркера, поэтому берём advisory-lock в БД. Не получилось —
        # обновление уже идёт в другом процессе.
        if not _acquire_update_lock():
            raise RuntimeError(
                "Обновление уже выполняется (другой процесс)"
            )

        try:
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
                # Своя сессия/группа процессов — чтобы «Остановить» убил и
                # пайплайн, и запущенные им стадии-подпроцессы.
                start_new_session=True,
            )

            threading.Thread(
                target=_monitor,
                args=(_PROCESS, dry_run, log_handle),
                daemon=True,
            ).start()
        except Exception:
            # Не удалось запустить — освобождаем блокировку.
            _release_update_lock()
            raise

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


def stop_update() -> dict:
    """Останавливает текущий прогон обновления/ dry-run.

    Убивает всю группу процессов (сам пайплайн и запущенные им
    стадии-подпроцессы). Монитор затем пометит прогон как «stopped».
    """
    global _STOP_REQUESTED

    with _LOCK:
        process = _PROCESS

        if process is None or process.poll() is not None:
            return {"success": False, "state": "not_running"}

        _STOP_REQUESTED = True
        pid = process.pid

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass

    try:
        process.wait(timeout=10)
    except Exception:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    return {"success": True, "state": "stopping"}


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


def _extract_failure(lines: list[str]) -> list[str]:
    """Суть ошибки из лога: последний traceback либо строки с ошибкой.

    Стадия могла упасть раньше staging/медиа — тогда
    collect_staging_errors ничего не находит, и раздел «лог об ошибках»
    оставался пустым, хотя прогон завершился с ошибкой.
    """
    # Первый traceback — корневая причина; последующие обычно лишь
    # оборачивают её («стадия завершилась с кодом 1»).
    first_tb = None

    for index, line in enumerate(lines):
        if "Traceback (most recent call last)" in line:
            first_tb = index
            break

    if first_tb is not None:
        return lines[first_tb:]

    picked = [
        line
        for line in lines
        if re.search(r"error|exception|ошибк|failed", line, re.I)
    ]

    if picked:
        return picked[-8:]

    return lines[-10:] if lines else []


def _finish(
    status: dict,
    process: subprocess.Popen,
    dry_run: bool,
    commit_key: Optional[str],
    collected: bool,
    seen_lines: int,
) -> None:
    global _STOP_REQUESTED

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

    if _STOP_REQUESTED:
        # Прогон остановлен пользователем — это не ошибка.
        status["state"] = "stopped"
        status["errors"] = []
    elif exit_code == 0:
        status["state"] = "success"

        if not dry_run:
            archived = archive_previous_after_success()

            if archived:
                status["archived_previous"] = archived

            # Данные изменились — сбрасываем кэш /api/constructions,
            # чтобы карта/список отдали свежий список сразу.
            invalidate_data_cache()

            # База теперь из нового импорта, а не из архива — снимаем
            # пометку о восстановлении.
            clear_last_restore()
    else:
        status["state"] = "error"

        # Реальная причина из лога: падение могло случиться до staging,
        # и тогда collect_staging_errors() пуст («Ошибок не обнаружено»).
        if not status.get("errors"):
            failure = _extract_failure(lines)

            if failure:
                status["errors"] = failure

    _archive_run_log(commit_key)

    _STOP_REQUESTED = False

    _write_status(status)

    try:
        log_handle.close()
    except Exception:
        pass

    # Прогон завершён — снимаем межпроцессную блокировку.
    _release_update_lock()


# ---------------------------------------------------------------- чтение


def get_update_status() -> dict:
    """Текущий статус обновления (для индикаторов фронта)."""
    status = _read_status()

    if _is_running() and status.get("state") != "running":
        status["state"] = "running"

    # Файл, ожидающий обновления (в input/). Показываем его присутствие,
    # имя, размер и дату загрузки (mtime).
    files = _input_files()

    if files:
        pending = files[0]

        try:
            stat = pending.stat()
            mtime = _dt.datetime.fromtimestamp(stat.st_mtime).isoformat()
            size = stat.st_size
        except OSError:
            mtime = None
            size = None

        valid, problem = check_input_file(pending)

        status["input_pending"] = {
            "name": pending.name,
            "size": size,
            "mtime": mtime,
            "valid": valid,
            "problem": problem,
        }
    else:
        status["input_pending"] = None

    # Запуск возможен, только когда в input/ ровно один Excel (как требует
    # start_update). После успешного обновления файл уходит в архив — тогда
    # кнопка «Обновить» недоступна до загрузки нового файла.
    status["input_ready"] = len(files) == 1

    # Последнее восстановление базы из архива (если было).
    status["last_restore"] = get_last_restore()

    return status


def record_restore(import_key: str, kind: str = "constructions") -> None:
    """Запомнить факт восстановления из архива (import_key)."""
    path = _RESTORE_FILES.get(kind, RESTORE_FILE)

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Ключ вида YYYYMMDD-HHMMSS → дата самой восстановленной базы.
    match = re.match(r"(\d{4})(\d{2})(\d{2})", str(import_key))
    base_date = (
        f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if match
        else None
    )

    payload = {
        "kind": kind,
        "import_key": str(import_key),
        "base_date": base_date,
        "restored_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_last_restore(kind: str = "constructions") -> None:
    """Сбросить пометку о восстановлении (после нового успешного импорта)."""
    try:
        _RESTORE_FILES.get(kind, RESTORE_FILE).unlink()
    except OSError:
        pass


def mark_restored(import_key: str) -> None:
    """Зафиксировать восстановление базы из архива.

    Дополнительно сбрасываем статус обновления: ошибка прошлого прогона
    больше не актуальна, а «Дата и время последнего обновления» показывает
    дату восстановленной базы (created_at активного импорта).
    """
    record_restore(import_key)

    base_datetime = None

    try:
        value = get_base_stats().get("last_update")

        if hasattr(value, "isoformat"):
            base_datetime = value.isoformat()
        elif value:
            base_datetime = str(value)
    except Exception:
        base_datetime = None

    status = _read_status()
    status["state"] = "idle"
    status["errors"] = []
    status["exit_code"] = None

    if base_datetime:
        status["finished_at"] = base_datetime

    _write_status(status)


def get_last_run_state() -> "Optional[str]":
    """Состояние последнего запуска обновления ('success'/'error'/…)."""
    return _read_status().get("state")


def get_last_restore(kind: str = "constructions") -> "Optional[dict]":
    """Последнее восстановление из архива или None."""
    path = _RESTORE_FILES.get(kind, RESTORE_FILE)

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    return data if isinstance(data, dict) else None


def mark_site_restored(import_key: str) -> None:
    """Зафиксировать восстановление части «всё остальное».

    Дату актуальной базы конструкций и статус обновления не трогаем —
    они относятся к части конструкций.
    """
    record_restore(import_key, kind="site")


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