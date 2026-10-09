"""Админ-раздел «О компании».

Чтение и редактирование страницы ``pages`` со slug ``o-kompanii``,
её блоков (``page_blocks``), статистики (``page_stats``) и элементов
сети (``about_network_items``).

HTTP-слой (роутер, авторизация) живёт здесь, доступ к PostgreSQL —
напрямую через ``get_connection`` (как в ``admin_contacts``).
Публичный вывод страницы — ``backend/services/about_service.py``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from psycopg.types.json import Jsonb

from backend.services.auth_api import require_admin
from backend.services.data_service import get_connection


router = APIRouter(
    prefix="/api/admin/about",
    tags=["admin-about"],
)

PAGE_SLUG = "o-kompanii"


# ---------------------------------------------------------------- models


class PagePayload(BaseModel):
    title: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    is_published: bool | None = None


class BlockPayload(BaseModel):
    id: int | None = None
    block_key: str | None = None
    block_type: str | None = None
    eyebrow: str | None = None
    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    content: dict | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    # Медиа блока. `media_ids is None` — связи не трогаем (обновление только
    # текстовых полей), пустой список — удаляем все связи.
    media_ids: list[int] | None = None
    cover_media_id: int | None = None


class StatPayload(BaseModel):
    id: int | None = None
    value: str | None = None
    label: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class NetworkPayload(BaseModel):
    id: int | None = None
    item_type: str | None = None
    title: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class AboutUpdatePayload(BaseModel):
    page: PagePayload | None = None
    blocks: list[BlockPayload] | None = None
    stats: list[StatPayload] | None = None
    network: list[NetworkPayload] | None = None
    # Явный флаг: удалять ли записи, отсутствующие в payload.
    # По умолчанию — нет (MVP: только обновление/добавление).
    delete_missing: bool = False


# ---------------------------------------------------------------- helpers


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_or_none(value: Any) -> str | None:
    value = _clean(value)
    return value or None


def _page_id(conn) -> int:
    row = conn.execute(
        "SELECT id FROM pages WHERE slug = %s",
        (PAGE_SLUG,),
    ).fetchone()

    if row is None:
        raise ValueError(f"Страница '{PAGE_SLUG}' не найдена")

    return row[0]


def _unique_block_key(conn, page_id: int, base: str) -> str:
    base = _clean(base) or "block"

    rows = conn.execute(
        "SELECT block_key FROM page_blocks WHERE page_id = %s",
        (page_id,),
    ).fetchall()
    existing = {row[0] for row in rows}

    if base not in existing:
        return base

    index = 2
    while f"{base}-{index}" in existing:
        index += 1

    return f"{base}-{index}"


def _delete_missing(conn, table: str, page_id: int, keep_ids: list[int]) -> None:
    # table — внутренняя константа, не пользовательский ввод.
    if keep_ids:
        placeholders = ", ".join(["%s"] * len(keep_ids))
        conn.execute(
            f"DELETE FROM {table} WHERE page_id = %s AND id NOT IN ({placeholders})",
            (page_id, *keep_ids),
        )
    else:
        conn.execute(
            f"DELETE FROM {table} WHERE page_id = %s",
            (page_id,),
        )


# ---------------------------------------------------------------- media


# Сериализация медиа повторяет формат новостей
# (backend/services/news_admin_service.py::_media_item), чтобы фронт
# использовал один и тот же компонент для новостей и блоков страниц.
_MEDIA_SELECT = """
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
    FROM page_block_media pbm
    JOIN media m
        ON m.id = pbm.media_id
    WHERE pbm.block_id = %s
    ORDER BY pbm.sort_order, pbm.id
"""


def _media_item(row) -> dict:
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
        variants,
        preview_path,
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
        "variants": variants or [],
        "preview_path": preview_path,
    }


def _valid_media_ids(conn, media_ids) -> list[int]:
    """Схлопывает дубликаты (первое вхождение) и отбрасывает
    несуществующие в таблице media id, сохраняя порядок."""
    ordered: list[int] = []
    seen: set[int] = set()

    for media_id in media_ids:
        if media_id is None or media_id in seen:
            continue
        seen.add(media_id)
        ordered.append(media_id)

    if not ordered:
        return []

    rows = conn.execute(
        "SELECT id FROM media WHERE id = ANY(%s)",
        (ordered,),
    ).fetchall()

    existing = {row[0] for row in rows}
    return [media_id for media_id in ordered if media_id in existing]


def _sync_block_media(
    conn,
    block_id: int,
    media_ids: list[int] | None,
    cover_media_id: int | None,
) -> None:
    """Полная синхронизация связей блока с медиа.

    `media_ids is None` — связи не трогаем. Пустой список или список,
    состоящий только из несуществующих id, — удаляем все связи.
    """
    if media_ids is None:
        return

    conn.execute(
        "DELETE FROM page_block_media WHERE block_id = %s",
        (block_id,),
    )

    valid_ids = _valid_media_ids(conn, media_ids)
    if not valid_ids:
        return

    cover = cover_media_id if cover_media_id in valid_ids else valid_ids[0]

    for index, media_id in enumerate(valid_ids):
        conn.execute(
            """
            INSERT INTO page_block_media (
                block_id, media_id, role, sort_order, is_cover
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (block_id, media_id, "photo", index, media_id == cover),
        )


