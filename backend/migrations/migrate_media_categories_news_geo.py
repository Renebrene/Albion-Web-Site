"""Раскладка медиатеки по разделам: «Новости» и «География».

- Фото новостей (media, привязанные к news_media) получают раздел
  «Новости».
- Фото городов и районов области (media из home_geo_attraction_photos)
  переносятся в новый раздел «География» (создаётся, если его нет).

Категории медиатеки виртуальные: файлы не двигаются, меняется только
category_id. Скрипт идемпотентен — повторный запуск ничего не портит.

Запуск: .venv/bin/python -m backend.migrations.migrate_media_categories_news_geo
"""
from __future__ import annotations

from backend.services.data_service import get_connection


NEWS_CATEGORY_ID = 2
GEO_CATEGORY_NAME = "География"
GEO_CATEGORY_SORT = 15


def ensure_category(cur, name: str, sort_order: int) -> int:
    """Возвращает id раздела по имени, создавая его при отсутствии."""
    cur.execute("SELECT id FROM media_categories WHERE name = %s", (name,))
    row = cur.fetchone()

    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO media_categories (name, sort_order)
        VALUES (%s, %s)
        RETURNING id
        """,
        (name, sort_order),
    )

    return cur.fetchone()[0]


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. Новости: добавляем тег «Новости» тем медиа новостей, у
            # которых его ещё нет (остальные категории не трогаем).
            cur.execute(
                """
                UPDATE media
                SET category_id = (
                        COALESCE(category_id, ARRAY[]::bigint[])
                        || ARRAY[%s]::bigint[]
                    ),
                    updated_at = NOW()
                WHERE id IN (SELECT media_id FROM news_media)
                  AND NOT (
                      COALESCE(category_id, ARRAY[]::bigint[])
                      @> ARRAY[%s]::bigint[]
                  )
                """,
                (NEWS_CATEGORY_ID, NEWS_CATEGORY_ID),
            )
            news_updated = cur.rowcount

            # 2. География: создаём раздел и переносим в него фото городов
            # и районов области (из «Разного»).
            geo_id = ensure_category(cur, GEO_CATEGORY_NAME, GEO_CATEGORY_SORT)

            cur.execute(
                """
                UPDATE media
                SET category_id = ARRAY[%s]::bigint[],
                    updated_at = NOW()
                WHERE id IN (SELECT media_id FROM home_geo_attraction_photos)
                  AND category_id IS DISTINCT FROM ARRAY[%s]::bigint[]
                """,
                (geo_id, geo_id),
            )
            geo_updated = cur.rowcount

            # 3. Чистка: у медиа, не привязанных ни к одной новости, тег
            # «Новости» лишний — снимаем его (если других тегов не осталось,
            # файл уходит в «Разное»).
            cur.execute(
                """
                UPDATE media
                SET category_id = CASE
                        WHEN array_remove(
                                 COALESCE(category_id, ARRAY[]::bigint[]),
                                 %s::bigint
                             ) = ARRAY[]::bigint[]
                            THEN ARRAY[1]::bigint[]
                        ELSE array_remove(
                                 COALESCE(category_id, ARRAY[]::bigint[]),
                                 %s::bigint
                             )
                    END,
                    updated_at = NOW()
                WHERE COALESCE(category_id, ARRAY[]::bigint[])
                      @> ARRAY[%s]::bigint[]
                  AND NOT EXISTS (
                      SELECT 1 FROM news_media nm WHERE nm.media_id = media.id
                  )
                """,
                (NEWS_CATEGORY_ID, NEWS_CATEGORY_ID, NEWS_CATEGORY_ID),
            )
            stripped = cur.rowcount

    print(f"Новости: добавлен тег у медиа — {news_updated}")
    print(f"География (id={geo_id}): перенесено фото — {geo_updated}")
    print(f"Чистка: снят лишний тег «Новости» — {stripped}")


if __name__ == "__main__":
    main()
