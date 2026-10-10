"""Раздел медиатеки «Документы».

Создаётся раздел для документов (текстовых и табличных файлов), которые
загружаются, в частности, для ссылок подвала сайта. Уже загруженные
документы (не изображения и не видео) переносятся сюда.

Запуск: .venv/bin/python -m backend.migrations.migrate_media_category_documents
"""
from __future__ import annotations

from backend.services.data_service import get_connection


CATEGORY_NAME = "Документы"
CATEGORY_SORT = 12


def ensure_category(cur) -> int:
    cur.execute("SELECT id FROM media_categories WHERE name = %s", (CATEGORY_NAME,))
    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO media_categories (name, sort_order)
        VALUES (%s, %s)
        RETURNING id
        """,
        (CATEGORY_NAME, CATEGORY_SORT),
    )

    return cur.fetchone()[0]


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            category_id = ensure_category(cur)

            # Документы — всё, что не изображение и не видео.
            cur.execute(
                """
                UPDATE media
                SET category_id = ARRAY[%s]::bigint[],
                    updated_at = NOW()
                WHERE mime_type IS NOT NULL
                  AND mime_type NOT LIKE 'image/%%'
                  AND mime_type NOT LIKE 'video/%%'
                  AND category_id IS DISTINCT FROM ARRAY[%s]::bigint[]
                """,
                (category_id, category_id),
            )
            moved = cur.rowcount

    print(f"Раздел «{CATEGORY_NAME}» (id={category_id}): перенесено документов — {moved}")


if __name__ == "__main__":
    main()
