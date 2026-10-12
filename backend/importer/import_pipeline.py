from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from backend.services.import_archive_service import (
    CONSTRUCTIONS_ARCHIVE_ROOT,
    CONSTRUCTIONS_SEQUENCES,
    CONSTRUCTIONS_TABLES,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_DIR / "input"
TMP_DIR = PROJECT_DIR / "tmp"
IMPORT_DIR = TMP_DIR / "import"
ARCHIVE_DIR = CONSTRUCTIONS_ARCHIVE_ROOT

# Сколько архивов конструкций храним (ручные и автоматические вместе).
KEEP_ARCHIVES = 5


def load_project_env() -> dict[str, str]:
    env: dict[str, str] = {}

    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        return env

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key.startswith("ALBION_DB_"):
            env[key] = value

    return env


def run_stage(module: str, *, env: dict[str, str] | None = None) -> None:
    command_env = os.environ.copy()
    command_env.update(load_project_env())

    if env:
        command_env.update(env)

    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_DIR,
        env=command_env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Стадия {module} завершилась с кодом {result.returncode}"
        )


def find_source_file() -> Path:
    files = sorted(
        p
        for p in INPUT_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".xlsx", ".xls"}
    )

    if not files:
        raise RuntimeError(
            f"В каталоге {INPUT_DIR} нет XLS/XLSX файла"
        )

    if len(files) > 1:
        names = ", ".join(p.name for p in files)
        raise RuntimeError(
            "Для одного импорта должен быть ровно один Excel-файл. "
            f"Найдены: {names}"
        )

    return files[0]


def find_import_key() -> str:
    staging_files = sorted(
        IMPORT_DIR.glob("*/staging.sqlite"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not staging_files:
        raise RuntimeError(
            "После staging не найден staging.sqlite"
        )

    return staging_files[0].parent.name


def read_load_result(import_key: str) -> dict:
    result_path = IMPORT_DIR / import_key / "load_result.json"

    if not result_path.exists():
        raise RuntimeError(
            f"Результат PostgreSQL import не найден: {result_path}"
        )

    return json.loads(result_path.read_text(encoding="utf-8"))


def archive_source(source: Path, import_key: str) -> Path:
    archive_root = ARCHIVE_DIR / import_key
    archive_root.mkdir(parents=True, exist_ok=True)

    destination = archive_root / "source.xlsx"

    if destination.exists():
        raise RuntimeError(
            f"Архивный source.xlsx уже существует: {destination}"
        )

    shutil.copy2(source, destination)
    return destination


def _db_params() -> tuple[list[str], dict[str, str]]:
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

    command_env = os.environ.copy()
    command_env["PGPASSWORD"] = password

    return params, command_env


def _pg_dump(destination: Path, selectors: list[str]) -> None:
    params, command_env = _db_params()
    destination.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["pg_dump", "-Fc", *selectors, *params, "-f", str(destination)],
        cwd=PROJECT_DIR,
        env=command_env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"pg_dump завершился с кодом {result.returncode}"
        )


def archive_constructions_database(import_key: str) -> Path:
    """Архив данных из XLS: только таблицы конструкций и медиа-реестр."""
    destination = ARCHIVE_DIR / import_key / "database.dump"

    selectors: list[str] = []
    for name in (*CONSTRUCTIONS_TABLES, *CONSTRUCTIONS_SEQUENCES):
        selectors += ["-t", name]

    _pg_dump(destination, selectors)
    return destination


def _link_or_copy(source: str, destination: str) -> None:
    """Жёсткая ссылка, а если нельзя (другая ФС) — обычное копирование.

    Медиа импорта неизменяемо (пишется один раз в свой каталог), поэтому
    снимок жёсткими ссылками мгновенный и не занимает место.
    """
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def archive_import_media(
    import_key: str,
    *,
    hardlink: bool = False,
) -> Path | None:
    """Копирует медиа (с превью) ТЕКУЩЕГО импорта в его архив.

    Сохраняем media того же импорта, что и `database.dump`: тогда архив
    самосогласован — restore кладёт media в
    storage/constructions/imports/<import_key>, к этой же базе.
    Если у импорта медиа нет — возвращаем None (шаг не критичен).

    ``hardlink=True`` — снимок ссылками (быстро, без занятого места);
    используется для предварительного снимка перед обновлением.
    """
    source = (
        PROJECT_DIR
        / "storage"
        / "constructions"
        / "imports"
        / import_key
    )
    destination = ARCHIVE_DIR / import_key / "media"

    if not source.exists():
        return None

    if destination.exists():
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        copy_function=_link_or_copy if hardlink else shutil.copy2,
    )

    return destination


