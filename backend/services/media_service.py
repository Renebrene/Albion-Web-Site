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
                title
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def save_image(
    file_bytes: bytes,
    original_name: str,
    *,
    alt: str | None = None,
    title: str | None = None,
    storage_subdir: str = "news",
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

    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")

    relative_dir = Path(storage_subdir) / year / month
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
