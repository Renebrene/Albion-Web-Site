from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.importer.construction_media_downloader import (
    build_filename,
    build_variants,
    fetch_public_media,
    write_variants,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]

STAGING_ROOT = PROJECT_DIR / "tmp" / "import"
STORAGE_ROOT = (
    PROJECT_DIR
    / "storage"
    / "constructions"
    / "imports"
)


def open_staging_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise RuntimeError(f"Staging DB не найден: {path}")

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_latest_staging_db() -> Path:
    databases = list(STAGING_ROOT.glob("*/staging.sqlite"))

    if not databases:
        raise RuntimeError("Staging DB не найден")

    return max(
        databases,
        key=lambda path: path.stat().st_mtime,
    )


def get_import_key(staging_path: Path) -> str:
    return staging_path.parent.name


def get_variant_dirs(import_key: str) -> dict[str, dict[str, Path]]:
    root = STORAGE_ROOT / import_key

    return {
        media_type: {
            variant: root / media_type / variant
            for variant in ("large", "card", "thumb")
        }
        for media_type in ("photo", "map")
    }


def ensure_directories(import_key: str) -> None:
    variant_dirs = get_variant_dirs(import_key)

    for media_type in variant_dirs.values():
        for path in media_type.values():
            path.mkdir(parents=True, exist_ok=True)


def load_media_tasks(
    conn: sqlite3.Connection,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            s.id,
            s.surface_hash,
            c.address,
            s.side,
            s.photo_url,
            s.map_url
        FROM surfaces s
        JOIN constructions c
          ON c.id = s.construction_id
        WHERE s.is_active = 1
          AND s.surface_hash IS NOT NULL
        ORDER BY s.id
        """
    ).fetchall()


def process_test_photo(
    row: sqlite3.Row,
    import_key: str,
) -> dict[str, object]:
    surface_hash = row["surface_hash"]
    address = row["address"]
    side = row["side"]
    url = row["photo_url"]

    if not url:
        raise RuntimeError("У тестовой поверхности отсутствует photo_url")

    filename = build_filename(
        address,
        side,
        "photo",
    )

    data = fetch_public_media(url)

    image, variants, image_format = build_variants(data)

    extension = ".png" if image_format == "PNG" else ".jpg"
    actual_filename = Path(filename).with_suffix(extension).name

    paths = write_variants(
        import_key,
        "photo",
        actual_filename,
        variants,
    )

    mime_type = (
        "image/png"
        if image_format == "PNG"
        else "image/jpeg"
    )

    return {
        "surface_id": row["id"],
        "surface_hash": surface_hash,
        "media_type": "photo",
        "source": "download",
        "source_url": url,
        "original_name": actual_filename,
        "mime_type": mime_type,
        "file_size": len(data),
        "width": image.width,
        "height": image.height,
        "large_path": paths["large"],
        "card_path": paths["card"],
        "thumb_path": paths["thumb"],
    }


def main() -> None:
    staging_path = get_latest_staging_db()
    import_key = get_import_key(staging_path)

    print("=" * 70)
    print("CONSTRUCTION MEDIA STAGING")
    print("=" * 70)
    print(f"Staging DB: {staging_path}")
    print(f"Import key: {import_key}")

    conn = open_staging_db(staging_path)

    try:
        rows = load_media_tasks(conn)

        photo_count = sum(
            1 for row in rows
            if row["photo_url"]
        )
        map_count = sum(
            1 for row in rows
            if row["map_url"]
        )

        print()
        print("MEDIA SOURCE")
        print("-" * 70)
        print(f"Surfaces:       {len(rows)}")
        print(f"Photo URLs:     {photo_count}")
        print(f"Map URLs:       {map_count}")
        print(f"No media URLs:  {len(rows) - len(set(
            row["id"] for row in rows
            if row["photo_url"] or row["map_url"]
        ))}")

        ensure_directories(import_key)

        print()
        print("Storage:")
        print(STORAGE_ROOT / import_key)
        print()
        print("PostgreSQL: НЕ ИЗМЕНЁН")
        print("Downloads:  НЕ ЗАПУЩЕНЫ")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