# ---------------------------------------------------------------- read


def get_admin_about() -> dict:
    with get_connection() as conn:
        page_id = _page_id(conn)

        page = conn.execute(
            """
            SELECT id, slug, title, seo_title, seo_description, is_published
            FROM pages
            WHERE id = %s
            """,
            (page_id,),
        ).fetchone()

        blocks = conn.execute(
            """
            SELECT id, block_key, block_type, eyebrow, title, subtitle,
                   body, content, sort_order, is_active
            FROM page_blocks
            WHERE page_id = %s
            ORDER BY sort_order, id
            """,
            (page_id,),
        ).fetchall()

        block_items = []
        for row in blocks:
            media_rows = conn.execute(_MEDIA_SELECT, (row[0],)).fetchall()
            block_items.append(
                {
                    "id": row[0],
                    "block_key": row[1],
                    "block_type": row[2],
                    "eyebrow": row[3] or "",
                    "title": row[4] or "",
                    "subtitle": row[5] or "",
                    "body": row[6] or "",
                    "content": row[7] or {},
                    "sort_order": row[8],
                    "is_active": row[9],
                    "media": [_media_item(media) for media in media_rows],
                }
            )

        stats = conn.execute(
            """
            SELECT id, value, label, sort_order, is_active
            FROM page_stats
            WHERE page_id = %s
            ORDER BY sort_order, id
            """,
            (page_id,),
        ).fetchall()

        network = conn.execute(
            """
            SELECT id, item_type, title, sort_order, is_active
            FROM about_network_items
            WHERE page_id = %s
            ORDER BY sort_order, id
            """,
            (page_id,),
        ).fetchall()

    return {
        "page": {
            "id": page[0],
            "slug": page[1],
            "title": page[2] or "",
            "seo_title": page[3] or "",
            "seo_description": page[4] or "",
            "is_published": page[5],
        },
        "blocks": block_items,
        "stats": [
            {
                "id": row[0],
                "value": row[1] or "",
                "label": row[2] or "",
                "sort_order": row[3],
                "is_active": row[4],
            }
            for row in stats
        ],
        "network": [
            {
                "id": row[0],
                "item_type": row[1],
                "title": row[2] or "",
                "sort_order": row[3],
                "is_active": row[4],
            }
            for row in network
        ],
    }


# ---------------------------------------------------------------- update


def _update_page(conn, page_id: int, page: PagePayload) -> None:
    fields = []
    values: list[Any] = []

    if page.title is not None:
        fields.append("title = %s")
        values.append(_clean(page.title))
    if page.seo_title is not None:
        fields.append("seo_title = %s")
        values.append(_clean_or_none(page.seo_title))
    if page.seo_description is not None:
        fields.append("seo_description = %s")
        values.append(_clean_or_none(page.seo_description))
    if page.is_published is not None:
        fields.append("is_published = %s")
        values.append(page.is_published)

    if not fields:
        return

    fields.append("updated_at = NOW()")
    conn.execute(
        f"UPDATE pages SET {', '.join(fields)} WHERE id = %s",
        (*values, page_id),
    )


