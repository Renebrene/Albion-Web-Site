from pathlib import Path
import datetime


PROJECT_DIR = Path(__file__).resolve().parents[2]

ARCHIVE_ROOT = (
    PROJECT_DIR
    / "archive"
    / "constructions"
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
    result = []

    if not ARCHIVE_ROOT.exists():
        return result

    for item in sorted(
        ARCHIVE_ROOT.iterdir(),
        reverse=True,
    ):
        if not item.is_dir():
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


def restore_archive(import_key: str) -> dict:
    import os
    import subprocess

    archive_dir = ARCHIVE_ROOT / import_key
    dump_file = archive_dir / "database.dump"

    if not dump_file.exists():
        raise RuntimeError(
            f"Архив PostgreSQL не найден: {dump_file}"
        )

    env = os.environ.copy()

    cmd = [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "-h",
        env.get("ALBION_DB_HOST", "127.0.0.1"),
        "-p",
        env.get("ALBION_DB_PORT", "5432"),
        "-U",
        env.get("ALBION_DB_USER", "albion_app"),
        "-d",
        env.get("ALBION_DB_NAME", "albion"),
        str(dump_file),
    ]

    subprocess.run(
        cmd,
        env=env,
        check=True,
    )

    return {
        "success": True,
        "import_key": import_key,
        "message": "Архив восстановлен",
    }
