from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import logging
import math
import os
from pathlib import Path
import shutil
from subprocess import CompletedProcess, TimeoutExpired, run
from uuid import uuid4
import warnings
import psutil

import pillow_heif
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from backend.services import albion_storage
from backend.services import storage_backend as storage_backend_service
from backend.services.data_service import PROJECT_DIR, get_connection


logger = logging.getLogger(__name__)


pillow_heif.register_heif_opener()

def _normalize_category_ids(category_id: list[int] | None) -> list[int]:
    category_ids = list(dict.fromkeys(category_id or [1]))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM media_categories WHERE id = ANY(%s)",
                (category_ids,),
            )

            if cur.fetchone()[0] != len(category_ids):
                raise MediaValidationError("Одна или несколько категорий не найдены")
    return category_ids


STORAGE_ROOT = PROJECT_DIR / "storage"

MAX_INPUT_FILE_SIZE = 40 * 1024 * 1024
MAX_DOCUMENT_FILE_SIZE = 40 * 1024 * 1024
VIDEO_MAX_INPUT_FILE_SIZE = 100 * 1024 * 1024
VIDEO_MAX_SIDE = 800
VIDEO_PRESET = "medium"
VIDEO_CRF = 23
VIDEO_AUDIO_BITRATE = "128k"
VIDEO_PREVIEW_QUALITY = 82
VIDEO_MAX_DURATION_SECONDS = 600
VIDEO_MAX_SOURCE_SIDE = 8192
VIDEO_MAX_SOURCE_PIXELS = 50_000_000
VIDEO_PROBE_TIMEOUT_SECONDS = 10
VIDEO_ENCODE_TIMEOUT_SECONDS = 120
VIDEO_PREVIEW_TIMEOUT_SECONDS = 30
MAX_PIXELS = 50_000_000

VARIANT_SIZES = {
    "large": 2400,
    "card": 1000,
    # Превью = реальная ширина карточки ×2 (retina): список/попап ~320px,
    # медиатека ~300px. 400px не хватало на retina, 1000px — избыточно.
    "thumb": 640,
}

SUPPORTED_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
    "HEIC",
    "HEIF",
    "TIFF",
    "BMP",
    "PSD",
    "GIF",
    "MPO",
}

# Документы сохраняются как есть, без конвертации.
DOCUMENT_MIME_TYPES = {
    ".pdf": "application/pdf",

    # Word / текст
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
    ".odt": "application/vnd.oasis.opendocument.text",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".md": "text/markdown",

    # Таблицы
    ".xls": "application/vnd.ms-excel",
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
    ),
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".csv": "text/csv",

    # Презентации
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": (
        "application/vnd.openxmlformats-officedocument"
        ".presentationml.presentation"
    ),
    ".odp": "application/vnd.oasis.opendocument.presentation",
}


class MediaValidationError(ValueError):
    pass


def is_document_name(original_name: str | None) -> bool:
    extension = Path(original_name or "").suffix.lower()

    return extension in DOCUMENT_MIME_TYPES


def _validate_image_header(image: Image.Image) -> None:
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise MediaValidationError(
            "Изображение содержит слишком большое количество пикселей"
        )

    if (image.format or "").upper() != "GIF" or not getattr(image, "is_animated", False):
        return

    frame_limit = int(os.getenv("ALBION_MEDIA_GIF_MAX_FRAMES", "100"))
    total_pixels_limit = int(
        os.getenv("ALBION_MEDIA_GIF_MAX_TOTAL_PIXELS", str(MAX_PIXELS * 2))
    )
    duration_limit_ms = int(os.getenv("ALBION_MEDIA_GIF_MAX_DURATION_MS", "60000"))

    if frame_limit < 1 or total_pixels_limit < 1 or duration_limit_ms < 1:
        raise MediaValidationError("Некорректные лимиты обработки GIF")

    total_duration_ms = 0
    total_frame_pixels = 0
    frame_count = 0
    try:
        # Do not ask Pillow for n_frames: some plugins scan the complete file
        # to compute it. Stop seeking as soon as the configured frame cap is hit.
        while frame_count <= frame_limit:
            try:
                image.seek(frame_count)
            except EOFError:
                break
            frame_count += 1
            frame_width, frame_height = image.size
            frame_pixels = frame_width * frame_height
            if frame_pixels > MAX_PIXELS:
                raise MediaValidationError(
                    "Кадр GIF содержит слишком много пикселей"
                )
            total_frame_pixels += frame_pixels
            if total_frame_pixels > total_pixels_limit:
                raise MediaValidationError("GIF превышает лимит суммарных пикселей")
            duration_ms = int(image.info.get("duration") or 0)
            if duration_ms < 0:
                raise ValueError("negative frame duration")
            total_duration_ms += duration_ms
            if total_duration_ms > duration_limit_ms:
                raise MediaValidationError("GIF слишком длинный")
        if frame_count > frame_limit:
            raise MediaValidationError("GIF содержит слишком много кадров")
    except MediaValidationError:
        raise
    except (OSError, ValueError) as exc:
        raise MediaValidationError("Не удалось проверить кадры GIF") from exc

    image.seek(0)


def _open_image(file_bytes: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(file_bytes))
            # Check dimensions before verify/load so oversized compressed images
            # never get fully decoded into memory.
            _validate_image_header(image)
            image.verify()

            image = Image.open(BytesIO(file_bytes))
            _validate_image_header(image)
            image.load()

        return image

    except Image.DecompressionBombError as exc:
        raise MediaValidationError(
            "Изображение содержит слишком большое количество пикселей"
        ) from exc
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise MediaValidationError(
            "Изображение содержит слишком большое количество пикселей"
        ) from exc
    except MediaValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise MediaValidationError(
            "Файл не является корректным изображением"
        ) from exc


