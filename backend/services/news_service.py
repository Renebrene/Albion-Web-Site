from backend.services.data_service import get_connection


def _media_item(row):
    (
        media_id,
        original_name,
        storage_path,
        mime_type,
        file_size,
        width,
        height,
        alt,
        title,
        sort_order,
        is_cover,
    ) = row

    return {
        "id": media_id,
        "original_name": original_name,
        "storage_path": storage_path,
        "mime_type": mime_type,
        "file_size": file_size,
        "width": width,
        "height": height,
        "alt": alt,
        "title": title,
        "sort_order": sort_order,
        "is_cover": is_cover,
    }


def _news_item(row, media_rows):
    (
        news_id,
        news_uuid,
        slug,
        title,
        excerpt,
        content,
        category_id,
        category_name,
        category_slug,
        published_at,
        is_published,
        is_featured,
        seo_title,
        seo_description,
        created_at,
        updated_at,
    ) = row

    return {
        "id": news_id,
        "uuid": str(news_uuid),
        "slug": slug,
        "title": title,
        "excerpt": excerpt,
        "content": content,
        "category": {
            "id": category_id,
            "name": category_name,
            "slug": category_slug,
        } if category_id is not None else None,
        "date": published_at.isoformat() if published_at else None,
        "published_at": published_at.isoformat() if published_at else None,
        "is_published": is_published,
        "is_featured": is_featured,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "media": [_media_item(media) for media in media_rows],
    }


def get_news():
    news_sql = """
        SELECT
            n.id,
            n.uuid,
            n.slug,
            n.title,
            n.excerpt,
            n.content,
            n.category_id,
            c.name AS category_name,
            c.slug AS category_slug,
            n.published_at,
            n.is_published,
            n.is_featured,
            n.seo_title,
            n.seo_description,
            n.created_at,
            n.updated_at
        FROM news n
        LEFT JOIN news_categories c
            ON c.id = n.category_id
        WHERE n.is_published = TRUE
        ORDER BY n.published_at DESC NULLS LAST, n.id DESC
    """

    media_sql = """
        SELECT
            m.id,
            m.original_name,
            m.storage_path,
            m.mime_type,
            m.file_size,
            m.width,
            m.height,
            m.alt,
            m.title,
            nm.sort_order,
            nm.is_cover
        FROM news_media nm
        JOIN media m
            ON m.id = nm.media_id
        WHERE nm.news_id = %s
        ORDER BY nm.sort_order, nm.id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(news_sql)
            news_rows = cur.fetchall()

            result = []

            for news_row in news_rows:
                news_id = news_row[0]

                cur.execute(media_sql, (news_id,))
                media_rows = cur.fetchall()

                result.append(_news_item(news_row, media_rows))

    return result


def get_news_item(slug: str):
    news_sql = """
        SELECT
            n.id,
            n.uuid,
            n.slug,
            n.title,
            n.excerpt,
            n.content,
            n.category_id,
            c.name AS category_name,
            c.slug AS category_slug,
            n.published_at,
            n.is_published,
            n.is_featured,
            n.seo_title,
            n.seo_description,
            n.created_at,
            n.updated_at
        FROM news n
        LEFT JOIN news_categories c
            ON c.id = n.category_id
        WHERE n.slug = %s
          AND n.is_published = TRUE
        LIMIT 1
    """

    media_sql = """
        SELECT
            m.id,
            m.original_name,
            m.storage_path,
            m.mime_type,
            m.file_size,
            m.width,
            m.height,
            m.alt,
            m.title,
            nm.sort_order,
            nm.is_cover
        FROM news_media nm
        JOIN media m
            ON m.id = nm.media_id
        WHERE nm.news_id = %s
        ORDER BY nm.sort_order, nm.id
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(news_sql, (slug,))
            news_row = cur.fetchone()

            if news_row is None:
                return None

            cur.execute(media_sql, (news_row[0],))
            media_rows = cur.fetchall()

    return _news_item(news_row, media_rows)
