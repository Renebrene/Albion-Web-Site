from backend.services.data_service import get_connection


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
        }