def _detect_format(image: Image.Image) -> str:
    image_format = (image.format or "").upper()

    if image_format == "JPG":
        image_format = "JPEG"

    if image_format not in SUPPORTED_FORMATS:
        allowed = ", ".join(sorted(SUPPORTED_FORMATS))
        raise MediaValidationError(
            f"Формат изображения не поддерживается. "
            f"Разрешены: {allowed}"
        )

    return image_format


def _is_animated_gif(image: Image.Image, image_format: str) -> bool:
    return (
        image_format == "GIF"
        and bool(getattr(image, "is_animated", False))
        and getattr(image, "n_frames", 1) > 1
    )


def _convert_cmyk_to_srgb(image: Image.Image) -> Image.Image:
    if image.mode != "CMYK":
        return image

    icc_profile = image.info.get("icc_profile")

    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(
                BytesIO(icc_profile)
            )
            srgb_profile = ImageCms.createProfile("sRGB")

            return ImageCms.profileToProfile(
                image,
                source_profile,
                srgb_profile,
                outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass

    return image.convert("RGB")


def _prepare_static_image(
    image: Image.Image,
    *,
    preserve_alpha: bool = False,
) -> Image.Image:
    image = ImageOps.exif_transpose(image)

    if image.mode == "CMYK":
        return _convert_cmyk_to_srgb(image)

    if preserve_alpha:
        if image.mode in ("RGBA", "LA"):
            return image.convert("RGBA")

        if image.mode == "P" and "transparency" in image.info:
            return image.convert("RGBA")

    if image.mode in ("RGBA", "LA"):
        background = Image.new("RGB", image.size, "white")
        alpha = image.getchannel("A")
        background.paste(image.convert("RGB"), mask=alpha)
        return background

    if image.mode == "P":
        if "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(
                rgba.convert("RGB"),
                mask=rgba.getchannel("A"),
            )
            return background

        return image.convert("RGB")

    if image.mode != "RGB":
        return image.convert("RGB")

    return image


def _resize_for_variant(
    image: Image.Image,
    max_side: int,
) -> Image.Image:
    width, height = image.size
    longest_side = max(width, height)

    if longest_side <= max_side:
        return image.copy()

    scale = max_side / longest_side
    new_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )

    return image.resize(new_size, Image.Resampling.LANCZOS)


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    output = BytesIO()

    image.save(
        output,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )

    return output.getvalue()


def _encode_webp(image: Image.Image, quality: int = 80) -> bytes:
    """WebP для карточных вариантов.

    Замер на 100 реальных фото: WebP q78–80 даёт ~27–29% меньше байт,
    чем JPEG q82, при SSIM не хуже. Large оставляем JPEG — он нужен
    для печати/экспорта и совместимости.
    """
    output = BytesIO()

    image.save(
        output,
        format="WEBP",
        quality=quality,
        method=6,
    )

    return output.getvalue()


def _encode_png(image: Image.Image) -> bytes:
    output = BytesIO()

    image.save(
        output,
        format="PNG",
        optimize=True,
    )

    return output.getvalue()


def _encode_gif(image: Image.Image) -> bytes:
    output = BytesIO()

    image.save(
        output,
        format="GIF",
    )

    return output.getvalue()


def _build_static_variants(
    image: Image.Image,
    preserve_png: bool,
) -> dict[str, tuple[bytes, str, str]]:
    prepared = _prepare_static_image(
        image,
        preserve_alpha=preserve_png,
    )

    result: dict[str, tuple[bytes, str, str]] = {}

    for variant, max_side in VARIANT_SIZES.items():
        resized = _resize_for_variant(prepared, max_side)

        if preserve_png:
            data = _encode_png(resized)
            mime_type = "image/png"
            extension = ".png"
        elif variant == "large":
            data = _encode_jpeg(resized, 85)
            mime_type = "image/jpeg"
            extension = ".jpg"
        else:
            # Оба карточных варианта — WebP q80: замер показал SSIM ~0.96
            # при экономии ~29% против JPEG q82.
            data = _encode_webp(resized, 80)
            mime_type = "image/webp"
            extension = ".webp"

        result[variant] = (
            data,
            mime_type,
            extension,
        )

    return result


def _build_gif(
    image: Image.Image,
) -> tuple[bytes, str, str]:
    if getattr(image, "is_animated", False):
        output = BytesIO()

        image.save(
            output,
            format="GIF",
            save_all=True,
        )

        return output.getvalue(), "image/gif", ".gif"

    output = BytesIO()
    image.save(output, format="GIF")

    return output.getvalue(), "image/gif", ".gif"


def _record_url(record: dict) -> str:
    return storage_backend_service.public_url(record)


