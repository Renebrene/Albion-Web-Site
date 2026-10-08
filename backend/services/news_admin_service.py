"""CMS-сервис новостей: чтение и редактирование новостей
и категорий из админки.

Только операции с PostgreSQL — HTTP-слой (роутер, авторизация)
живёт в backend/api/admin_news.py.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from backend.services.data_service import get_connection


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def _clean(value: Any) -> str:
    return (value or "").strip() if value is not None else ""


def _clean_or_none(value: Any) -> str | None:
    value = _clean(value)
    return value or None


def _slugify(value: str) -> str:
    """Латиница из произвольного текста (в т.ч. кириллицы)."""
    value = _clean(value).lower()

    chars = []
    for char in value:
        if char in _TRANSLIT:
            chars.append(_TRANSLIT[char])
        elif char.isalnum() and char.isascii():
            chars.append(char)
        else:
            chars.append("-")

    slug = re.sub(r"-+", "-", "".join(chars)).strip("-")
    return slug or "news"


def _unique_slug(conn, slug: str, exclude_id: int | None = None) -> str:
    """Добавляет -2, -3, … пока slug не станет уникальным."""
    base = slug
    index = 1

    while True:
        row = conn.execute(
            "SELECT id FROM news WHERE slug = %s",
            (slug,),
        ).fetchone()

        if row is None or (exclude_id is not None and row[0] == exclude_id):
            return slug

        index += 1
        slug = f"{base}-{index}"


def _unique_category_slug(conn, slug: str, exclude_id: int | None = None) -> str:
    base = slug
    index = 1

    while True:
        row = conn.execute(
            "SELECT id FROM news_categories WHERE slug = %s",
            (slug,),
        ).fetchone()

        if row is None or (exclude_id is not None and row[0] == exclude_id):
            return slug

        index += 1
        slug = f"{base}-{index}"


def _parse_datetime(value: Any) -> datetime | None:
    value = _clean(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Некорректная дата публикации")


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _news_row(row) -> dict:
    (
        news_id,
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
        "slug": slug,
        "title": title,
        "excerpt": excerpt or "",
        "content": content or "",
        "category_id": category_id,
        "category": (
            {
                "id": category_id,
                "name": category_name,
                "slug": category_slug,
            }
            if category_id is not None
            else None
        ),
        "published_at": _iso(published_at),
        "is_published": is_published,
        "is_featured": is_featured,
        "seo_title": seo_title or "",
        "seo_description": seo_description or "",
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
    }


def _category_row(row) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "slug": row[2],
        "sort_order": row[3],
        "is_active": row[4],
    }


def get_admin_news() -> dict:
    with get_connection() as conn:
        news_rows = conn.execute(
            """
            SELECT
                n.id, n.slug, n.title, n.excerpt, n.content,
                n.category_id, c.name, c.slug,
                n.published_at, n.is_published, n.is_featured,
                n.seo_title, n.seo_description,
                n.created_at, n.updated_at
            FROM news n
            LEFT JOIN news_categories c ON c.id = n.category_id
            ORDER BY n.published_at DESC NULLS LAST, n.id DESC
            """
        ).fetchall()

        category_rows = conn.execute(
            """
            SELECT id, name, slug, sort_order, is_active
            FROM news_categories
            ORDER BY sort_order, id
            """
        ).fetchall()

    return {
        "news": [_news_row(row) for row in news_rows],
        "categories": [_category_row(row) for row in category_rows],
    }


def _validate_category(conn, category_id: int | None) -> None:
    if category_id is None:
        return

    ok = conn.execute(
        "SELECT 1 FROM news_categories WHERE id = %s",
        (category_id,),
    ).fetchone()

    if not ok:
        raise ValueError("Указанная категория не найдена")


def create_news(
    *,
    title: str,
    content: str,
    excerpt: str | None = None,
    category_id: int | None = None,
    published_at: str | None = None,
    is_published: bool = False,
    is_featured: bool = False,
    seo_title: str | None = None,
    seo_description: str | None = None,
    slug: str | None = None,
) -> dict:
    title = _clean(title)
    content = _clean(content)

    if not title:
        raise ValueError("Не указан заголовок новости")
    if not content:
        raise ValueError("Не указан текст новости")

    published = _parse_datetime(published_at)

    with get_connection() as conn:
        with conn.transaction():
            _validate_category(conn, category_id)

            final_slug = _unique_slug(conn, _slugify(slug or title))

            if is_published and published is None:
                published = datetime.now().astimezone()

            row = conn.execute(
                """
                INSERT INTO news (
                    slug, title, excerpt, content, category_id,
                    published_at, is_published, is_featured,
                    seo_title, seo_description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    final_slug,
                    title,
                    _clean_or_none(excerpt),
                    content,
                    category_id,
                    published,
                    is_published,
                    is_featured,
                    _clean_or_none(seo_title),
                    _clean_or_none(seo_description),
                ),
            ).fetchone()

    return {"id": row[0], "slug": final_slug}


