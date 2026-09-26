from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from pathlib import Path
from urllib.parse import urlparse

from urllib.parse import urlencode
from urllib.request import Request, urlopen
from PIL import Image

from backend.services.data_service import PROJECT_DIR, get_connection
from backend.services.media_service import (
    MAX_INPUT_FILE_SIZE,
    MAX_PIXELS,
    _build_static_variants,
    _detect_format,
    _open_image,
)


API_URL = "https://cloud-api.yandex.net/v1/disk/public/resources/download"

STORAGE_ROOT = (
    PROJECT_DIR
    / "storage"
    / "constructions"
    / "imports"
)

MEDIA_TYPES = {
    "photo": "photo",
    "map": "map",
}

WRITE_VARIANTS_LOCK = Lock()


def safe_filename(value: str) -> str:
    value = value.replace("/", " ").replace("\\", " ")

    value = re.sub(r'[:*?"<>|]', "", value)
    value = re.sub(r"\s+", " ", value).strip()

    if not value:
        value = "construction"

    return value[:180]


def build_filename(
    address: str | None,
    side: str | None,
    media_type: str,
) -> str:
    address_part = safe_filename(address or "construction")

    if media_type == "map":
        return f"{address_part}_карта"
    
    side_part = safe_filename(side or "")
    return (
        f"{address_part}_{side_part}"
        if side_part
        else address_part
    )


def get_import_storage_root(import_key: str) -> Path:
    return STORAGE_ROOT / import_key


def get_variant_dirs(import_key: str) -> dict[str, dict[str, Path]]:
    root = get_import_storage_root(import_key)

    return {
        media_type: {
            variant: root / media_type / variant
            for variant in ("large", "card", "thumb")
        }
        for media_type in MEDIA_TYPES
    }


def ensure_directories(import_key: str) -> None:
    variant_dirs = get_variant_dirs(import_key)

    for media_type in MEDIA_TYPES:
        for variant in ("large", "card", "thumb"):
            variant_dirs[media_type][variant].mkdir(
                parents=True,
                exist_ok=True,
            )