def active_import_key() -> str | None:
    """Ключ текущего активного импорта конструкций (или None)."""
    from backend.services.data_service import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT import_key FROM construction_imports "
                "WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()

    return row[0] if row else None


def create_current_archive(reason: str = "manual") -> dict:
    """Создать архив ТЕКУЩЕЙ базы конструкций: дамп + медиа (превью) + source.

    Ручной снимок активного импорта, без запуска импорта. Ключ архива —
    ``<reason>-YYYYMMDD-HHMMSS`` (отдельно от ключей импорта).
    """
    active_key = active_import_key()

    if not active_key:
        raise RuntimeError("Нет активного импорта конструкций")

    safe_reason = re.sub(r"[^a-zA-Z0-9_-]", "", reason or "")[:32] or "manual"

    key = f"{safe_reason}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    destination = ARCHIVE_DIR / key

    if destination.exists():
        raise RuntimeError(f"Архив {key} уже существует")

    destination.mkdir(parents=True, exist_ok=True)

    # 1. source.xlsx — берём из архива активного импорта, если он там есть.
    source_xlsx = ARCHIVE_DIR / active_key / "source.xlsx"

    if source_xlsx.exists():
        shutil.copy2(source_xlsx, destination / "source.xlsx")

    # 2. Дамп текущей БД по таблицам конструкций.
    selectors: list[str] = []

    for name in (*CONSTRUCTIONS_TABLES, *CONSTRUCTIONS_SEQUENCES):
        selectors += ["-t", name]

    _pg_dump(destination / "database.dump", selectors)

    # 3. Медиа активного импорта (с превью large/card/thumb).
    media_src = (
        PROJECT_DIR
        / "storage"
        / "constructions"
        / "imports"
        / active_key
    )

    if media_src.exists():
        # Жёсткие ссылки: ручной снимок тоже мгновенный и без места.
        shutil.copytree(
            media_src,
            destination / "media",
            copy_function=_link_or_copy,
        )

    # Соблюдаем лимит архивов и при ручном создании.
    removed = cleanup_old_archives(ARCHIVE_DIR)

    return {
        "import_key": key,
        "active_import_key": active_key,
        "removed": removed,
    }


def cleanup_import_temp(import_key: str) -> None:
    import_root = IMPORT_DIR / import_key

    if import_root.exists():
        shutil.rmtree(import_root)


def cleanup_import_storage(import_key: str) -> None:
    storage_root = (
        PROJECT_DIR
        / "storage"
        / "constructions"
        / "imports"
        / import_key
    )

    if storage_root.exists():
        shutil.rmtree(storage_root)


def cleanup_old_archives(
    root: Path,
    *,
    keep: int = KEEP_ARCHIVES,
) -> list[str]:
    """Удаляет архивы сверх `keep`, оставляя самые свежие (по времени).

    Сортировка — по mtime (а не по имени): ручные архивы называются
    `manual-…` и по имени вставали бы не в хронологическом порядке.
    """
    if not root.exists():
        return []

    archives = sorted(
        (
            path
            for path in root.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        ),
        key=lambda path: (path.stat().st_mtime, path.name),
        reverse=True,
    )

    old_archives = archives[keep:]
    removed = []

    for archive in old_archives:
        shutil.rmtree(archive)
        removed.append(archive.name)

    return removed


def current_active_import_key() -> str | None:
    """Ключ текущего ACTIVE-импорта конструкций (состояние ДО обновления)."""
    from backend.services.data_service import get_connection

    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT import_key FROM construction_imports "
                "WHERE status = 'active' LIMIT 1"
            ).fetchone()
    except Exception:
        return None

    return row[0] if row else None


def snapshot_current_base(import_key: str, *, hardlink: bool = False) -> Path:
    """Снимок ТЕКУЩЕЙ базы ДО обновления — гарантированный откат.

    Делает самосогласованный архив текущего ACTIVE-импорта: дамп текущей БД
    + превью этого импорта. Восстанавливается обычным restore (media ляжет в
    storage/constructions/imports/<import_key>, и пути в дампе совпадут).

    Если архив этого импорта уже есть — это и есть тот же снимок, не плодим
    дубликаты.
    """
    archive_dir = ARCHIVE_DIR / import_key

    if (archive_dir / "database.dump").exists():
        return archive_dir

    archive_constructions_database(import_key)
    archive_import_media(import_key, hardlink=hardlink)

    return archive_dir


