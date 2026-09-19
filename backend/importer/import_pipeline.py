from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from excel_to_json import convert
from json_to_postgres import main as import_to_postgres


PROJECT_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_DIR / "input"
TMP_DIR = PROJECT_DIR / "tmp"
ARCHIVE_DIR = PROJECT_DIR / "archive"
JSON_FILE = TMP_DIR / "import.json"


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


def archive_source(source: Path) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = ARCHIVE_DIR / f"{timestamp}_{source.name}"

    if destination.exists():
        raise RuntimeError(
            f"Архивный файл уже существует: {destination}"
        )

    shutil.move(str(source), str(destination))
    return destination


def cleanup_json() -> None:
    if JSON_FILE.exists():
        JSON_FILE.unlink()


def run(dry_run: bool = False) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    source = find_source_file()

    print("=" * 70)
    print("ALBION IMPORT PIPELINE")
    print("=" * 70)
    print(f"Источник: {source}")
    print(f"JSON:     {JSON_FILE}")
    print(f"Архив:    {ARCHIVE_DIR}")

    print()
    print("===== STEP 1: EXCEL → JSON =====")
    generated_json = convert()

    if generated_json != JSON_FILE:
        raise RuntimeError(
            f"Excel importer создал неожиданный JSON: {generated_json}"
        )

    if not JSON_FILE.exists():
        raise RuntimeError(
            f"После Excel → JSON файл не найден: {JSON_FILE}"
        )

    print()
    print(f"JSON создан: {JSON_FILE}")

    if dry_run:
        print()
        print("=" * 70)
        print("DRY-RUN COMPLETE")
        print("PostgreSQL не изменён")
        print("Excel не перемещён")
        print("JSON не удалён")
        print("=" * 70)
        return

    try:
        print()
        print("===== STEP 2: JSON → POSTGRESQL =====")
        import_to_postgres()

    except Exception:
        cleanup_json()

        print()
        print("=" * 70)
        print("IMPORT FAILED")
        print("Исходный Excel оставлен в input/")
        print("Временный JSON удалён")
        print("PostgreSQL-транзакция откатывается автоматически")
        print("=" * 70)
        raise

    print()
    print("===== STEP 3: ARCHIVE SOURCE =====")

    try:
        archived = archive_source(source)
    except Exception as exc:
        cleanup_json()

        print()
        print("=" * 70)
        print("DATABASE IMPORT SUCCEEDED")
        print("ARCHIVE FAILED")
        print(f"Исходный Excel всё ещё находится в input/: {source}")
        print(f"Причина: {exc}")
        print("Временный JSON удалён")
        print("=" * 70)
        raise

    print(f"Excel перемещён: {archived}")

    print()
    print("===== STEP 4: CLEANUP JSON =====")
    cleanup_json()
    print(f"JSON удалён: {JSON_FILE}")

    print()
    print("=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Безопасный импорт Albion: Excel → JSON → PostgreSQL → archive"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только Excel → JSON, без PostgreSQL, архивации и удаления JSON",
    )

    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
