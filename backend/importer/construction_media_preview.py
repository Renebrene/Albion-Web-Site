from __future__ import annotations

import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from backend.services.media_service import (
    MAX_PIXELS,
    _build_static_variants,
    _detect_format,
    _open_image,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
STAGING_ROOT = PROJECT_DIR / "tmp" / "import"
STORAGE_ROOT = PROJECT_DIR / "storage" / "constructions" / "imports"

VARIANT_NAMES = ("large", "card", "thumb")
WORKERS = max(1, (os.cpu_count() or 1) // 2)


def get_latest_staging_db() -> Path:
    candidates = sorted(
        STAGING_ROOT.glob("*/staging.sqlite"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError("staging.sqlite не найден")
    return candidates[0]


def load_media_tasks(staging_path: Path) -> list[dict]:
    conn = sqlite3.connect(staging_path)

    try:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.surface_hash,
                c.address,
                s.side
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            WHERE s.is_active = 1
              AND s.surface_hash IS NOT NULL
            ORDER BY s.id
            """
        ).fetchall()
    finally:
        conn.close()

    tasks = []
    downloads_root = staging_path.parent / "downloads"

    for surface_id, surface_hash, address, side in rows:
        for media_type in ("photo", "map"):
            source_dir = downloads_root / media_type / surface_hash

            for source_path in sorted(source_dir.glob("*.source")):
                tasks.append(
                    {
                        "surface_id": surface_id,
                        "surface_hash": surface_hash,
                        "address": address,
                        "side": side,
                        "media_type": media_type,
                        "source_path": str(source_path),
                    }
                )

    return tasks


def load_preview_bytes(source_path: Path) -> bytes:
    data = source_path.read_bytes()

    if data.startswith(b"PK\x03\x04"):
        with ZipFile(source_path) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and "карта" in Path(info.filename).name.lower()
                and "фото+карта" not in Path(info.filename).name.lower()
            ]

            if len(candidates) != 1:
                raise RuntimeError(
                    f"ZIP: найдено карт-кандидатов: {len(candidates)}"
                )

            return archive.read(candidates[0])

    return data


def build_preview(task: dict) -> dict:
    source_path = Path(task["source_path"])

    data = load_preview_bytes(source_path)

    image = _open_image(data)

    if image.width * image.height > MAX_PIXELS:
        raise RuntimeError(
            f"Слишком много пикселей: "
            f"{image.width}x{image.height}"
        )

    image_format = _detect_format(image)

    if image_format == "GIF" and getattr(image, "is_animated", False):
        raise RuntimeError(
            "Анимированный GIF не поддерживается для construction preview"
        )

    preserve_png = image_format == "PNG"

    variants = _build_static_variants(
        image,
        preserve_png=preserve_png,
    )

    output_root = (
        STORAGE_ROOT
        / task["import_key"]
        / task["media_type"]
    )

    for variant in VARIANT_NAMES:
        output_root.joinpath(variant).mkdir(
            parents=True,
            exist_ok=True,
        )

    stem = f'{task["surface_hash"]}_{task["media_type"]}'
    extension = variants["large"][2]

    paths = {}

    for variant in VARIANT_NAMES:
        data_bytes, _, _ = variants[variant]
        destination = (
            output_root
            / variant
            / f"{stem}{extension}"
        )

        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        temporary.write_bytes(data_bytes)
        os.replace(temporary, destination)

        paths[variant] = str(
            destination.relative_to(PROJECT_DIR)
        )

    return {
        **task,
        "status": "OK",
        "format": image_format,
        "width": image.width,
        "height": image.height,
        "large_path": paths["large"],
        "card_path": paths["card"],
        "thumb_path": paths["thumb"],
    }


def worker(task: dict) -> dict:
    try:
        return build_preview(task)
    except Exception as exc:
        return {
            **task,
            "status": "ERROR",
            "error": str(exc),
        }


def main() -> None:
    staging_path = get_latest_staging_db()
    import_key = staging_path.parent.name

    tasks = load_media_tasks(staging_path)

    for task in tasks:
        task["import_key"] = import_key

    print("=" * 70)
    print("CONSTRUCTION MEDIA PREVIEW")
    print("=" * 70)
    print(f"Staging DB: {staging_path}")
    print(f"Import key: {import_key}")
    print(f"Tasks:      {len(tasks)}")
    print(f"Workers:    {WORKERS}")
    print()
    print("Preview generation started...")

    ok = 0
    errors = []

    with ProcessPoolExecutor(max_workers=WORKERS) as executor:
        futures = [
            executor.submit(worker, task)
            for task in tasks
        ]

        for future in as_completed(futures):
            result = future.result()

            if result["status"] == "OK":
                ok += 1
            else:
                errors.append(result)

    print()
    print("PREVIEW RESULT")
    print("-" * 70)
    print(f"Tasks:  {len(tasks)}")
    print(f"OK:     {ok}")
    print(f"ERROR:  {len(errors)}")
    print()
    print("PostgreSQL: НЕ ИЗМЕНЁН")


if __name__ == "__main__":
    main()