def _insert_media(
    conn,
    *,
    media_uuid,
    original_name: str,
    storage_path: Path,
    mime_type: str,
    file_size: int,
    width: int,
    height: int,
    alt: str | None,
    title: str | None,
    category_id: list[int] | None,
    preview_path: Path | None = None,
    storage_backend: str = "local",
    external_url: str | None = None,
    external_key: str | None = None,
) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO media (
                uuid,
                original_name,
                storage_path,
                mime_type,
                file_size,
                width,
                height,
                alt,
                title,
                category_id,
                preview_path,
                storage_backend,
                external_url,
                external_key
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id, uuid, original_name, storage_path,
                      mime_type, file_size, width, height,
                      alt, title, category_id, preview_path, created_at, updated_at,
                      storage_backend, external_url, external_key
            """,
            (
                media_uuid,
                original_name,
                str(storage_path),
                mime_type,
                file_size,
                width,
                height,
                alt,
                title,
                category_id,
                str(preview_path) if preview_path else None,
                storage_backend,
                external_url,
                external_key,
            ),
        )

        row = cur.fetchone()

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "id": row[0],
        "uuid": str(row[1]),
        "original_name": row[2],
        "storage_path": row[3],
        "mime_type": row[4],
        "file_size": row[5],
        "width": row[6],
        "height": row[7],
        "alt": row[8],
        "title": row[9],
        "category_id": row[10],
        "preview_path": row[11],
        "created_at": row[12].isoformat() if row[12] else None,
        "updated_at": row[13].isoformat() if row[13] else None,
        "storage_backend": row[14] or "local",
        "external_url": row[15],
        "external_key": row[16],
        "url": _record_url(
            {"storage_path": row[3], "external_url": row[15]}
        ),
    }


def _insert_variant(
    conn,
    *,
    media_id: int,
    variant: str,
    storage_path: Path,
    mime_type: str,
    file_size: int,
    width: int,
    height: int,
    storage_backend: str = "local",
    external_url: str | None = None,
    external_key: str | None = None,
) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO media_variants (
                media_id,
                variant,
                storage_path,
                mime_type,
                file_size,
                width,
                height,
                storage_backend,
                external_url,
                external_key
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, storage_backend, external_url, external_key
            """,
            (
                media_id,
                variant,
                str(storage_path),
                mime_type,
                file_size,
                width,
                height,
                storage_backend,
                external_url,
                external_key,
            ),
        )

        row = cur.fetchone()

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "id": row[0],
        "variant": variant,
        "storage_path": str(storage_path),
        "mime_type": mime_type,
        "file_size": file_size,
        "width": width,
        "height": height,
        "storage_backend": row[1] or "local",
        "external_url": row[2],
        "external_key": row[3],
        "url": _record_url(
            {"storage_path": str(storage_path), "external_url": row[2]}
        ),
    }


def _safe_error(exc: Exception) -> str:
    return str(exc).strip()[:300] or exc.__class__.__name__


def _remote_upload_objects(media_result: dict, objects: list[dict]) -> None:
    """Дублирует созданные файлы в Albion и обновляет строки БД.

    Никогда не бросает: при ошибке файл остаётся локальным, а ответ
    загрузки — успешным.
    """
    if not objects:
        return

    try:
        if not storage_backend_service.should_store_remote():
            return
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Albion storage: не удалось определить режим хранения: %s",
            _safe_error(exc),
        )
        return

    try:
        uploaded = storage_backend_service.upload_saved_objects(
            [
                (obj["path"], obj["relative_path"], obj["kind"])
                for obj in objects
            ]
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Albion storage: загрузка не выполнена: %s",
            _safe_error(exc),
        )
        return

    by_relative = {
        str(item.get("storage_path")): item
        for item in uploaded
        if isinstance(item, dict)
    }

    updates: list[tuple[dict, dict]] = []

    for obj in objects:
        remote = by_relative.get(str(obj["relative_path"]))

        if not remote or not remote.get("external_url"):
            continue

        updates.append((obj, remote))

    if not updates:
        return

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for obj, remote in updates:
                    if obj["kind"] == "media":
                        cur.execute(
                            """
                            UPDATE media
                            SET storage_backend = 'albion',
                                external_url = %s,
                                external_key = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                remote["external_url"],
                                remote.get("external_key"),
                                obj.get("id"),
                            ),
                        )
                    elif obj["kind"] == "variant":
                        cur.execute(
                            """
                            UPDATE media_variants
                            SET storage_backend = 'albion',
                                external_url = %s,
                                external_key = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                remote["external_url"],
                                remote.get("external_key"),
                                obj.get("id"),
                            ),
                        )
                    # У preview видео нет отдельной строки в БД: файл
                    # загружается, но ключ хранить негде.
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Albion storage: не удалось сохранить внешние ссылки: %s",
            _safe_error(exc),
        )
        return

    # Ответ обновляем только после успешной записи в БД.
    for obj, remote in updates:
        if obj["kind"] == "media":
            media_result["storage_backend"] = "albion"
            media_result["external_url"] = remote["external_url"]
            media_result["external_key"] = remote.get("external_key")
            media_result["url"] = remote["external_url"]
        elif obj["kind"] == "variant":
            for variant in media_result.get("variants") or []:
                if variant.get("id") == obj.get("id"):
                    variant["storage_backend"] = "albion"
                    variant["external_url"] = remote["external_url"]
                    variant["external_key"] = remote.get("external_key")
                    variant["url"] = remote["external_url"]
                    break
        elif obj["kind"] == "preview":
            media_result["preview_url"] = remote["external_url"]


def _media_filter_sql(
    *,
    category_id: int | None = None,
    category_ids: list[int] | None = None,
    search: str | None = None,
    media_type: str = "all",
    date_from=None,
    date_to=None,
) -> tuple[str, list]:
    """Build parameterized filters shared by media rows and exact count."""
    clauses = []
    params = []
    if category_ids:
        clauses.append("m.category_id && %s::bigint[]")
        params.append(category_ids)
    elif category_id is not None:
        clauses.append("%s::bigint = ANY(m.category_id)")
        params.append(category_id)
    if search and search.strip():
        clauses.append(
            "(m.original_name ILIKE %s OR COALESCE(m.alt, '') ILIKE %s "
            "OR COALESCE(m.title, '') ILIKE %s)"
        )
        term = f"%{search.strip()}%"
        params.extend((term, term, term))
    if media_type == "photo":
        clauses.append("m.mime_type LIKE 'image/%'")
    elif media_type == "video":
        clauses.append("m.mime_type LIKE 'video/%'")
    elif media_type == "document":
        clauses.append("m.mime_type NOT LIKE 'image/%' AND m.mime_type NOT LIKE 'video/%'")
    if date_from is not None:
        clauses.append("m.created_at >= %s")
        params.append(date_from)
    if date_to is not None:
        from datetime import timedelta
        clauses.append("m.created_at < %s")
        params.append(date_to + timedelta(days=1))
    return ("WHERE " + " AND ".join(clauses) if clauses else "", params)