def get_active_import(conn) -> tuple[int, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, import_key
            FROM construction_imports
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cur.fetchone()

    if not row:
        raise RuntimeError(
            "В construction_imports нет активной версии импорта"
        )

    return int(row[0]), str(row[1])


def get_direct_link(public_url: str) -> str:
    query = urlencode({"public_key": public_url})
    request = Request(f"{API_URL}?{query}")

    with urlopen(request, timeout=30) as response:
        import json

        payload = json.loads(response.read().decode("utf-8"))

    href = payload.get("href")

    if not href:
        raise RuntimeError("Yandex API не вернул временную ссылку")

    return href


def download_bytes(href: str) -> bytes:
    request = Request(href)

    with urlopen(request, timeout=120) as response:
        content_length = response.headers.get("Content-Length")

        if content_length:
            size = int(content_length)
            if size > MAX_INPUT_FILE_SIZE:
                raise RuntimeError(
                    f"Файл слишком большой: {size} байт"
                )

        data = response.read()

    if len(data) > MAX_INPUT_FILE_SIZE:
        raise RuntimeError(
            f"Файл слишком большой: {len(data)} байт"
        )

    if not data:
        raise RuntimeError("Yandex вернул пустой файл")

    return data


def build_variants(
    data: bytes,
) -> tuple[
    Image.Image,
    dict[str, tuple[bytes, str, str]],
    str,
]:
    image = _open_image(data)

    if image.width * image.height > MAX_PIXELS:
        raise RuntimeError(
            "Изображение превышает допустимое количество пикселей"
        )

    image_format = _detect_format(image)

    preserve_png = image_format == "PNG"

    variants = _build_static_variants(
        image,
        preserve_png=preserve_png,
    )

    return image, variants, image_format


def write_variants(
    import_key: str,
    media_type: str,
    filename: str,
    variants: dict[str, tuple[bytes, str, str]],
) -> dict[str, str]:
    paths: dict[str, str] = {}
    variant_dirs = get_variant_dirs(import_key)

    stem = Path(filename).stem

    with WRITE_VARIANTS_LOCK:
        iteration = 1
        while True:
            suffix = "_" * iteration

            candidate_paths = {
                variant: variant_dirs[media_type][variant] / (
                    f"{stem}{suffix}{extension}"
                )
                for variant, (_data, _mime_type, extension) in variants.items()
            }

            if all(not path.exists() for path in candidate_paths.values()):
                break

            iteration += 1

        for variant, (data, _mime_type, extension) in variants.items():
            path = candidate_paths[variant]

            tmp_path = path.with_suffix(path.suffix + ".tmp")
            tmp_path.write_bytes(data)
            os.replace(tmp_path, path)

            paths[variant] = str(
                path.relative_to(PROJECT_DIR)
            )

    return paths


def already_imported(
    conn,
    import_id: int,
    media_type: str,
    surface_hash: str,
    original_url: str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id
            FROM construction_media
            WHERE import_id = %s
              AND surface_hash = %s
              AND media_type = %s
              AND original_url = %s
            LIMIT 1
            """,
            (
                import_id,
                surface_hash,
                media_type,
                original_url,
            ),
        )

        return cur.fetchone() is not None


def find_previous_media(
    conn,
    *,
    import_id: int,
    surface_hash: str,
    media_type: str,
) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                cm.id,
                cm.import_id,
                ci.import_key,
                cm.surface_hash,
                cm.media_type,
                cm.original_url,
                cm.original_name,
                cm.mime_type,
                cm.file_size,
                cm.width,
                cm.height,
                cm.large_path,
                cm.card_path,
                cm.thumb_path
            FROM construction_media cm
            JOIN construction_imports ci
              ON ci.id = cm.import_id
            WHERE cm.import_id <> %s
              AND cm.surface_hash = %s
              AND cm.media_type = %s
              AND (
                    cm.large_path IS NOT NULL
                 OR cm.card_path IS NOT NULL
                 OR cm.thumb_path IS NOT NULL
              )
            ORDER BY cm.import_id DESC, cm.id DESC
            LIMIT 1
            """,
            (
                import_id,
                surface_hash,
                media_type,
            ),
        )

        row = cur.fetchone()

    if not row:
        return None

    columns = [
        "id",
        "import_id",
        "import_key",
        "surface_hash",
        "media_type",
        "original_url",
        "original_name",
        "mime_type",
        "file_size",
        "width",
        "height",
        "large_path",
        "card_path",
        "thumb_path",
    ]

    return dict(zip(columns, row))


def copy_previous_variants(
    *,
    previous_media: dict,
    import_key: str,
    media_type: str,
) -> dict[str, str]:
    variant_dirs = get_variant_dirs(import_key)
    paths: dict[str, str] = {}

    for variant in ("large", "card", "thumb"):
        previous_path = previous_media.get(f"{variant}_path")

        if not previous_path:
            continue

        source = PROJECT_DIR / previous_path

        if not source.is_file():
            raise RuntimeError(
                f"Не найден старый файл {variant}: {source}"
            )

        destination = variant_dirs[media_type][variant] / (
            source.name
        )

        tmp_path = destination.with_suffix(
            destination.suffix + ".tmp"
        )

        import shutil

        shutil.copy2(source, tmp_path)
        os.replace(tmp_path, destination)

        paths[variant] = str(
            destination.relative_to(PROJECT_DIR)
        )

    if not paths:
        raise RuntimeError(
            "У предыдущей версии нет доступных файлов"
        )

    return paths


def save_media_record(
    conn,
    *,
    import_id: int,
    surface_id: int,
    surface_hash: str,
    media_type: str,
    original_url: str | None,
    original_name: str | None,
    mime_type: str | None,
    file_size: int | None,
    width: int | None,
    height: int | None,
    paths: dict[str, str],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO construction_media (
                import_id,
                surface_id,
                surface_hash,
                media_type,
                original_url,
                original_name,
                mime_type,
                file_size,
                width,
                height,
                large_path,
                card_path,
                thumb_path
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (import_id, surface_hash, media_type)
            DO UPDATE SET
                surface_id = EXCLUDED.surface_id,
                original_url = EXCLUDED.original_url,
                original_name = EXCLUDED.original_name,
                mime_type = EXCLUDED.mime_type,
                file_size = EXCLUDED.file_size,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                large_path = EXCLUDED.large_path,
                card_path = EXCLUDED.card_path,
                thumb_path = EXCLUDED.thumb_path,
                updated_at = NOW()
            """,
            (
                import_id,
                surface_id,
                surface_hash,
                media_type,
                original_url,
                original_name,
                mime_type,
                file_size,
                width,
                height,
                paths["large"],
                paths["card"],
                paths["thumb"],
            ),
        )


def process_surface(
    conn,
    row,
    import_id: int,
    import_key: str,
    media_type: str,
    url: str,
    dry_run: bool,
) -> str:
    surface_id = row["id"]
    surface_hash = row["surface_hash"]
    address = row["address"]
    side = row["side"]

    filename = build_filename(
        address,
        side,
        media_type,
    )

    if already_imported(
        conn,
        import_id,
        media_type,
        surface_hash,
        url,
    ):
        return f"SKIP {media_type}: {filename}"

    if dry_run:
        return f"DRY {media_type}: {filename}"

    try:
        href = get_direct_link(url)
        data = download_bytes(href)

        image, variants, image_format = build_variants(data)

        extension = ".png" if image_format == "PNG" else ".jpg"

        actual_filename = Path(filename).with_suffix(extension).name

        paths = write_variants(
            import_key,
            media_type,
            actual_filename,
            variants,
        )

        mime_type = (
            "image/png"
            if image_format == "PNG"
            else "image/jpeg"
        )

        save_media_record(
            conn,
            import_id=import_id,
            surface_id=surface_id,
            surface_hash=surface_hash,
            media_type=media_type,
            original_url=url,
            original_name=actual_filename,
            mime_type=mime_type,
            file_size=len(data),
            width=image.width,
            height=image.height,
            paths=paths,
        )

        return (
            f"OK {media_type}: "
            f"{actual_filename} "
            f"{image.width}x{image.height}"
        )

    except Exception as download_error:
        previous_media = find_previous_media(
            conn,
            import_id=import_id,
            surface_hash=surface_hash,
            media_type=media_type,
        )

        if not previous_media:
            raise

        paths = copy_previous_variants(
            previous_media=previous_media,
            import_key=import_key,
            media_type=media_type,
        )

        save_media_record(
            conn,
            import_id=import_id,
            surface_id=surface_id,
            surface_hash=surface_hash,
            media_type=media_type,
            original_url=previous_media["original_url"],
            original_name=previous_media["original_name"],
            mime_type=previous_media["mime_type"],
            file_size=previous_media["file_size"],
            width=previous_media["width"],
            height=previous_media["height"],
            paths=paths,
        )

        return (
            f"FALLBACK {media_type}: "
            f"{previous_media['original_name']} "
            f"(download error: {download_error})"
        )


def load_surfaces(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.id,
                s.surface_hash,
                s.photo,
                s.map,
                c.address,
                s.side
            FROM surfaces s
            JOIN constructions c
              ON c.id = s.construction_id
            WHERE s.is_active = TRUE
              AND s.surface_hash IS NOT NULL
              AND (
                    NULLIF(TRIM(s.photo), '') IS NOT NULL
                 OR NULLIF(TRIM(s.map), '') IS NOT NULL
              )
            ORDER BY s.id
            """
        )

        columns = [desc.name for desc in cur.description]

        return [
            dict(zip(columns, row))
            for row in cur.fetchall()
        ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Импорт фото и карт конструкций из Yandex в construction_media"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать план, ничего не скачивать",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="количество параллельных загрузок",
    )
    args = parser.parse_args()

    stats = {
        "surfaces": 0,
        "processed": 0,
        "skipped": 0,
        "errors": 0,
    }

    with get_connection() as conn:
        import_id, import_key = get_active_import(conn)

        if not args.dry_run:
            ensure_directories(import_key)

        surfaces = load_surfaces(conn)
        stats["surfaces"] = len(surfaces)

        print(f"[*] Import ID:  {import_id}")
        print(f"[*] Import key: {import_key}")
        print(f"[*] Поверхностей: {len(surfaces)}")
        print(
            f"[*] Storage: "
            f"{get_import_storage_root(import_key)}"
        )

        tasks = []

        for index, row in enumerate(surfaces, 1):
            for media_type, column in (
                ("photo", "photo"),
                ("map", "map"),
            ):
                value = row.get(column)

                if value and str(value).strip().startswith("http"):
                    tasks.append(
                        (
                            index,
                            row,
                            media_type,
                            str(value).strip(),
                        )
                    )

        def process_task(task):
            index, row, media_type, url = task

            with get_connection() as worker_conn:
                try:
                    result = process_surface(
                        worker_conn,
                        row,
                        import_id,
                        import_key,
                        media_type,
                        url,
                        args.dry_run,
                    )
                    worker_conn.commit()

                    return (
                        index,
                        row["id"],
                        media_type,
                        result,
                        None,
                    )

                except Exception as exc:
                    worker_conn.rollback()

                    return (
                        index,
                        row["id"],
                        media_type,
                        None,
                        exc,
                    )

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(process_task, task)
                for task in tasks
            ]

            for future in as_completed(futures):
                index, surface_id, media_type, result, error = future.result()

                if error is not None:
                    stats["errors"] += 1
                    print(
                        f"[{index}/{len(surfaces)}] "
                        f"ERROR {media_type} "
                        f"surface={surface_id}: {error}"
                    )
                    continue

                print(
                    f"[{index}/{len(surfaces)}] "
                    f"{surface_id} {result}"
                )

                if result.startswith("SKIP"):
                    stats["skipped"] += 1
                else:
                    stats["processed"] += 1

        if not args.dry_run:
            conn.commit()

    print()
    print("=== ИТОГ ===")
    print(f"Поверхностей: {stats['surfaces']}")
    print(f"Обработано:   {stats['processed']}")
    print(f"Пропущено:    {stats['skipped']}")
    print(f"Ошибок:       {stats['errors']}")


if __name__ == "__main__":
    main()
