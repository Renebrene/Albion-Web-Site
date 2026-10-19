from pathlib import Path
from contextlib import contextmanager
import datetime
import json
import os


PROJECT_DIR = Path(__file__).resolve().parents[2]
MAINTENANCE_FILE = PROJECT_DIR / "tmp" / ".maintenance.json"

ARCHIVE_ROOT = PROJECT_DIR / "archive"

# Архив данных, которые приходят из Excel-файла (конструкции и их медиа).
CONSTRUCTIONS_ARCHIVE_ROOT = ARCHIVE_ROOT / "constructions"

# Резервные копии перед восстановлением (не показываются в списках).
SAFETY_ROOT = ARCHIVE_ROOT / "_safety"

# Данные, которые приходят из XLS-файла. Обновление и восстановление базы
# конструкций затрагивает ТОЛЬКО эти таблицы — прочее (новости, настройки,
# пользователи, контакты) не меняется.
CONSTRUCTIONS_TABLES = (
    "construction_imports",
    "cities",
    "constructions",
    "surfaces",
    "surface_availability",
    "construction_media",
    "construction_month_overrides",
    "media_import_registry",
)

CONSTRUCTIONS_SEQUENCES = tuple(
    f"{table}_id_seq"
    for table in CONSTRUCTIONS_TABLES
)


def get_dir_size(path: Path) -> int:
    total = 0

    if not path.exists():
        return 0

    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size

    return total


def list_archives() -> list[dict]:
    root = CONSTRUCTIONS_ARCHIVE_ROOT
    result = []

    if not root.exists():
        return result

    for item in sorted(root.iterdir(), reverse=True):
        if (
            not item.is_dir()
            or item.name.startswith("_")
            or item.name.endswith("_safety")
        ):
            continue

        source = item / "source.xlsx"
        dump = item / "database.dump"
        media = item / "media"

        size_bytes = get_dir_size(item)

        result.append(
            {
                "import_key": item.name,

                "created_at": datetime.datetime.fromtimestamp(
                    item.stat().st_mtime
                ).isoformat(),

                "source_exists": source.exists(),
                "database_exists": dump.exists(),
                "media_exists": media.exists(),

                "size_bytes": size_bytes,

                "size_mb": round(
                    size_bytes / 1024 / 1024,
                    2,
                ),
            }
        )

    return result


def _copy_into(source: Path, destination: Path) -> int:
    """Скопировать содержимое каталога ``source`` в ``destination``.

    Файлы, уже лежащие на месте (тот же inode — например, архив-снимок
    перед обновлением сделан жёсткими ссылками на этот же storage),
    пропускаем: копирование «файла в самого себя» падает SameFileError.
    """
    import shutil

    copied = 0

    for item in source.rglob("*"):
        if not item.is_file():
            continue

        target = destination / item.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            if target.exists() and target.samefile(item):
                continue
        except OSError:
            pass

        shutil.copy2(item, target)
        copied += 1

    return copied


def _dump_tables(dump_file: Path, env: dict) -> set[str]:
    """Таблицы public, присутствующие в дампе (custom-формат)."""
    import subprocess

    try:
        proc = subprocess.run(
            ["pg_restore", "-l", str(dump_file)],
            capture_output=True,
            text=True,
            env=env,
        )
    except Exception:
        return set()

    if proc.returncode != 0:
        return set()

    tables: set[str] = set()

    for line in proc.stdout.splitlines():
        parts = line.split()

        if "TABLE" in parts and "public" in parts:
            index = parts.index("public")

            if index + 1 < len(parts):
                tables.add(parts[index + 1])

    return tables


