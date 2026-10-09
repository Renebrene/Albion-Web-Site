from backend.services.data_service import get_connection


# Медиа, прикреплённые к блокам страницы. Формат элемента совпадает с
# форматом медиа новостей (см. news_service._media_item), чтобы фронт
# переиспользовал NewsMediaCarousel/normalizeMedia без адаптеров.
_BLOCKS_MEDIA_SQL = """
    SELECT
        pb.block_key,
        m.id,
        m.original_name,
        m.storage_path,
        m.mime_type,
        m.file_size,
        m.width,
        m.height,
        m.alt,
        m.title,
        pbm.sort_order,
        pbm.is_cover,
        COALESCE(
            (
                SELECT json_agg(
                    json_build_object(
                        'variant', mv.variant,
                        'storage_path', mv.storage_path,
                        'mime_type', mv.mime_type,
                        'width', mv.width,
                        'height', mv.height,
                        'file_size', mv.file_size
                    )
                    ORDER BY CASE mv.variant
                        WHEN 'large' THEN 1
                        WHEN 'card' THEN 2
                        WHEN 'thumb' THEN 3
                        ELSE 4
                    END
                )
                FROM media_variants mv
                WHERE mv.media_id = m.id
            ),
            '[]'::json
        ) AS variants,
        m.preview_path
    FROM page_blocks pb
    JOIN page_block_media pbm
        ON pbm.block_id = pb.id
    JOIN media m
        ON m.id = pbm.media_id
    WHERE pb.page_id = %s
      AND pb.is_active = TRUE
    ORDER BY pb.sort_order, pb.id, pbm.sort_order, pbm.id
"""


def _media_item(row) -> dict:
    return {
        "id": row[1],
        "original_name": row[2],
        "storage_path": row[3],
        "mime_type": row[4],
        "file_size": row[5],
        "width": row[6],
        "height": row[7],
        "alt": row[8],
        "title": row[9],
        "sort_order": row[10],
        "is_cover": row[11],
        "variants": row[12] or [],
        "preview_path": row[13],
    }


def _blocks_media(conn, page_id: int) -> dict:
    """Медиа блоков в виде ``{ "<block_key>": [media, ...] }``."""
    result: dict[str, list[dict]] = {}

    rows = conn.execute(_BLOCKS_MEDIA_SQL, (page_id,)).fetchall()

    for row in rows:
        block_key = row[0]
        result.setdefault(block_key, []).append(_media_item(row))

    return result


def get_about():
    with get_connection() as conn:
        page = conn.execute(
            """
            SELECT id, title
            FROM pages
            WHERE slug = 'o-kompanii'
              AND is_published = TRUE
            """
        ).fetchone()

        if page is None:
            raise RuntimeError("Страница 'o-kompanii' не найдена")

        page_id, title = page

        hero = conn.execute(
            """
            SELECT eyebrow, title, body
            FROM page_blocks
            WHERE page_id = %s
              AND block_key = 'hero'
              AND is_active = TRUE
            """,
            (page_id,),
        ).fetchone()

        if hero is None:
            raise RuntimeError("Hero-блок страницы 'o-kompanii' не найден")

        stats = conn.execute(
            """
            SELECT value, label
            FROM page_stats
            WHERE page_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (page_id,),
        ).fetchall()

        network = conn.execute(
            """
            SELECT item_type, title
            FROM about_network_items
            WHERE page_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (page_id,),
        ).fetchall()

        network_block = conn.execute(
            """
            SELECT title
            FROM page_blocks
            WHERE page_id = %s
              AND block_key = 'network'
              AND is_active = TRUE
            """,
            (page_id,),
        ).fetchone()

        activity_block = conn.execute(
            """
            SELECT title
            FROM page_blocks
            WHERE page_id = %s
              AND block_key = 'activities'
              AND is_active = TRUE
            """,
            (page_id,),
        ).fetchone()

        activities = conn.execute(
            """
            SELECT title
            FROM about_activity_items
            WHERE page_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (page_id,),
        ).fetchall()

        production_block = conn.execute(
            """
            SELECT title
            FROM page_blocks
            WHERE page_id = %s
              AND block_key = 'production'
              AND is_active = TRUE
            """,
            (page_id,),
        ).fetchone()

        production = conn.execute(
            """
            SELECT title, body
            FROM about_production_items
            WHERE page_id = %s
              AND is_active = TRUE
            ORDER BY sort_order
            """,
            (page_id,),
        ).fetchall()

        blocks_media = _blocks_media(conn, page_id)

        return {
            "eyebrow": hero[0],
            "title": hero[1],
            "intro": hero[2],
            "stats": [
                {
                    "value": row[0],
                    "label": row[1],
                }
                for row in stats
            ],
            "network": {
                "title": network_block[0] if network_block else "",
                "cities": [
                    row[1]
                    for row in network
                    if row[0] == "city"
                ],
                "highways": [
                    row[1]
                    for row in network
                    if row[0] == "highway"
                ],
            },
            "activities": {
                "title": activity_block[0] if activity_block else "",
                "items": [row[0] for row in activities],
            },
            "production": {
                "title": production_block[0] if production_block else "",
                "items": [
                    {
                        "title": row[0],
                        "text": row[1],
                    }
                    for row in production
                ],
            },
            "images": {
                "hero": "",
                "network": "",
                "production": "",
            },
            "blocks_media": blocks_media,
        }
