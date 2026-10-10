from __future__ import annotations

from typing import Any

MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


def _period(query: Any) -> str:
    months = query.get_months()
    if not months:
        return str(query.year)
    names = [MONTH_NAMES.get(month, str(month)) for month in months]
    return ", ".join(names) + f" {query.year}"


def format_answer(query: Any, items: list[dict[str, Any]]) -> str:
    count = len(items)
    subject = query.media_type or "рекламных конструкций"
    if query.district:
        subject += f" в районе {query.district}"
    elif query.city:
        subject += f" в городе {query.city}"

    if query.availability == "FREE":
        subject = f"свободных {subject}"

    if query.sort_by == "load_asc":
        return (
            f"Найдено {count} {subject} с наименьшей загрузкой "
            f"за {_period(query)}."
        )

    if query.address and items and query.min_price is None and query.max_price is None:
        prices = [item.get("price") for item in items if item.get("price") is not None]
        if prices:
            if len(set(prices)) == 1:
                return (
                    f"Цена {subject} по адресу {query.address}: "
                    f"{prices[0]:,}".replace(",", " ") + " ₽."
                )
            low, high = min(prices), max(prices)
            return (
                f"Цена {subject} по адресу {query.address}: "
                f"от {low:,}".replace(",", " ")
                + f" до {high:,}".replace(",", " ") + " ₽."
            )
        return f"По адресу {query.address} найдено {count} вариантов {subject}."

    return f"Найдено {count} {subject} за {_period(query)}."


def actions_for(items: list[dict[str, Any]]) -> dict[str, Any]:
    ids = [int(item["id"]) for item in items if item.get("id") is not None]
    has_coordinates = any(
        item.get("lat") is not None and item.get("lng") is not None
        for item in items
    )
    has_media = any(
        item.get("photo")
        or item.get("photo_large")
        or item.get("map_large")
        for item in items
    )
    return {
        "map": {
            "available": has_coordinates,
            "item_ids": ids,
            "reason": None if has_coordinates else "У результатов нет координат",
        },
        "list": {"available": bool(items)},
        "media": {"available": has_media, "item_ids": ids},
        "portfolio": {"available": bool(items), "item_ids": ids},
        "export": {
            "available": bool(items),
            "formats": ["xlsx", "docx", "pdf"],
        },
    }