def _restore_archive_impl(import_key: str, dry_run: bool = False) -> dict:
    """Восстановить из архива данные, пришедшие из XLS.

    Затрагивает только таблицы конструкций и их медиа. Новости, настройки,
    пользователи, контакты и прочее не меняются.
    ``dry_run=True`` — только план, без изменений.
    """
    import os
    import shutil
    import subprocess

    archive_dir = CONSTRUCTIONS_ARCHIVE_ROOT / import_key
    dump_file = archive_dir / "database.dump"
    media_src = archive_dir / "media"

    if not dump_file.exists():
        raise RuntimeError(f"Архив PostgreSQL не найден: {dump_file}")

    media_files = (
        [item for item in media_src.rglob("*") if item.is_file()]
        if media_src.exists()
        else []
    )

    steps: list[dict] = []

    def add_step(name: str, status: str, path: Path | None = None) -> None:
        entry = {"name": name, "status": status}
        if path is not None:
            entry["path"] = str(path)
        steps.append(entry)

    # ---- План (dry-run) ----
    if dry_run:
        present = _dump_tables(dump_file, os.environ.copy())
        planned = (
            [t for t in CONSTRUCTIONS_TABLES if t in present]
            if present
            else list(CONSTRUCTIONS_TABLES)
        )
        add_step("database.dump", "найден", dump_file)
        add_step("таблицы конструкций", ", ".join(planned))
        add_step(
            "media",
            f"файлов: {len(media_files)}" if media_files else "нет",
            media_src if media_files else None,
        )
        add_step("_safety", "создать копию текущей базы")

        return {
            "success": True,
            "dry_run": True,
            "import_key": import_key,
            "steps": steps,
        }

    env = os.environ.copy()

    host = env.get("ALBION_DB_HOST", "127.0.0.1")
    port = env.get("ALBION_DB_PORT", "5432")
    user = env.get("ALBION_DB_USER", "albion_app")
    name = env.get("ALBION_DB_NAME", "albion")

    db_args = ["-h", host, "-p", port, "-U", user, "-d", name]

    if env.get("ALBION_DB_PASSWORD"):
        env["PGPASSWORD"] = env["ALBION_DB_PASSWORD"]

    # 1) _safety — резервная копия текущей базы (custom-формат)
    safety_key = (
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "_restore"
    )
    safety_dir = SAFETY_ROOT / safety_key
    safety_dir.mkdir(parents=True, exist_ok=True)
    safety_dump = safety_dir / "database.dump"

    try:
        subprocess.run(
            ["pg_dump", "-Fc", "--no-owner", *db_args, "-f", str(safety_dump)],
            env=env,
            check=True,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось создать _safety-копию текущей базы: {exc}"
        ) from exc

    add_step("_safety-копия текущей базы", "создана", safety_dir)

    # 2) Пересоздаём только таблицы конструкций, которые есть в архиве.
    #    Старые архивы могли не содержать часть таблиц (например, cities) —
    #    такие не трогаем, чтобы случайно их не потерять.
    present = _dump_tables(dump_file, env)
    tables = (
        [t for t in CONSTRUCTIONS_TABLES if t in present]
        if present
        else list(CONSTRUCTIONS_TABLES)
    )

    # Восстанавливаем ТОЛЬКО таблицы конструкций. Архив может быть ПОЛНЫМ
    # дампом базы — без фильтра `-t` мы бы перезаписали данные сайта
    # (новости, настройки, пользователи, медиа). `--clean --if-exists`
    # пересоздаёт только выбранные таблицы, а `--single-transaction` делает
    # DROP + restore атомарными: при ошибке старые таблицы остаются.
    restore_args = [
        "pg_restore",
        "--no-owner",
        "--clean",
        "--if-exists",
        "--single-transaction",
    ]

    for table in tables:
        restore_args += ["-t", table]

    for table in tables:
        restore_args += ["-t", f"{table}_id_seq"]

    restore_proc = subprocess.run(
        [*restore_args, *db_args, str(dump_file)],
        env=env,
        capture_output=True,
        text=True,
    )

    if restore_proc.returncode != 0:
        # pg_restore возвращает код 1, если часть команд не применилась.
        # «already exists» и права на расширение postgis ожидаемы и не мешают
        # восстановлению данных; любые другие ошибки считаем фатальными.
        fatal = [
            line.strip()
            for line in (restore_proc.stderr or "").splitlines()
            if line.startswith("pg_restore: error:")
            and "already exists" not in line
            and "postgis" not in line.lower()
        ]

        if restore_proc.returncode not in (0, 1) or fatal:
            raise RuntimeError(
                "pg_restore завершился с ошибкой: "
                + (
                    "; ".join(fatal)
                    or (restore_proc.stderr or "").strip()[:500]
                )
            )

    # Дотягиваем схему конструкций: `pg_restore -t` не переносит отдельные
    # записи DEFAULT/CONSTRAINT (PK/UNIQUE/FK) и индексы.
    try:
        from backend.services.constructions_schema import repair_schema

        with get_connection() as conn:
            repair_schema(conn)

        add_step(
            "схема конструкций",
            "выровнена (DEFAULT/PK/UNIQUE/FK/индексы)",
        )
    except Exception as exc:
        add_step("схема конструкций", f"ошибка выравнивания: {exc}")

    add_step("PostgreSQL (конструкции)", "восстановлено из архива", dump_file)

    # 3) Медиа конструкций
    if media_files:
        destination = (
            PROJECT_DIR
            / "storage"
            / "constructions"
            / "imports"
            / import_key
        )
        destination.mkdir(parents=True, exist_ok=True)
        copied = _copy_into(media_src, destination)
        add_step("media → storage", f"скопировано файлов: {copied}", destination)
    else:
        add_step("media", "в архиве нет")

    # 4) Проверка
    verify: dict = {}

    try:
        from backend.services.data_service import (
            invalidate_data_cache,
        )

        invalidate_data_cache()

        with get_connection() as conn:
            with conn.cursor() as cur:
                counts = {}
                for table in CONSTRUCTIONS_TABLES:
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM public."{table}"')
                        counts[table] = cur.fetchone()[0]
                    except Exception:
                        pass
                verify["counts"] = counts

                preserved = {}
                for table in ("news", "site_menu_items", "user_accounts"):
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
        "import_key": import_key,
        "steps": steps,
        "verify": verify,
    }