def list_media(
    limit: int = 30,
    offset: int = 0,
    category_id: int | None = None,
    *,
    category_ids: list[int] | None = None,
    search: str | None = None,
    media_type: str = "all",
    date_from=None,
    date_to=None,
    include_total: bool = False,
) -> list[dict] | tuple[list[dict], int]:
    where, filter_params = _media_filter_sql(
        category_id=category_id,
        category_ids=category_ids,
        search=search,
        media_type=media_type,
        date_from=date_from,
        date_to=date_to,
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            total = None
            if include_total:
                cur.execute(f"SELECT COUNT(*) FROM media m {where}", tuple(filter_params))
                total = cur.fetchone()[0]

            cur.execute(
                f"""
                SELECT
                    m.id,
                    m.uuid,
                    m.original_name,
                    m.category_id,
                    COALESCE(
                        ARRAY(
                            SELECT mc.name
                            FROM media_categories mc
                            WHERE mc.id = ANY(m.category_id)
                            ORDER BY mc.sort_order, mc.name, mc.id
                        ),
                        ARRAY[]::TEXT[]
                    ) AS category_names,
                    m.storage_path,
                    m.mime_type,
                    m.file_size,
                    m.width,
                    m.height,
                    m.alt,
                    m.title,
                    m.preview_path,
                    m.created_at,
                    m.updated_at,
                    EXISTS (
                        SELECT 1
                        FROM news_media nm
                        WHERE nm.media_id = m.id
                    ) AS used_in_news,
                    EXISTS (
                        SELECT 1
                        FROM page_block_media pbm
                        WHERE pbm.media_id = m.id
                    ) AS used_in_pages,
                    EXISTS (
                        SELECT 1
                        FROM home_geo_attraction_photos g
                        WHERE g.media_id = m.id
                    ) AS used_in_geo,
                    COALESCE((
                        SELECT array_agg(DISTINCT p.slug)
                        FROM page_block_media pbm
                        JOIN page_blocks b ON b.id = pbm.block_id
                        JOIN pages p ON p.id = b.page_id
                        WHERE pbm.media_id = m.id
                    ), ARRAY[]::text[]) AS page_slugs,
                    m.storage_backend,
                    m.external_url,
                    m.external_key
                FROM media m
                {where}
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT %s OFFSET %s
                """,
                (*filter_params, limit, offset),
            )

            rows = cur.fetchall()
            result = []

            for row in rows:
                media_id = row[0]

                cur.execute(
                    """
                    SELECT
                        id,
                        variant,
                        storage_path,
                        mime_type,
                        file_size,
                        width,
                        height,
                        storage_backend,
                        external_url,
                        external_key
                    FROM media_variants
                    WHERE media_id = %s
                    ORDER BY
                        CASE variant
                            WHEN 'large' THEN 1
                            WHEN 'card' THEN 2
                            WHEN 'thumb' THEN 3
                            ELSE 4
                        END
                    """,
                    (media_id,),
                )

                variants = [
                    {
                        "id": variant_row[0],
                        "variant": variant_row[1],
                        "storage_path": variant_row[2],
                        "mime_type": variant_row[3],
                        "file_size": variant_row[4],
                        "width": variant_row[5],
                        "height": variant_row[6],
                        "storage_backend": variant_row[7] or "local",
                        "external_url": variant_row[8],
                        "external_key": variant_row[9],
                        "url": _record_url(
                            {
                                "storage_path": variant_row[2],
                                "external_url": variant_row[8],
                            }
                        ),
                    }
                    for variant_row in cur.fetchall()
                ]

                result.append(
                    {
                        "id": media_id,
                        "uuid": str(row[1]),
                        "original_name": row[2],
                        "category_id": row[3],
                        "category_names": row[4],
                        "category_name": ", ".join(row[4]) if row[4] else "Разное",
                        "storage_path": row[5],
                        "mime_type": row[6],
                        "file_size": row[7],
                        "width": row[8],
                        "height": row[9],
                        "alt": row[10],
                        "title": row[11],
                        "preview_path": row[12],
                        "created_at": row[13].isoformat() if row[13] else None,
                        "updated_at": row[14].isoformat() if row[14] else None,
                        "used_in_news": row[15],
                        "used_in_pages": row[16],
                        "used_in_geo": row[17],
                        "used_sections": used_section_names(
                            in_news=row[15],
                            in_geo=row[17],
                            page_slugs=row[18],
                        ),
                        "storage_backend": row[19] or "local",
                        "external_url": row[20],
                        "external_key": row[21],
                        "url": _record_url(
                            {
                                "storage_path": row[5],
                                "external_url": row[20],
                            }
                        ),
                        "variants": variants,
                    }
                )

            return (result, total) if include_total else result


# Фактическое использование медиа → раздел, тег которого снять нельзя.
# Страницы сайта задаются slug-ом (см. таблицу pages).
_PAGE_SECTION_BY_SLUG = {
    "kontakty": "Контакты",
    "home": "Главная",
    "o-kompanii": "О компании",
}


def used_section_names(
    *,
    in_news: bool = False,
    in_geo: bool = False,
    page_slugs=None,
) -> list[str]:
    """Разделы, где медиа реально используется (по ссылкам в контенте)."""
    names: set[str] = set()

    if in_news:
        names.add("Новости")

    if in_geo:
        names.add("География")

    for slug in page_slugs or ():
        names.add(_PAGE_SECTION_BY_SLUG.get(str(slug), "Прочее"))

    return sorted(names)


def used_sections_for(cur, media_id: int) -> list[str]:
    """То же для одного файла (при правке тегов)."""
    cur.execute(
        "SELECT EXISTS (SELECT 1 FROM news_media WHERE media_id = %s)",
        (media_id,),
    )
    in_news = bool(cur.fetchone()[0])

    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM home_geo_attraction_photos WHERE media_id = %s
        )
        """,
        (media_id,),
    )
    in_geo = bool(cur.fetchone()[0])

    cur.execute(
        """
        SELECT DISTINCT p.slug
        FROM page_block_media pbm
        JOIN page_blocks b ON b.id = pbm.block_id
        JOIN pages p ON p.id = b.page_id
        WHERE pbm.media_id = %s
        """,
        (media_id,),
    )
    slugs = [row[0] for row in cur.fetchall()]

    return used_section_names(
        in_news=in_news,
        in_geo=in_geo,
        page_slugs=slugs,
    )


def list_media_categories() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, sort_order, created_at, updated_at
                FROM media_categories
                ORDER BY sort_order, name, id
                """
            )
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "sort_order": row[2],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None,
                }
                for row in cur.fetchall()
            ]


