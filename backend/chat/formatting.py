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


def format_area_answer(places: list[str], items: list[dict[str, Any]]) -> str:
    """Простой ответ для поиска вокруг населённого пункта.

    Только название пункта, количество вариантов и сами варианты —
    без источника координат, радиуса и LLM-фразировки.
    """
    lines: list[str] = []
    if places:
        lines.append(", ".join(dict.fromkeys(places)))

    count = len(items)
    mod10, mod100 = count % 10, count % 100
    if mod10 == 1 and mod100 != 11:
        word = "вариант"
    elif 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        word = "варианта"
    else:
        word = "вариантов"
    lines.append(f"Найдено {count} {word}.")

    for index, item in enumerate(items, 1):
        address = (
            item.get("address")
            or item.get("name")
            or item.get("title")
            or "без адреса"
        )
        details: list[str] = []
        if item.get("side"):
            details.append(f"сторона {item['side']}")
        media = item.get("type") or item.get("media_type")
        if media:
            details.append(str(media))
        if item.get("size"):
            details.append(str(item["size"]))

        line = f"{index}. {address}"
        if details:
            line += " — " + ", ".join(details)
        if item.get("price") is not None:
            price = f"{int(item['price']):,}".replace(",", " ")
            line += f" — {price} ₽"
        lines.append(line)

    return "\n".join(lines)


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