def _set_maintenance(active: bool, import_key: str = "") -> None:
    """Межпроцессный флаг: API не должно читать таблицы во время restore."""
    try:
        if active:
            MAINTENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = MAINTENANCE_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "kind": "restore",
                        "import_key": import_key,
                        "started_at": datetime.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, MAINTENANCE_FILE)
        else:
            MAINTENANCE_FILE.unlink(missing_ok=True)
    except OSError:
        # Флаг не должен ломать само восстановление.
        pass


@contextmanager
def _restore_guard(import_key: str):
    """Тот же advisory-lock, что у импорта, плюс maintenance-флаг."""
    from backend.services.data_service import get_raw_connection
    from backend.services.update_service import _UPDATE_LOCK_ID

    conn = get_raw_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (_UPDATE_LOCK_ID,),
            )
            locked = cur.fetchone()[0]

        if not locked:
            raise RuntimeError(
                "Импорт или восстановление уже выполняется"
            )

        _set_maintenance(True, import_key)

        try:
            yield
        finally:
            _set_maintenance(False)
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (_UPDATE_LOCK_ID,),
                )
        except Exception:
            pass
        conn.close()


def _process_holds_update_lock() -> bool:
    """True, если этот процесс уже держит advisory-lock импорта.

    Нужно для авто-отката: он вызывается из monitor-потока до
    `_release_update_lock()`, и повторный `pg_try_advisory_lock` на другом
    соединении всегда вернул бы False.
    """
    try:
        from backend.services.update_service import _LOCK_CONN

        return _LOCK_CONN is not None
    except Exception:
        return False


def restore_archive(import_key: str, dry_run: bool = False) -> dict:
    """Публичная точка входа: план без изменений или restore под guard."""
    if dry_run:
        return _restore_archive_impl(import_key, dry_run=True)

    if _process_holds_update_lock():
        _set_maintenance(True, import_key)
        try:
            return _restore_archive_impl(import_key, dry_run=False)
        finally:
            _set_maintenance(False)

    with _restore_guard(import_key):
        return _restore_archive_impl(import_key, dry_run=False)
