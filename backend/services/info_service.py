"""Закладки страницы «Информация» и geo-данные для закладки «Города и районы».

Публичная часть отдаёт только активные закладки; для закладки вида `geo`
дополнительно подмешивается geo-контент главной (города/районы и их
описания), чтобы страница обходилась одним запросом.
"""
from __future__ import annotations

from typing import Any

from backend.services.data_service import get_connection


TAB_KINDS = ("text", "geo")


def _tab_dict(row) -> dict:
    (
        tab_id,
        title,
        kind,
        content,
        sort_order,
        is_active,
    ) = row

    return {
        "id": tab_id,
        "title": title or "",
        "kind": kind or "text",
        "content": content or "",
        "sort_order": sort_order,
        "is_active": is_active,
    }


def _load_tabs(conn) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, title, kind, content, sort_order, is_active
        FROM info_tabs
        ORDER BY sort_order, id
        """
    ).fetchall()

    return [_tab_dict(row) for row in rows]


def _location_sort_key(location: dict):
    """Ростов-на-Дону — первым, затем города, районы — в конце списка."""
    label = str(location.get("label") or "").strip()
    low = label.lower()

    is_rostov = low.startswith("ростов-на-дону")
    is_district = location.get("kind") == "district" or "район" in low

    if is_rostov:
        group = 0
    elif is_district:
        group = 2
    else:
        group = 1

    return (group, int(location.get("sort_order") or 0), low)


def get_public_info() -> dict:
    """Активные закладки + geo-данные, если есть закладка «Города и районы»."""
    with get_connection() as conn:
        tabs = [tab for tab in _load_tabs(conn) if tab["is_active"]]

    result: dict[str, Any] = {"tabs": tabs}

    if any(tab["kind"] == "geo" for tab in tabs):
        from backend.services.home_geo_service import get_public_geo

        geo = get_public_geo()
        geo["locations"] = sorted(
            geo.get("locations", []),
            key=_location_sort_key,
        )
        result["geo"] = geo

    return result


def get_admin_info() -> dict:
    """Все закладки для редактора админки (включая скрытые)."""
    with get_connection() as conn:
        return {"tabs": _load_tabs(conn)}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def save_tabs(items: list[dict] | None) -> dict:
    """Заменяет список закладок целиком (порядок = порядок в списке)."""
    items = items or []

    with get_connection() as conn:
        with conn.transaction():
            conn.execute("DELETE FROM info_tabs")

            for index, item in enumerate(items):
                title = _clean(item.get("title"))
                if not title:
                    raise ValueError("У закладки нет названия")

                kind = _clean(item.get("kind")) or "text"
                if kind not in TAB_KINDS:
                    raise ValueError(
                        f"Неизвестный тип закладки: {kind}"
                    )

                conn.execute(
                    """
                    INSERT INTO info_tabs
                        (title, kind, content, sort_order, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        title[:200],
                        kind,
                        str(item.get("content") or ""),
                        int(item.get("sort_order") or (index + 1) * 10),
                        bool(item.get("is_active", True)),
                    ),
                )

    return get_admin_info()
