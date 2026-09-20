from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from backend.services.data_service import PROJECT_DIR, get_connection


STORAGE_ROOT = PROJECT_DIR / "storage"

ALLOWED_FORMATS = {
    "JPEG": {
        "mime_type": "image/jpeg",
        "extension": ".jpg",
    },
    "PNG": {
        "mime_type": "image/png",
        "extension": ".png",
    },
    "WEBP": {
        "mime_type": "image/webp",
        "extension": ".webp",
    },
}

MAX_FILE_SIZE = 15 * 1024 * 1024


class MediaValidationError(ValueError):
    pass


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

    if len(file_bytes) > MAX_FILE_SIZE:
        raise MediaValidationError(
            f"Размер файла превышает {MAX_FILE_SIZE // (1024 * 1024)} МБ"
        )

    try:
        image = Image.open(__import__("io").BytesIO(file_bytes))
        image.verify()

        image = Image.open(__import__("io").BytesIO(file_bytes))
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaValidationError("Файл не является корректным изображением") from exc

    image_format = (image.format or "").upper()

    if image_format not in ALLOWED_FORMATS:
        allowed = ", ".join(ALLOWED_FORMATS)
        raise MediaValidationError(
            f"Формат изображения не поддерживается. Разрешены: {allowed}"
        )

    width, height = image.size
    media_uuid = uuid4()

    now = datetime.now(timezone.utc)
    year = now.strftime("%Y")
    month = now.strftime("%m")

    relative_dir = Path(storage_subdir) / year / month
    absolute_dir = STORAGE_ROOT / relative_dir
    absolute_dir.mkdir(parents=True, exist_ok=True)

    extension = ALLOWED_FORMATS[image_format]["extension"]
    filename = f"{media_uuid}{extension}"

    relative_path = relative_dir / filename
    absolute_path = STORAGE_ROOT / relative_path

    absolute_path.write_bytes(file_bytes)

    try:
        with get_connection() as conn:
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
                        str(relative_path),
                        ALLOWED_FORMATS[image_format]["mime_type"],
                        len(file_bytes),
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

    except Exception:
        absolute_path.unlink(missing_ok=True)
        raise
