from backend.services.data_service import get_connection


def get_page(slug: str):
    page_sql = """
        SELECT
            id,
            slug,
            title,
            seo_title,
            seo_description,
            is_published,
            page_type,
            menu_title,
            show_in_menu,
            menu_order,
            parent_id,
            template
        FROM pages
        WHERE slug = %s
        LIMIT 1
    """

    blocks_sql = """
        SELECT
            id,
            block_key,
            block_type,
            eyebrow,
            title,
            subtitle,
            body,
            sort_order,
            is_active,
            content
        FROM page_blocks
        WHERE page_id = %s
          AND is_active = TRUE
        ORDER BY sort_order, id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(page_sql, (slug,))
            page = cur.fetchone()

            if page is None:
                return None

            (
                page_id,
                page_slug,
                title,
                seo_title,
                seo_description,
                is_published,
                page_type,
                menu_title,
                show_in_menu,
                menu_order,
                parent_id,
                template,
            ) = page

            cur.execute(blocks_sql, (page_id,))
            block_rows = cur.fetchall()

    blocks = []

    for row in block_rows:
        (
            block_id,
            block_key,
            block_type,
            eyebrow,
            block_title,
            subtitle,
            body,
            sort_order,
            is_active,
            content,
        ) = row

        blocks.append({
            "id": block_id,
            "key": block_key,
            "type": block_type,
            "eyebrow": eyebrow,
            "title": block_title,
            "subtitle": subtitle,
            "body": body,
            "sort_order": sort_order,
            "is_active": is_active,
            "content": content or {},
        })

    return {
        "id": page_id,
        "slug": page_slug,
        "title": title,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "is_published": is_published,
        "page_type": page_type,
        "menu_title": menu_title,
        "show_in_menu": show_in_menu,
        "menu_order": menu_order,
        "parent_id": parent_id,
        "template": template,
        "blocks": blocks,
    }
