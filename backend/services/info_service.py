"""Закладки страницы «Информация» и geo-данные для закладки «Города и районы».

Публичная часть отдаёт только активные закладки; для закладки вида `geo`
дополнительно подмешивается geo-контент главной (города/районы и их
описания), чтобы страница обходилась одним запросом.

Для закладки `traffic-light` поле `content` хранит JSON:
  {
    "image_url": "url изображения светофора",
    "text": "основной текст",
    "photos": [{"url": "...", "label": "..."}, ...]
  }
"""
from __future__ import annotations

import json
from typing import Any

from backend.services.data_service import get_connection


TAB_KINDS = ("text", "geo", "traffic-light")


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


def _parse_traffic_light_content(content_text: str) -> dict:
    """Парсит JSON-контент закладки traffic-light.

    Возвращает:
      {
        "image_url": str | None,
        "custom_html": str,
        "text": str,
        "photos": [{"url": str, "label": str}, ...]
      }
    """
    text = content_text.strip()
    if not text:
        return {
            "image_url": None,
            "custom_html": "",
            "text": "",
            "photos": [],
        }

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Если не JSON — считаем весь текст обычным текстом.
        return {
            "image_url": None,
            "custom_html": "",
            "text": text,
            "photos": [],
        }

    if not isinstance(data, dict):
        return {
            "image_url": None,
            "custom_html": "",
            "text": str(data),
            "photos": [],
        }

    image_url = data.get("image_url") or None
    custom_html = data.get("custom_html") or ""
    text_content = data.get("text") or ""
    photos_raw = data.get("photos") or []

    photos = []
    for p in photos_raw:
        if isinstance(p, dict):
            url = p.get("url") or ""
            if url:
                photos.append({
                    "url": str(url),
                    "label": str(p.get("label") or ""),
                })

    return {
        "image_url": str(image_url) if image_url else None,
        "custom_html": str(custom_html),
        "text": str(text_content),
        "photos": photos,
    }


def _build_traffic_light_content(data: dict) -> str:
    """Сериализует данные traffic-light в JSON-строку для поля content."""
    return json.dumps(
        {
            "image_url": data.get("image_url") or "",
            "custom_html": data.get("custom_html") or "",
            "text": data.get("text") or "",
            "photos": data.get("photos") or [],
        },
        ensure_ascii=False,
        indent=2,
    )


def save_tabs(items: list[dict] | None) -> dict:
    """Сохраняет список закладок.

    Существующие закладки обновляются по `id` (их идентификаторы не
    меняются, поэтому ссылки вида /informaciya?tab=<id> продолжают
    работать). Новые вставляются, отсутствующие в payload — удаляются.
    Порядок задаётся `sort_order`.
    """
    items = items or []

    with get_connection() as conn:
        with conn.transaction():
            keep_ids: list[int] = []

            for index, item in enumerate(items):
                title = _clean(item.get("title"))
                if not title:
                    raise ValueError("У закладки нет названия")

                kind = _clean(item.get("kind")) or "text"
                if kind not in TAB_KINDS:
                    raise ValueError(
                        f"Неизвестный тип закладки: {kind}"
                    )

                content = str(item.get("content") or "")

                # Для traffic-light — парсим JSON и пересобираем.
                if kind == "traffic-light":
                    parsed = _parse_traffic_light_content(content)
                    # Обновляем поля из payload, если переданы.
                    if "image_url" in item:
                        parsed["image_url"] = str(item["image_url"]) or None
                    if "custom_html" in item:
                        parsed["custom_html"] = str(item["custom_html"] or "")
                    if "text" in item:
                        parsed["text"] = str(item["text"])
                    if "photos" in item:
                        parsed["photos"] = [
                            {
                                "url": str(p.get("url", "")),
                                "label": str(p.get("label", "")),
                            }
                            for p in item["photos"]
                            if p.get("url")
                        ]
                    content = _build_traffic_light_content(parsed)

                sort_order = int(item.get("sort_order") or (index + 1) * 10)
                is_active = bool(item.get("is_active", True))
                tab_id = item.get("id")

                if tab_id:
                    conn.execute(
                        """
                        UPDATE info_tabs
                        SET title = %s, kind = %s, content = %s,
                            sort_order = %s, is_active = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            title[:200],
                            kind,
                            content,
                            sort_order,
                            is_active,
                            int(tab_id),
                        ),
                    )
                    keep_ids.append(int(tab_id))
                    continue

                row = conn.execute(
                    """
                    INSERT INTO info_tabs
                        (title, kind, content, sort_order, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (title[:200], kind, content, sort_order, is_active),
                ).fetchone()
                keep_ids.append(row[0])

            # Удаляем закладки, которых нет в payload.
            if keep_ids:
                placeholders = ", ".join(["%s"] * len(keep_ids))
                conn.execute(
                    f"DELETE FROM info_tabs WHERE id NOT IN ({placeholders})",
                    tuple(keep_ids),
                )
            else:
                conn.execute("DELETE FROM info_tabs")

    return get_admin_info()
