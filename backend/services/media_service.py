from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pillow_heif
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from backend.services.data_service import PROJECT_DIR, get_connection


pillow_heif.register_heif_opener()

STORAGE_ROOT = PROJECT_DIR / "storage"

MAX_INPUT_FILE_SIZE = 40 * 1024 * 1024
MAX_PIXELS = 50_000_000

VARIANT_SIZES = {
    "large": 2400,
    "card": 1000,
    "thumb": 400,
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
}


class MediaValidationError(ValueError):
    pass


def _open_image(file_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(BytesIO(file_bytes))

        image.verify()

        image = Image.open(BytesIO(file_bytes))
        image.load()

        return image

    except Image.DecompressionBombError as exc:
        raise MediaValidationError(
            "Изображение содержит слишком большое количество пикселей"
        ) from exc
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
        else:
            data = _encode_jpeg(resized, 85 if variant == "large" else 82)
            mime_type = "image/jpeg"
            extension = ".jpg"

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
    category_id: int | None,
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
                category_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, uuid, original_name, storage_path,
                      mime_type, file_size, width, height,
                      alt, title, created_at, updated_at
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
            ),
        )

        row = cur.fetchone()

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
        "created_at": row[10].isoformat() if row[10] else None,
        "updated_at": row[11].isoformat() if row[11] else None,
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
                height
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                media_id,
                variant,
                str(storage_path),
                mime_type,
                file_size,
                width,
                height,
            ),
        )

        row = cur.fetchone()

    return {
        "id": row[0],
        "variant": variant,
        "storage_path": str(storage_path),
        "mime_type": mime_type,
        "file_size": file_size,
        "width": width,
        "height": height,
    }


def list_media() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    m.id,
                    m.uuid,
                    m.original_name,
                    m.category_id,
                    mc.name AS category_name,
                    m.storage_path,
                    m.mime_type,
                    m.file_size,
                    m.width,
                    m.height,
                    m.alt,
                    m.title,
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
                    ) AS used_in_pages
                FROM media m
                LEFT JOIN media_categories mc
                    ON mc.id = m.category_id
                ORDER BY m.created_at DESC, m.id DESC
                """
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
                        height
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
                    }
                    for variant_row in cur.fetchall()
                ]

                result.append(
                    {
                        "id": media_id,
                        "uuid": str(row[1]),
                        "original_name": row[2],
                        "category_id": row[3],
                        "category_name": row[4],
                        "storage_path": row[5],
                        "mime_type": row[6],
                        "file_size": row[7],
                        "width": row[8],
                        "height": row[9],
                        "alt": row[10],
                        "title": row[11],
                        "created_at": row[12].isoformat() if row[12] else None,
                        "updated_at": row[13].isoformat() if row[13] else None,
                        "used_in_news": row[14],
                        "used_in_pages": row[15],
                        "variants": variants,
                    }
                )

            return result


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
    category_id: int | None = None,
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

            if category_id_provided and category_id is not None:
                cur.execute(
                    "SELECT id FROM media_categories WHERE id = %s",
                    (category_id,),
                )
                if cur.fetchone() is None:
                    raise MediaValidationError("Категория не найдена")

            fields = []
            values = []

            if original_name is not None:
                fields.append("original_name = %s")
                values.append(original_name)

            if category_id_provided:
                if category_id is None:
                    fields.append("category_id = NULL")
                else:
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
                    storage_path
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
                SELECT storage_path
                FROM media_variants
                WHERE media_id = %s
                """,
                (media_id,),
            )

            variant_paths = [
                Path(variant_row[0])
                for variant_row in cur.fetchall()
            ]

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

    for file_path in files_to_delete:
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "id": media_id,
        "deleted": True,
    }

def save_image(
    file_bytes: bytes,
    original_name: str,
    *,
    alt: str | None = None,
    title: str | None = None,
    category_id: int | None = 1,
) -> dict:
    if not file_bytes:
        raise MediaValidationError("Файл пустой")

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

            return result

    except Exception:
        for path in created_files:
            path.unlink(missing_ok=True)
        raise