def create_media_category(name: str) -> dict:
    name = name.strip()

    if not name:
        raise MediaValidationError("Название категории не может быть пустым")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, sort_order, created_at, updated_at
                FROM media_categories
                WHERE LOWER(name) = LOWER(%s)
                """,
                (name,),
            )
            existing = cur.fetchone()

            if existing:
                raise MediaValidationError("Такая категория уже существует")

            cur.execute(
                """
                INSERT INTO media_categories (name)
                VALUES (%s)
                RETURNING id, name, sort_order, created_at, updated_at
                """,
                (name,),
            )
            row = cur.fetchone()

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "id": row[0],
        "name": row[1],
        "sort_order": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
        "updated_at": row[4].isoformat() if row[4] else None,
    }


def update_media(
    media_id: int,
    *,
    original_name: str | None = None,
    category_id: list[int] | None = None,
    category_id_provided: bool = False,
) -> dict:
    if original_name is not None:
        original_name = original_name.strip()
        if not original_name:
            raise MediaValidationError(
                "Название файла не может быть пустым"
            )

    if original_name is None and not category_id_provided:
        raise MediaValidationError("Нет изменений для сохранения")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM media WHERE id = %s",
                (media_id,),
            )
            if cur.fetchone() is None:
                raise MediaValidationError("Медиафайл не найден")

            if category_id_provided:
                category_id = category_id or [1]
                cur.execute(
                    "SELECT COUNT(*) FROM media_categories WHERE id = ANY(%s)",
                    (category_id,),
                )
                if cur.fetchone()[0] != len(set(category_id)):
                    raise MediaValidationError("Одна или несколько категорий не найдены")

                # Тег раздела, где файл реально используется, снять нельзя.
                # Добавлять новые теги при этом можно свободно.
                locked_names = used_sections_for(cur, media_id)

                if locked_names:
                    cur.execute(
                        "SELECT id, name FROM media_categories "
                        "WHERE name = ANY(%s)",
                        (locked_names,),
                    )
                    locked = {row[0]: row[1] for row in cur.fetchall()}

                    cur.execute(
                        "SELECT category_id FROM media WHERE id = %s",
                        (media_id,),
                    )
                    current_ids = set(cur.fetchone()[0] or [])
                    new_ids = set(category_id)

                    removed = sorted(
                        name
                        for cid, name in locked.items()
                        if cid in current_ids and cid not in new_ids
                    )

                    if removed:
                        raise MediaValidationError(
                            "Нельзя снять раздел, где файл используется: "
                            + ", ".join(removed)
                        )

            fields = []
            values = []

            if original_name is not None:
                fields.append("original_name = %s")
                values.append(original_name)

            if category_id_provided:
                fields.append("category_id = %s")
                values.append(category_id)

            fields.append("updated_at = NOW()")
            values.append(media_id)

            cur.execute(
                f"""
                UPDATE media
                SET {", ".join(fields)}
                WHERE id = %s
                RETURNING id, original_name, category_id, updated_at
                """,
                values,
            )
            row = cur.fetchone()

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "id": row[0],
        "original_name": row[1],
        "category_id": row[2],
        "updated_at": row[3].isoformat() if row[3] else None,
    }


def delete_media(media_id: int) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    storage_path,
                    preview_path,
                    storage_backend,
                    external_key
                FROM media
                WHERE id = %s
                """,
                (media_id,),
            )

            row = cur.fetchone()

            if row is None:
                raise MediaValidationError("Медиафайл не найден")

            cur.execute(
                """
                SELECT
                    storage_path,
                    storage_backend,
                    external_key
                FROM media_variants
                WHERE media_id = %s
                """,
                (media_id,),
            )

            variant_rows = cur.fetchall()
            variant_paths = [
                Path(variant_row[0])
                for variant_row in variant_rows
            ]

            external_keys = []

            main_backend = row[3] or "local"
            main_external_key = row[4]

            if main_backend == "albion" and main_external_key:
                external_keys.append(main_external_key)

            for variant_row in variant_rows:
                variant_backend = variant_row[1] or "local"
                variant_external_key = variant_row[2]

                if variant_backend == "albion" and variant_external_key:
                    external_keys.append(variant_external_key)

            cur.execute(
                """
                SELECT 1
                FROM news_media
                WHERE media_id = %s
                LIMIT 1
                """,
                (media_id,),
            )

            if cur.fetchone():
                raise MediaValidationError(
                    "Медиафайл используется в новостях и не может быть удалён"
                )

            cur.execute(
                """
                SELECT 1
                FROM page_block_media
                WHERE media_id = %s
                LIMIT 1
                """,
                (media_id,),
            )

            if cur.fetchone():
                raise MediaValidationError(
                    "Медиафайл используется на страницах сайта и не может быть удалён"
                )

            storage_path = Path(row[1])
            preview_path = Path(row[2]) if row[2] else None

            cur.execute(
                """
                DELETE FROM media
                WHERE id = %s
                """,
                (media_id,),
            )

    files_to_delete = [
        STORAGE_ROOT / storage_path,
        *[STORAGE_ROOT / path for path in variant_paths],
    ]

    if preview_path:
        files_to_delete.append(STORAGE_ROOT / preview_path)

    for file_path in files_to_delete:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    # Локальные копии удалены. Объекты в Albion удаляем, только если это
    # разрешено токену; отсутствие права delete не делает операцию неуспешной.
    for external_key in external_keys:
        try:
            deleted = albion_storage.delete_file(external_key)
        except Exception as exc:  # noqa: BLE001 — локальное удаление важнее
            logger.warning(
                "Albion storage: ошибка удаления объекта: %s",
                _safe_error(exc),
            )
            continue

        if not deleted:
            logger.warning(
                "Albion storage: объект %s остался в Albion "
                "(нет права delete или хранилище недоступно)",
                external_key,
            )

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "id": media_id,
        "deleted": True,
    }