def run(*, commit: bool) -> None:
    source = find_source_file()

    print("=" * 70)
    print("ALBION CONSTRUCTION IMPORT PIPELINE")
    print("=" * 70)
    print(f"Источник: {source}")
    print(f"Режим:    {'COMMIT' if commit else 'DRY-RUN'}")

    print()
    print("===== STEP 1: EXCEL → JSON =====")
    run_stage("backend.importer.constructions_excel_to_json")

    print()
    print("===== STEP 2: JSON → SQLITE STAGING =====")
    run_stage("backend.importer.staging")

    import_key = find_import_key()

    print()
    print(f"Import key: {import_key}")

    if commit:
        # Снимок ТЕКУЩЕЙ базы (до изменений) — чтобы откат был всегда, даже
        # если прогон упадёт раньше шага архивации.
        print()
        print("===== STEP 0: SNAPSHOT CURRENT BASE (до обновления) =====")
        current_key = current_active_import_key()

        if current_key:
            snapshot = snapshot_current_base(current_key)
            print(f"Снимок текущей базы: {snapshot}")
        else:
            print("Текущего ACTIVE-импорта нет — снимок не требуется.")

        print()
        print("===== STEP 3: DOWNLOAD MEDIA =====")
        run_stage("backend.importer.construction_media_download")

        print()
        print("===== STEP 4: CREATE PREVIEWS =====")
        run_stage("backend.importer.construction_media_preview")
    else:
        # Dry-run: файлы не качаем — только проверяем доступность ссылок.
        print()
        print("===== STEP 3: CHECK MEDIA LINKS (dry-run, без скачивания) =====")
        run_stage("backend.importer.construction_media_check")

    print()
    print("===== STEP 5: SQLITE → POSTGRESQL =====")
    run_stage(
        "backend.importer.staging_to_postgres",
        env={
            "ALBION_IMPORT_DRY_RUN": "0" if commit else "1",
        },
    )

    # Мягкие проверки (адреса/координаты/цены). Не блокируют прогон:
    # падают только ошибки внутри самих проверок, и тогда их видно в логе.
    print()
    print("===== STEPS 6-8: CHECKS (адреса/координаты/цены) =====")
    run_stage(
        "backend.importer.constructions_checks",
        env={"ALBION_IMPORT_KEY": import_key},
    )

    old_active_import_key = None

    if commit:
        load_result = read_load_result(import_key)
        old_active_import_key = load_result.get("old_active_import_key")

        print()
        print(f"Предыдущий ACTIVE import: {old_active_import_key or 'нет'}")

    if not commit:
        print()
        print("===== DRY-RUN CLEANUP =====")
        cleanup_import_temp(import_key)

        storage_import = (
            PROJECT_DIR
            / "storage"
            / "constructions"
            / "imports"
            / import_key
        )

        if storage_import.exists():
            shutil.rmtree(storage_import)

        print(f"tmp/import/{import_key}: удалён")
        print(f"storage/.../{import_key}: удалён")

        print()
        print("=" * 70)
        print("DRY-RUN COMPLETE")
        print("PostgreSQL: НЕ ИЗМЕНЁН")
        print("Исходный Excel: НЕ ИЗМЕНЁН")
        print("Временные media: УДАЛЕНЫ")
        print("=" * 70)
        return

    print()
    print("===== STEP 9: ARCHIVE =====")

    archived_source = archive_source(source, import_key)
    print(f"source.xlsx:            {archived_source}")

    archived_db = archive_constructions_database(import_key)
    print(f"constructions database: {archived_db}")

    # Медиа ТЕКУЩЕГО импорта (с превью) — вместе с дампом БД.
    archived_media = archive_import_media(import_key)
    print(f"constructions media:    {archived_media or '(нет медиа)'}")

    if old_active_import_key:
        cleanup_import_storage(old_active_import_key)
        print(
            "storage/constructions/imports/"
            f"{old_active_import_key}: удалён"
        )

    print()
    print("===== STEP 10: CLEANUP =====")
    cleanup_import_temp(import_key)
    print(f"tmp/import/{import_key}: удалён")

    print()
    print("===== ARCHIVE RETENTION =====")
    removed_archives = cleanup_old_archives(ARCHIVE_DIR)

    if removed_archives:
        for archive_name in removed_archives:
            print(f"Удалён старый архив: {archive_name}")
    else:
        print("Архивов не больше 5, удаление не требуется.")

    print()
    print("=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Безопасный импорт конструкций: "
            "Excel → SQLite → media → PostgreSQL → archive"
        )
    )

    parser.add_argument(
        "--commit",
        action="store_true",
        help="выполнить реальный PostgreSQL COMMIT и архивирование",
    )

    args = parser.parse_args()
    run(commit=args.commit)


if __name__ == "__main__":
    main()