def _sync_blocks(
    conn,
    page_id: int,
    blocks: list[BlockPayload],
    delete_missing: bool,
) -> None:
    keep_ids: list[int] = []

    for index, block in enumerate(blocks):
        sort_order = (
            block.sort_order if block.sort_order is not None else (index + 1) * 10
        )
        is_active = True if block.is_active is None else block.is_active
        content = Jsonb(block.content or {})

        if block.id:
            # Обновляем только запись этой страницы.
            conn.execute(
                """
                UPDATE page_blocks
                SET eyebrow = %s, title = %s, subtitle = %s, body = %s,
                    content = %s, sort_order = %s, is_active = %s,
                    updated_at = NOW()
                WHERE id = %s AND page_id = %s
                """,
                (
                    _clean_or_none(block.eyebrow),
                    _clean_or_none(block.title),
                    _clean_or_none(block.subtitle),
                    _clean_or_none(block.body),
                    content,
                    sort_order,
                    is_active,
                    block.id,
                    page_id,
                ),
            )
            keep_ids.append(block.id)
            _sync_block_media(
                conn, block.id, block.media_ids, block.cover_media_id
            )
            continue

        block_type = _clean(block.block_type) or "text"
        block_key = _unique_block_key(
            conn,
            page_id,
            _clean(block.block_key) or block_type,
        )

        row = conn.execute(
            """
            INSERT INTO page_blocks (
                page_id, block_key, block_type, eyebrow, title, subtitle,
                body, content, sort_order, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                page_id,
                block_key,
                block_type,
                _clean_or_none(block.eyebrow),
                _clean_or_none(block.title),
                _clean_or_none(block.subtitle),
                _clean_or_none(block.body),
                content,
                sort_order,
                is_active,
            ),
        ).fetchone()
        keep_ids.append(row[0])
        _sync_block_media(
            conn, row[0], block.media_ids, block.cover_media_id
        )

    if delete_missing:
        _delete_missing(conn, "page_blocks", page_id, keep_ids)


def _sync_stats(
    conn,
    page_id: int,
    stats: list[StatPayload],
    delete_missing: bool,
) -> None:
    keep_ids: list[int] = []

    for index, stat in enumerate(stats):
        sort_order = (
            stat.sort_order if stat.sort_order is not None else (index + 1) * 10
        )
        is_active = True if stat.is_active is None else stat.is_active

        if stat.id:
            conn.execute(
                """
                UPDATE page_stats
                SET value = %s, label = %s, sort_order = %s,
                    is_active = %s, updated_at = NOW()
                WHERE id = %s AND page_id = %s
                """,
                (
                    _clean(stat.value),
                    _clean(stat.label),
                    sort_order,
                    is_active,
                    stat.id,
                    page_id,
                ),
            )
            keep_ids.append(stat.id)
            continue

        value = _clean(stat.value)
        label = _clean(stat.label)

        if not value and not label:
            # Пустую новую строку не сохраняем.
            continue

        row = conn.execute(
            """
            INSERT INTO page_stats (page_id, value, label, sort_order, is_active)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (page_id, value, label, sort_order, is_active),
        ).fetchone()
        keep_ids.append(row[0])

    if delete_missing:
        _delete_missing(conn, "page_stats", page_id, keep_ids)


def _sync_network(
    conn,
    page_id: int,
    network: list[NetworkPayload],
    delete_missing: bool,
) -> None:
    keep_ids: list[int] = []

    for index, item in enumerate(network):
        sort_order = (
            item.sort_order if item.sort_order is not None else (index + 1) * 10
        )
        is_active = True if item.is_active is None else item.is_active

        if item.id:
            conn.execute(
                """
                UPDATE about_network_items
                SET item_type = %s, title = %s, sort_order = %s,
                    is_active = %s, updated_at = NOW()
                WHERE id = %s AND page_id = %s
                """,
                (
                    _clean(item.item_type) or "city",
                    _clean(item.title),
                    sort_order,
                    is_active,
                    item.id,
                    page_id,
                ),
            )
            keep_ids.append(item.id)
            continue

        title = _clean(item.title)

        if not title:
            # Пустую новую строку не сохраняем.
            continue

        row = conn.execute(
            """
            INSERT INTO about_network_items (
                page_id, item_type, title, sort_order, is_active
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                page_id,
                _clean(item.item_type) or "city",
                title,
                sort_order,
                is_active,
            ),
        ).fetchone()
        keep_ids.append(row[0])

    if delete_missing:
        _delete_missing(conn, "about_network_items", page_id, keep_ids)


def update_admin_about(
    *,
    page: PagePayload | None = None,
    blocks: list[BlockPayload] | None = None,
    stats: list[StatPayload] | None = None,
    network: list[NetworkPayload] | None = None,
    delete_missing: bool = False,
) -> None:
    with get_connection() as conn:
        with conn.transaction():
            page_id = _page_id(conn)

            if page is not None:
                _update_page(conn, page_id, page)

            if blocks is not None:
                _sync_blocks(conn, page_id, blocks, delete_missing)

            if stats is not None:
                _sync_stats(conn, page_id, stats, delete_missing)

            if network is not None:
                _sync_network(conn, page_id, network, delete_missing)


# ---------------------------------------------------------------- routes


@router.get("")
def admin_get_about(auth=Depends(require_admin)):
    try:
        return {"success": True, **get_admin_about()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("")
def admin_update_about(
    payload: AboutUpdatePayload,
    auth=Depends(require_admin),
):
    try:
        update_admin_about(
            page=payload.page,
            blocks=payload.blocks,
            stats=payload.stats,
            network=payload.network,
            delete_missing=payload.delete_missing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"success": True, **get_admin_about()}
