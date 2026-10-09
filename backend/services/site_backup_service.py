"""Бекапы сайта.

Бекап сайта — это всё, что НЕ приходит из XLS-файла: новости, страницы,
настройки, пользователи, контакты, статистика и медиа сайта. Данные
конструкций в бекап не входят и при восстановлении не затрагиваются.

Хранится в ``archive/site/<YYYYMMDD-HHMMSS>/`` (database.dump + media/ +
meta.json). Авто-бекап создаётся раз в 7 дней, хранится не более 5 штук.
Перед восстановлением текущее состояние тоже сохраняется в бекап.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

from backend.services.import_archive_service import (
    CONSTRUCTIONS_SEQUENCES,
    CONSTRUCTIONS_TABLES,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]

SITE_BACKUP_ROOT = PROJECT_DIR / "archive" / "site"

# Медиа сайта (не конструкций).
SITE_MEDIA_DIRS = ("media", "news", "misc")

# Не более 5 бекапов; авто-бекап не чаще, чем раз в 7 дней.
KEEP_BACKUPS = 5
AUTO_INTERVAL_DAYS = 7

# Идентификатор advisory-блокировки, чтобы авто-бекап создавался один раз
# даже при нескольких worker'ах uvicorn.
_LOCK_ID = 815_223_001


# ---------------------------------------------------------------- утилиты


def _db_params() -> tuple[list[str], dict]:
    password = None
    env_file = PROJECT_DIR / ".env"

    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("ALBION_DB_PASSWORD="):
                password = line.split("=", 1)[1].strip()
                break

    if not password:
        raise RuntimeError("Не найден ALBION_DB_PASSWORD в .env")

    params = [
        "-h", os.getenv("ALBION_DB_HOST", "127.0.0.1"),
        "-p", os.getenv("ALBION_DB_PORT", "5432"),
        "-U", os.getenv("ALBION_DB_USER", "albion_app"),
        "-d", os.getenv("ALBION_DB_NAME", "albion"),
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    return params, env


def _exclude_constructions_selectors() -> list[str]:
    selectors: list[str] = []

    for name in (*CONSTRUCTIONS_TABLES, *CONSTRUCTIONS_SEQUENCES):
        selectors += ["-T", name]

    return selectors


def _backup_dirs() -> list[Path]:
    if not SITE_BACKUP_ROOT.exists():
        return []

    return sorted(
        (
            path
            for path in SITE_BACKUP_ROOT.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        ),
        key=lambda path: path.name,
        reverse=True,
    )


def _prune() -> list[str]:
    removed = []

    for path in _backup_dirs()[KEEP_BACKUPS:]:
        shutil.rmtree(path)
        removed.append(path.name)

    return removed


def _read_meta(directory: Path) -> dict:
    meta_file = directory / "meta.json"

    if not meta_file.exists():
        return {}

    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def list_backups() -> list[dict]:
    result = []

    for directory in _backup_dirs():
        meta = _read_meta(directory)
        dump = directory / "database.dump"
        media = directory / "media"

        size_bytes = sum(
            item.stat().st_size
            for item in directory.rglob("*")
            if item.is_file()
        )

        created_at = meta.get("created_at") or datetime.datetime.fromtimestamp(
            directory.stat().st_mtime
        ).isoformat()

        result.append(
            {
                "name": directory.name,
                "reason": meta.get("reason", "unknown"),
                "created_at": created_at,
                "database_exists": dump.exists(),
                "media_exists": media.exists(),
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / 1024 / 1024, 2),
            }
        )

    return result


# ---------------------------------------------------------------- создание


def create_backup(reason: str = "manual") -> dict:
    """Создать бекап сайта. Возвращает описание бекапа."""
    SITE_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = stamp
    directory = SITE_BACKUP_ROOT / name

    # Очень редкая коллизия имён (в пределах секунды) — добавим суффикс.
    suffix = 1
    while directory.exists():
        name = f"{stamp}-{suffix}"
        directory = SITE_BACKUP_ROOT / name
        suffix += 1

    directory.mkdir(parents=True)

    params, env = _db_params()

    dump_file = directory / "database.dump"

    result = subprocess.run(
        [
            "pg_dump",
            "-Fc",
            *_exclude_constructions_selectors(),
            *params,
            "-f",
            str(dump_file),
        ],
        cwd=PROJECT_DIR,
        env=env,
    )

    if result.returncode != 0:
        shutil.rmtree(directory, ignore_errors=True)
        raise RuntimeError(
            f"pg_dump завершился с кодом {result.returncode}"
        )

    # Медиа сайта
    storage_root = PROJECT_DIR / "storage"
    media_dst = directory / "media"
    copied_any = False

    for sub in SITE_MEDIA_DIRS:
        source = storage_root / sub

        if not source.exists():
            continue

        media_dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, media_dst / sub)
        copied_any = True

    meta = {
        "name": name,
        "reason": reason,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "media_dirs": [d for d in SITE_MEDIA_DIRS if copied_any],
    }

    (directory / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    removed = _prune()
    meta["pruned"] = removed

    return meta


# ---------------------------------------------------------------- авто-бекап


def ensure_weekly_backup() -> bool:
    """Создать авто-бекап, если последнего не было 7+ дней.

    Возвращает True, если бекап был создан. Защищено advisory-блокировкой,
    чтобы несколько worker'ов не создали дубликаты.
    """
    from backend.services.data_service import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (_LOCK_ID,))
            locked = cur.fetchone()[0]

        if not locked:
            return False

        try:
            dirs = _backup_dirs()

            if dirs:
                latest = datetime.datetime.fromtimestamp(
                    dirs[0].stat().st_mtime
                )
                age = datetime.datetime.now() - latest

                if age < datetime.timedelta(days=AUTO_INTERVAL_DAYS):
                    return False

            create_backup("auto")
            return True
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_ID,))


# ---------------------------------------------------------------- восстановление


def restore_backup(name: str, dry_run: bool = False) -> dict:
    """Восстановить бекап сайта.

    Перед реальным восстановлением текущее состояние сохраняется в новый
    бекап. Таблицы конструкций не затрагиваются.
    """
    directory = SITE_BACKUP_ROOT / name
    dump_file = directory / "database.dump"
    media_src = directory / "media"

    if not name or "/" in name or ".." in name:
        raise ValueError("Некорректное имя бекапа")

    if not dump_file.exists():
        raise RuntimeError(f"Бекап не найден: {dump_file}")

    media_files = (
        [item for item in media_src.rglob("*") if item.is_file()]
        if media_src.exists()
        else []
    )

    steps: list[dict] = []

    def add_step(name_: str, status: str) -> None:
        steps.append({"name": name_, "status": status})

    if dry_run:
        add_step("database.dump", "найден")
        add_step("таблицы", "все, кроме конструкций")
        add_step("media", f"файлов: {len(media_files)}" if media_files else "нет")
        add_step("сохранение текущего", "перед восстановлением")

        return {
            "success": True,
            "dry_run": True,
            "name": name,
            "steps": steps,
        }

    # 1) Сохраняем текущее состояние, чтобы его можно было вернуть.
    current = create_backup("before-restore")
    add_step("сохранение текущего", f"создан бекап {current['name']}")

    params, env = _db_params()

    result = subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            *params,
            str(dump_file),
        ],
        cwd=PROJECT_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        fatal = [
            line.strip()
            for line in (result.stderr or "").splitlines()
            if line.startswith("pg_restore: error:")
            and "already exists" not in line
            and "postgis" not in line.lower()
        ]

        if result.returncode not in (0, 1) or fatal:
            raise RuntimeError(
                "pg_restore завершился с ошибкой: "
                + ("; ".join(fatal) or (result.stderr or "").strip()[:500])
            )

    add_step("PostgreSQL (сайт)", "восстановлено из бекапа")

    # 2) Медиа сайта
    storage_root = PROJECT_DIR / "storage"
    copied_total = 0

    for sub in SITE_MEDIA_DIRS:
        source = media_src / sub

        if not source.exists():
            continue

        destination = storage_root / sub
        destination.mkdir(parents=True, exist_ok=True)

        for item in source.rglob("*"):
            if not item.is_file():
                continue

            target = destination / item.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied_total += 1

    add_step("media сайта → storage", f"скопировано файлов: {copied_total}")

    # 3) Проверка
    verify: dict = {}

    try:
        from backend.services.data_service import (
            get_connection,
            invalidate_data_cache,
        )

        invalidate_data_cache()

        with get_connection() as conn:
            with conn.cursor() as cur:
                counts = {}
                for table in (
                    "news",
                    "site_settings",
                    "user_accounts",
                    "site_menu_items",
                    "media",
                ):
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                        counts[table] = cur.fetchone()[0]
                    except Exception:
                        pass
                verify["counts"] = counts

                preserved = {}
                for table in ("constructions", "surfaces", "construction_media"):
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                        preserved[table] = cur.fetchone()[0]
                    except Exception:
                        pass
                verify["preserved"] = preserved

        add_step("проверка", "выполнена")
    except Exception as exc:
        add_step("проверка", f"ошибка: {exc}")

    return {
        "success": True,
        "name": name,
        "steps": steps,
        "verify": verify,
    }


# ---------------------------------------------------------------- планировщик


def start_scheduler() -> None:
    """Запустить фоновый поток авто-бекапа (раз в 7 дней)."""
    import threading
    import time

    def _loop() -> None:
        # Первая проверка — сразу при старте, дальше — раз в 6 часов.
        while True:
            try:
                ensure_weekly_backup()
            except Exception:
                pass

            time.sleep(6 * 60 * 60)

    thread = threading.Thread(
        target=_loop,
        name="albion-site-backup",
        daemon=True,
    )
    thread.start()