def update_news(
    news_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
    excerpt: str | None = None,
    category_id: int | None = None,
    published_at: str | None = None,
    is_published: bool | None = None,
    is_featured: bool | None = None,
    seo_title: str | None = None,
    seo_description: str | None = None,
    slug: str | None = None,
) -> dict:
    if title is not None:
        title = _clean(title)
        if not title:
            raise ValueError("Не указан заголовок новости")

    if content is not None:
        content = _clean(content)
        if not content:
            raise ValueError("Не указан текст новости")

    published = _parse_datetime(published_at)

    with get_connection() as conn:
        with conn.transaction():
            _validate_category(conn, category_id)

            updates = []
            values = []

            if title is not None:
                updates.append("title = %s")
                values.append(title)
            if content is not None:
                updates.append("content = %s")
                values.append(content)
            if excerpt is not None:
                updates.append("excerpt = %s")
                values.append(_clean_or_none(excerpt))
            if slug is not None and _clean(slug):
                updates.append("slug = %s")
                values.append(_unique_slug(conn, _slugify(slug), news_id))
            # category_id передаётся всегда (может быть NULL)
            updates.append("category_id = %s")
            values.append(category_id)
            if published is not None:
                updates.append("published_at = %s")
                values.append(published)
            if is_published is not None:
                updates.append("is_published = %s")
                values.append(is_published)
                if is_published and published is None:
                    updates.append("published_at = COALESCE(published_at, NOW())")
            if is_featured is not None:
                updates.append("is_featured = %s")
                values.append(is_featured)
            if seo_title is not None:
                updates.append("seo_title = %s")
                values.append(_clean_or_none(seo_title))
            if seo_description is not None:
                updates.append("seo_description = %s")
                values.append(_clean_or_none(seo_description))

            if not updates:
                raise ValueError("Нет данных для обновления")

            updates.append("updated_at = NOW()")

            conn.execute(
                f"""
                UPDATE news
                SET {', '.join(updates)}
                WHERE id = %s
                """,
                (*values, news_id),
            )

    return {"id": news_id}


def delete_news(news_id: int) -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM news WHERE id = %s", (news_id,))


def create_category(
    *,
    name: str,
    slug: str | None = None,
) -> dict:
    name = _clean(name)

    if not name:
        raise ValueError("Не указано название категории")

    with get_connection() as conn:
        with conn.transaction():
            existing = conn.execute(
                "SELECT 1 FROM news_categories WHERE name = %s",
                (name,),
            ).fetchone()

            if existing:
                raise ValueError("Категория с таким названием уже существует")

            final_slug = _unique_category_slug(conn, _slugify(slug or name))

            row = conn.execute(
                """
                INSERT INTO news_categories (name, slug, sort_order)
                VALUES (
                    %s, %s,
                    COALESCE(
                        (SELECT MAX(sort_order) + 10 FROM news_categories),
                        10
                    )
                )
                RETURNING id, name, slug
                """,
                (name, final_slug),
            ).fetchone()

    return {"category": {"id": row[0], "name": row[1], "slug": row[2]}}
