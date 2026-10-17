"""Shared rich-result presenter for search v1 and v2.

Both versions must return exactly the same JSON shape; keeping the mapping
and sorting here avoids drift between the SQL bridge and the in-process
catalog.
"""

from __future__ import annotations

from typing import Any, Iterable

from engine.query.query import SearchQuery
from engine.storage.models import AvailabilityRecord, SurfaceRecord


def primary_month(
    query: SearchQuery,
    availability: Iterable[AvailabilityRecord],
) -> int | None:
    records = list(availability)

    if query.month is not None:
        return query.month

    months = query.get_months()
    if months:
        # Show the first month the user actually asked for, not the earliest
        # month present in the yearly data.
        return months[0]

    return min((item.month for item in records), default=None)


def rich_item(
    surface: SurfaceRecord,
    availability: list[AvailabilityRecord],
    query: SearchQuery,
) -> dict[str, Any]:
    monthly: dict[str, dict[str, Any]] = {}
    monthly_prices: dict[int, int | None] = {}
    monthly_statuses: dict[int, str | None] = {}
    monthly_loads: dict[int, int | None] = {}
    month_texts: dict[int, str | None] = {}

    for item in availability:
        monthly[item.month] = {
            "price": item.price,
            "status": item.status,
            "load_percent": item.load_percent,
            "raw_value": item.raw_value,
        }
        monthly_prices[item.month] = item.price
        monthly_statuses[item.month] = item.status
        monthly_loads[item.month] = item.load_percent
        month_texts[item.month] = item.raw_value

    selected_month = primary_month(query, availability)
    selected = next(
        (item for item in availability if item.month == selected_month),
        None,
    )
    metadata = surface.metadata or {}
    price = (
        selected.price
        if selected and selected.price is not None
        else surface.price
    )

    selected_load = selected.load_percent if selected else None

    if query.sort_by == "load_asc" and len(query.get_months()) > 1:
        requested = set(query.get_months())
        loads = [
            item.load_percent
            for item in availability
            if item.month in requested and item.load_percent is not None
        ]
        selected_load = round(sum(loads) / len(loads)) if loads else None

    return {
        "id": surface.id or 0,
        "external_id": surface.external_id,
        "city": surface.city,
        "district": surface.district,
        "address": surface.address,
        "name": surface.title,
        "title": surface.title,
        "side": surface.side,
        "type": metadata.get("type") or surface.media_type,
        "media_type": surface.media_type,
        "size": surface.size,
        "lat": surface.latitude,
        "lng": surface.longitude,
        "latitude": surface.latitude,
        "longitude": surface.longitude,
        "light": surface.light,
        "material": surface.material,
        "price": price,
        "load_percent": selected_load,
        "status": selected.status if selected else None,
        "raw_value": selected.raw_value if selected else None,
        "monthly": monthly,
        "monthly_prices": monthly_prices,
        "monthly_statuses": monthly_statuses,
        "monthly_loads": monthly_loads,
        "month_texts": month_texts,
        "photo": metadata.get("photo") or surface.photo_url,
        "photo_url": surface.photo_url,
        "photo_thumb": metadata.get("photo_thumb"),
        "photo_large": metadata.get("photo_large") or surface.photo_url,
        "map": metadata.get("map") or surface.map_url,
        "map_thumb": metadata.get("map_thumb"),
        "map_card": metadata.get("map_card"),
        "map_large": metadata.get("map_large") or surface.map_url,
    }


def alphabetical(value: Any) -> str:
    """Case-insensitive, whitespace-collapsed key for tie ordering."""
    return " ".join(str(value or "").casefold().replace("ё", "е").split())


def sort_and_limit(
    items: list[dict[str, Any]],
    query: SearchQuery,
) -> list[dict[str, Any]]:
    def tail(item: dict[str, Any]):
        return (
            alphabetical(item.get("city")),
            alphabetical(item.get("address")),
            alphabetical(item.get("side")),
            item.get("id") or 0,
        )

    if query.sort_by == "price_asc":
        items.sort(
            key=lambda item: (
                item["price"] is None,
                item["price"] if item["price"] is not None else 0,
                *tail(item),
            )
        )
    elif query.sort_by == "load_asc":
        items.sort(
            key=lambda item: (
                item["load_percent"] is None,
                item["load_percent"]
                if item["load_percent"] is not None
                else 101,
                *tail(item),
            )
        )

    if query.limit is not None:
        return items[: query.limit]

    return items