def _run_video_command(args: list[str], *, timeout: int):
    try:
        return run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except TimeoutExpired as exc:
        raise MediaValidationError(
            "Обработка видео превысила допустимое время"
        ) from exc


def save_video(
    file_bytes: bytes,
    original_name: str,
    *,
    alt: str | None = None,
    title: str | None = None,
    category_id: list[int] | None = None,
    preview_time: float | None = None,
) -> dict:
    if not file_bytes:
        raise MediaValidationError("Файл пустой")

    category_id = _normalize_category_ids(category_id)

    if len(file_bytes) > VIDEO_MAX_INPUT_FILE_SIZE:
        raise MediaValidationError(
            "Размер исходного видео превышает 100 МБ"
        )

    media_uuid = uuid4()
    relative_dir = Path("media")
    absolute_dir = STORAGE_ROOT / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = STORAGE_ROOT / ".tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    input_path = temp_dir / f"{media_uuid}-input"
    output_path = absolute_dir / f"{media_uuid}.mp4"
    preview_path = absolute_dir / f"{media_uuid}-preview.webp"

    created_files: list[Path] = []

    try:
        input_path.write_bytes(file_bytes)

        probe = _run_video_command(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            timeout=VIDEO_PROBE_TIMEOUT_SECONDS,
        )

        duration_probe = _run_video_command(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            timeout=VIDEO_PROBE_TIMEOUT_SECONDS,
        )

        if probe.returncode != 0:
            raise MediaValidationError(
                "Не удалось определить параметры видео"
            )

        if duration_probe.returncode != 0 or not duration_probe.stdout.strip():
            raise MediaValidationError(
                "Не удалось определить длительность видео"
            )
        dimensions = probe.stdout.strip().splitlines()

        if len(dimensions) != 2:
            raise MediaValidationError(
                "Не удалось определить параметры видео"
            )

        try:
            source_width = int(dimensions[0])
            source_height = int(dimensions[1])
            duration = float(duration_probe.stdout.strip())
        except ValueError as exc:
            raise MediaValidationError(
                "Некорректные размеры видео"
            ) from exc

        if (
            source_width <= 0
            or source_height <= 0
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise MediaValidationError("Некорректные параметры видео")
        if (
            source_width > VIDEO_MAX_SOURCE_SIDE
            or source_height > VIDEO_MAX_SOURCE_SIDE
            or source_width * source_height > VIDEO_MAX_SOURCE_PIXELS
        ):
            raise MediaValidationError("Разрешение исходного видео слишком велико")
        if duration > VIDEO_MAX_DURATION_SECONDS:
            raise MediaValidationError(
                f"Длительность видео превышает {VIDEO_MAX_DURATION_SECONDS // 60} минут"
            )

        if preview_time is None:
            selected_preview_time = duration * 0.10
        else:
            selected_preview_time = max(0.0, min(float(preview_time), duration))


        scale = min(
            1.0,
            VIDEO_MAX_SIDE / max(source_width, source_height),
        )

        output_width = max(2, int(source_width * scale) // 2 * 2)
        output_height = max(2, int(source_height * scale) // 2 * 2)

        encode = run(
            [
                "ffmpeg",
                "-y",
                "-threads", "2",
                "-i", str(input_path),
                "-vf", f"scale={output_width}:{output_height}:flags=lanczos",
                "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264",
                "-preset", VIDEO_PRESET,
                "-crf", str(VIDEO_CRF),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", VIDEO_AUDIO_BITRATE,
                "-movflags", "+faststart",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=VIDEO_ENCODE_TIMEOUT_SECONDS,
        )

        if encode.returncode != 0 or not output_path.exists():
            raise MediaValidationError(
                "Не удалось обработать видео"
            )

        created_files.append(output_path)

        preview = run(
            [
                "ffmpeg",
                "-y",
                "-ss", str(selected_preview_time),
                "-i", str(output_path),
                "-frames:v", "1",
                "-vf", f"scale={output_width}:{output_height}:flags=lanczos",
                "-c:v", "libwebp",
                "-q:v", str(VIDEO_PREVIEW_QUALITY),
                str(preview_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=VIDEO_PREVIEW_TIMEOUT_SECONDS,
        )

        if preview.returncode != 0 or not preview_path.exists():
            raise MediaValidationError(
                "Не удалось создать превью видео"
            )

        created_files.append(preview_path)
        with get_connection() as conn:
            result = _insert_media(
                conn,
                media_uuid=media_uuid,
                original_name=original_name,
                storage_path=output_path.relative_to(STORAGE_ROOT),
                mime_type="video/mp4",
                file_size=output_path.stat().st_size,
                width=output_width,
                height=output_height,
                alt=alt,
                title=title,
                category_id=category_id,
                preview_path=(
                    preview_path.relative_to(STORAGE_ROOT)
                    if preview_path.exists()
                    else None
                ),
            )

        result["variants"] = []

        remote_objects = [
            {
                "kind": "media",
                "id": result["id"],
                "path": output_path,
                "relative_path": output_path.relative_to(STORAGE_ROOT),
            }
        ]

        if preview_path.exists():
            result["preview_path"] = str(
                preview_path.relative_to(STORAGE_ROOT)
            )
            remote_objects.append(
                {
                    "kind": "preview",
                    "id": None,
                    "path": preview_path,
                    "relative_path": preview_path.relative_to(STORAGE_ROOT),
                }
            )

        _remote_upload_objects(result, remote_objects)

        return result

    except TimeoutExpired as exc:
        for file_path in created_files:
            file_path.unlink(missing_ok=True)
        raise MediaValidationError(
            "Обработка видео превысила допустимое время"
        ) from exc
    except Exception:
        for file_path in created_files:
            file_path.unlink(missing_ok=True)
        raise
    finally:
        input_path.unlink(missing_ok=True)

def save_image(
    file_bytes: bytes,
    original_name: str,
    *,
    alt: str | None = None,
    title: str | None = None,
    category_id: list[int] | None = None,
    preview_time: float | None = None,
) -> dict:
    if not file_bytes:
        raise MediaValidationError("Файл пустой")

    category_id = _normalize_category_ids(category_id)

    if len(file_bytes) > MAX_INPUT_FILE_SIZE:
        raise MediaValidationError(
            "Размер исходного файла превышает 40 МБ"
        )

    image = _open_image(file_bytes)
    image_format = _detect_format(image)

    width, height = image.size

    if width <= 0 or height <= 0:
        raise MediaValidationError("Некорректные размеры изображения")

    if width * height > MAX_PIXELS:
        raise MediaValidationError(
            "Изображение содержит слишком большое количество пикселей"
        )

    media_uuid = uuid4()


    relative_dir = Path("media")
    absolute_dir = STORAGE_ROOT / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []

    try:
        if image_format == "GIF":
            data, mime_type, extension = _build_gif(image)

            relative_path = relative_dir / f"{media_uuid}{extension}"
            absolute_path = STORAGE_ROOT / relative_path

            absolute_path.write_bytes(data)
            created_files.append(absolute_path)

            with get_connection() as conn:
                result = _insert_media(
                    conn,
                    media_uuid=media_uuid,
                    original_name=original_name,
                    storage_path=relative_path,
                    mime_type=mime_type,
                    file_size=len(data),
                    width=width,
                    height=height,
                    alt=alt,
                    title=title,
                category_id=category_id,
                )

            result["variants"] = []

            _remote_upload_objects(
                result,
                [
                    {
                        "kind": "media",
                        "id": result["id"],
                        "path": absolute_path,
                        "relative_path": relative_path,
                    }
                ],
            )

            return result

        preserve_png = (
            image_format == "PNG"
            and (
                "transparency" in image.info
                or image.mode in ("RGBA", "LA")
            )
        )

        variants = _build_static_variants(
            image,
            preserve_png=preserve_png,
        )

        main_data, main_mime, main_extension = variants["large"]

        main_path = relative_dir / f"{media_uuid}{main_extension}"
        main_absolute_path = STORAGE_ROOT / main_path
        main_absolute_path.write_bytes(main_data)
        created_files.append(main_absolute_path)

        with Image.open(BytesIO(main_data)) as checked_main:
            checked_main.verify()

        main_width, main_height = _resize_for_variant(
            _prepare_static_image(image),
            VARIANT_SIZES["large"],
        ).size

        remote_objects = [
            {
                "kind": "media",
                "id": None,
                "path": main_absolute_path,
                "relative_path": main_path,
            }
        ]

        with get_connection() as conn:
            result = _insert_media(
                conn,
                media_uuid=media_uuid,
                original_name=original_name,
                storage_path=main_path,
                mime_type=main_mime,
                file_size=len(main_data),
                width=main_width,
                height=main_height,
                alt=alt,
                title=title,
                category_id=category_id,
            )

            result["variants"] = []
            remote_objects[0]["id"] = result["id"]

            for variant, (data, mime_type, extension) in variants.items():
                if variant == "large":
                    continue

                variant_image = Image.open(BytesIO(data))
                variant_width, variant_height = variant_image.size

                variant_path = (
                    relative_dir
                    / f"{media_uuid}-{variant}{extension}"
                )
                variant_absolute_path = STORAGE_ROOT / variant_path

                variant_absolute_path.write_bytes(data)
                created_files.append(variant_absolute_path)

                with Image.open(BytesIO(data)) as checked_variant:
                    checked_variant.verify()

                variant_result = _insert_variant(
                    conn,
                    media_id=result["id"],
                    variant=variant,
                    storage_path=variant_path,
                    mime_type=mime_type,
                    file_size=len(data),
                    width=variant_width,
                    height=variant_height,
                )

                result["variants"].append(variant_result)
                remote_objects.append(
                    {
                        "kind": "variant",
                        "id": variant_result["id"],
                        "path": variant_absolute_path,
                        "relative_path": variant_path,
                    }
                )

        _remote_upload_objects(result, remote_objects)

        return result

    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise

def save_document(
    file_bytes: bytes,
    original_name: str,
    *,
    alt: str | None = None,
    title: str | None = None,
    category_id: list[int] | None = None,
) -> dict:
    if not file_bytes:
        raise MediaValidationError("Файл пустой")

    extension = Path(original_name or "").suffix.lower()

    if extension not in DOCUMENT_MIME_TYPES:
        allowed = ", ".join(
            sorted(item.lstrip(".") for item in DOCUMENT_MIME_TYPES)
        )
        raise MediaValidationError(
            f"Формат документа не поддерживается. Разрешены: {allowed}"
        )

    category_id = _normalize_category_ids(category_id)

    if len(file_bytes) > MAX_DOCUMENT_FILE_SIZE:
        raise MediaValidationError(
            "Размер исходного файла превышает 40 МБ"
        )

    media_uuid = uuid4()

    relative_dir = Path("media")
    absolute_dir = STORAGE_ROOT / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    relative_path = relative_dir / f"{media_uuid}{extension}"
    absolute_path = STORAGE_ROOT / relative_path

    created_files: list[Path] = []

    try:
        absolute_path.write_bytes(file_bytes)
        created_files.append(absolute_path)

        with get_connection() as conn:
            result = _insert_media(
                conn,
                media_uuid=media_uuid,
                original_name=original_name,
                storage_path=relative_path,
                mime_type=DOCUMENT_MIME_TYPES[extension],
                file_size=len(file_bytes),
                width=None,
                height=None,
                alt=alt,
                title=title,
                category_id=category_id,
            )

        result["variants"] = []

        _remote_upload_objects(
            result,
            [
                {
                    "kind": "media",
                    "id": result["id"],
                    "path": absolute_path,
                    "relative_path": relative_path,
                }
            ],
        )

        return result

    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise

def get_media_stats() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_files,
                    COUNT(*) FILTER (
                        WHERE EXISTS (SELECT 1 FROM news_media nm WHERE nm.media_id = media.id) OR EXISTS (SELECT 1 FROM page_block_media pbm WHERE pbm.media_id = media.id)
                    ) AS used_files,
                    COALESCE(SUM(file_size), 0) AS size_bytes
                FROM media
                """
            )
            overview = cur.fetchone()

            cur.execute(
                """
                SELECT
                    mc.id,
                    mc.name,
                    COUNT(m.id) AS total_files,
                    COUNT(m.id) FILTER (
                        WHERE EXISTS (SELECT 1 FROM news_media nm WHERE nm.media_id = m.id) OR EXISTS (SELECT 1 FROM page_block_media pbm WHERE pbm.media_id = m.id)
                    ) AS used_files,
                    COALESCE(SUM(m.file_size), 0) AS size_bytes
                FROM media_categories mc
                LEFT JOIN media m
                    ON mc.id = ANY(m.category_id)
                GROUP BY mc.id, mc.name, mc.sort_order
                ORDER BY mc.sort_order, mc.id
                """
            )
            categories = [
                {
                    "id": row[0],
                    "name": row[1],
                    "total_files": row[2],
                    "used_files": row[3],
                    "size_bytes": row[4],
                }
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE mime_type LIKE 'image/%'),
                    COALESCE(
                        SUM(file_size) FILTER (WHERE mime_type LIKE 'image/%'),
                        0
                    ),
                    COUNT(*) FILTER (WHERE mime_type LIKE 'video/%'),
                    COALESCE(
                        SUM(file_size) FILTER (WHERE mime_type LIKE 'video/%'),
                        0
                    ),
                    COUNT(*) FILTER (
                        WHERE mime_type NOT LIKE 'image/%'
                          AND mime_type NOT LIKE 'video/%'
                    ),
                    COALESCE(
                        SUM(file_size) FILTER (
                            WHERE mime_type NOT LIKE 'image/%'
                              AND mime_type NOT LIKE 'video/%'
                        ),
                        0
                    )
                FROM media
                """
            )
            type_row = cur.fetchone()

            cur.execute(
                """
                SELECT
                    CASE
                        WHEN original_name ~ '\\.[^.]+$'
                        THEN lower(substring(original_name from '\\.([^.]+)$'))
                        ELSE 'без расширения'
                    END AS extension,
                    COUNT(*) AS total_files,
                    COALESCE(SUM(file_size), 0) AS size_bytes
                FROM media
                GROUP BY extension
                ORDER BY total_files DESC, extension
                """
            )
            extensions = [
                {
                    "extension": row[0],
                    "total_files": row[1],
                    "size_bytes": row[2],
                }
                for row in cur.fetchall()
            ]

    disk = shutil.disk_usage(STORAGE_ROOT)
    cpu_percent = psutil.cpu_percent(interval=0.1)


    return {
        "overview": {
            "total_files": overview[0],
            "used_files": overview[1],
            "size_bytes": overview[2],
        },
        "categories": categories,
        "types": {
            "photos": {
                "total_files": type_row[0],
                "size_bytes": type_row[1],
            },
            "videos": {
                "total_files": type_row[2],
                "size_bytes": type_row[3],
            },
            "other": {
                "total_files": type_row[4],
                "size_bytes": type_row[5],
            },
            "extensions": extensions,
        },
        "storage": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "free_percent": round((disk.free / disk.total) * 100, 1) if disk.total else 0,
        },
        "cpu_percent": cpu_percent,
}
