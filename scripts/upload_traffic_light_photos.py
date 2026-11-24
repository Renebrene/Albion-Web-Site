"""Загрузка фотографий светофоров в хранилище.

Скрипт:
1. Создаёт категорию «Светофоры» если её нет.
2. Копирует фотографии из /home/alexice/Desktop/MEGA/светофоры в storage/media/.
3. Регистрирует их в таблице media с вариантами (card, thumb, original).

Запуск:
  .venv/bin/python scripts/upload_traffic_light_photos.py
"""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path

from backend.services.data_service import get_connection, load_env_file, PROJECT_DIR


load_env_file(PROJECT_DIR / ".env")

PHOTOS_DIR = Path("/home/alexice/Desktop/MEGA/светофоры")
STORAGE_ROOT = PROJECT_DIR / "storage"
STORAGE_DIR = STORAGE_ROOT / "media"
CATEGORY_NAME = "Светофоры"


def get_or_create_category(conn, name: str) -> int:
    """Получает или создаёт категорию медиа. Возвращает id."""
    row = conn.execute(
        "SELECT id FROM media_categories WHERE name = %s",
        (name,),
    ).fetchone()

    if row:
        return row[0]

    # Получаем максимальный sort_order.
    max_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), 0) FROM media_categories"
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO media_categories (name, sort_order)
        VALUES (%s, %s)
        """,
        (name, max_order + 10),
    )

    return conn.execute(
        "SELECT id FROM media_categories WHERE name = %s",
        (name,),
    ).fetchone()[0]


def generate_filename(base_name: str) -> str:
    """Генерирует UUID-имя файла на основе原名."""
    # Убираем расширение.
    stem = base_name.rsplit(".", 1)[0] if "." in base_name else base_name

    # Хэш для уникальности.
    hash_val = hashlib.md5(stem.encode()).hexdigest()[:12]

    return f"{hash_val}-{base_name}"


def create_variants(src_path: Path, base_name: str) -> dict:
    """Создаёт варианты изображения (card, thumb, original).

    Возвращает:
      {
        'original': {'storage_path': str, 'width': int, 'height': int, ...},
        'card': {'storage_path': str, 'width': int, 'height': int, ...},
        'thumb': {'storage_path': str, 'width': int, 'height': int, ...}
      }
    """
    import PIL.Image

    variants = {}

    # Оригинальный файл.
    orig_name = generate_filename(base_name)
    orig_path = STORAGE_DIR / orig_name
    shutil.copy2(src_path, orig_path)

    img = PIL.Image.open(src_path)
    width, height = img.size

    variants["large"] = {
        "storage_path": str(orig_path.relative_to(STORAGE_ROOT)),
        "width": width,
        "height": height,
        "mime_type": img.format.lower(),
        "file_size": src_path.stat().st_size,
    }

    # Card variant: 640px по shortest side.
    card_name = f"{orig_name.replace('.jpg', '').replace('.png', '')}-card.jpg"
    card_path = STORAGE_DIR / card_name
    img_card = img.copy()
    img_card.thumbnail((640, 480), PIL.Image.LANCZOS)
    img_card.save(card_path, "JPEG", quality=85)

    variants["card"] = {
        "storage_path": str(card_path.relative_to(STORAGE_ROOT)),
        "width": img_card.size[0],
        "height": img_card.size[1],
        "mime_type": "jpeg",
        "file_size": card_path.stat().st_size,
    }

    # Thumb variant: 200px.
    thumb_name = f"{orig_name.replace('.jpg', '').replace('.png', '')}-thumb.jpg"
    thumb_path = STORAGE_DIR / thumb_name
    img_thumb = img.copy()
    img_thumb.thumbnail((200, 150), PIL.Image.LANCZOS)
    img_thumb.save(thumb_path, "JPEG", quality=70)

    variants["thumb"] = {
        "storage_path": str(thumb_path.relative_to(STORAGE_ROOT)),
        "width": img_thumb.size[0],
        "height": img_thumb.size[1],
        "mime_type": "jpeg",
        "file_size": thumb_path.stat().st_size,
    }

    return variants


def upload_photos() -> None:
    """Загружает все фотографии из PHOTOS_DIR."""
    if not PHOTOS_DIR.exists():
        print(f"Директория не найдена: {PHOTOS_DIR}")
        return

    photos = sorted(PHOTOS_DIR.glob("*.jpg")) + sorted(PHOTOS_DIR.glob("*.png"))

    if not photos:
        print("Фотографий не найдено.")
        return

    with get_connection() as conn:
        category_id = get_or_create_category(conn, CATEGORY_NAME)
        print(f"Категория «{CATEGORY_NAME}»: id={category_id}")

        uploaded = 0

        for photo_path in photos:
            base_name = photo_path.name
            print(f"  Загрузка: {base_name}")

            try:
                variants = create_variants(photo_path, base_name)

                # Определяем mime_type.
                mime_type = "image/jpeg"
                if base_name.lower().endswith(".png"):
                    mime_type = "image/png"

                # Генерируем UUID для media записи.
                media_uuid = uuid.uuid4()

                # Вставляем в media (id auto-increment, category_id as array).
                result = conn.execute(
                    """
                    INSERT INTO media (
                        uuid, original_name, storage_path, mime_type,
                        file_size, width, height, category_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        media_uuid,
                        base_name,
                        variants["large"]["storage_path"],
                        mime_type,
                        variants["large"]["file_size"],
                        variants["large"]["width"],
                        variants["large"]["height"],
                        [category_id],  # Array format
                    ),
                )

                media_id = result.fetchone()[0]

                # Вставляем варианты.
                for variant_name, variant_data in variants.items():
                    conn.execute(
                        """
                        INSERT INTO media_variants (
                            media_id, variant, storage_path,
                            mime_type, width, height, file_size
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            media_id,
                            variant_name,
                            variant_data["storage_path"],
                            variant_data["mime_type"],
                            variant_data["width"],
                            variant_data["height"],
                            variant_data["file_size"],
                        ),
                    )

                uploaded += 1
                print(f"    ✓ Загружено (id={media_id})")

            except Exception as exc:
                print(f"    ✗ Ошибка: {exc}")

        print(f"\nЗагружено фотографий: {uploaded}/{len(photos)}")


if __name__ == "__main__":
    upload_photos()
