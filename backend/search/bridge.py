from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from engine.query.query import SearchQuery
from engine.search.service import SearchService
from engine.storage.models import (
    AvailabilityRecord,
    SearchResultItem,
    SurfaceRecord,
)

from backend.search.repository import SitePostgreSQLSearchRepository


class AlbionSearchBridge:
    """Anti-Corruption Layer between the site schema and albion-search."""

    def __init__(
        self,
        repository: SitePostgreSQLSearchRepository | None = None,
    ) -> None:
        self.repository = repository or SitePostgreSQLSearchRepository()
        self.service = SearchService(self.repository)

    @staticmethod
    def _normalize_area(value: str | None) -> str:
        return (
            str(value or "")
            .strip()
            .casefold()
            .replace("ё", "е")
        )

    @classmethod
    def _matches_district(cls, surface: SurfaceRecord, expected: str) -> bool:
        """Districts in the site data live in the city/area name column.

        The site keeps administrative areas (e.g. "ОКТЯБРЬСКИЙ РАЙОН") as
        cities, and constructions.district mirrors that same value. Accept a
        match on either field so a district query keeps working after imports.
        """
        for candidate in (surface.city, surface.district):
            if expected in cls._normalize_area(candidate):
                return True
        return False

    @staticmethod
    def _location_terms(query: SearchQuery) -> list[str]:
        """Location words the user asked for (city and/or district)."""
        terms: list[str] = []
        for value in (query.city, query.district):
            normalized = AlbionSearchBridge._normalize_area(value)
            if normalized and normalized not in terms:
                terms.append(normalized)
        return terms

    @classmethod
    def _matches_location(cls, surface: SurfaceRecord, terms: list[str]) -> bool:
        """A location word may appear in the city, address or construction name.

        The user asked to look for it not only in the name/city column but also
        in the construction address and title, so match across all of them.
        """
        haystack = [
            surface.city,
            surface.district,
            surface.address,
            surface.title,
        ]
        for field in haystack:
            normalized = cls._normalize_area(field)
            if not normalized:
                continue
            for term in terms:
                if term in normalized:
                    return True
        return False

    def _surfaces(self, query: SearchQuery) -> list[SurfaceRecord]:
        if not isinstance(query, SearchQuery):
            raise TypeError("AlbionSearchBridge.search() ожидает SearchQuery")

        terms = self._location_terms(query)

        # The location word is matched across cities, address and title, so
        # relax the SQL city restriction and apply the broader OR filter here.
        effective = (
            replace(query, city=None, district=None)
            if terms
            else query
        )

        surfaces = self.service.search(effective)

        if terms:
            surfaces = [
                surface
                for surface in surfaces
                if self._matches_location(surface, terms)
            ]

        return surfaces

    def _availability(
        self,
        surfaces: list[SurfaceRecord],
        query: SearchQuery,
    ) -> dict[int, list[AvailabilityRecord]]:
        ids = [surface.id for surface in surfaces if surface.id is not None]
        if not ids:
            return {}

        # Fetch availability for ALL months of the year, not only the queried
        # one: otherwise the card would show "free" for months it never
        # loaded, i.e. incorrect occupancy for the other months.
        return self.repository.get_availabilities_for_surfaces(
            surface_ids=ids,
            year=query.year,
            months=None,
        )

    @staticmethod
    def _primary_month(
        query: SearchQuery,
        availability: Iterable[AvailabilityRecord],
    ) -> int | None:
        records = list(availability)
        if query.month is not None:
            return query.month

        months = query.get_months()
        if len(months) == 1:
            return months[0]

        return min((item.month for item in records), default=None)

    @classmethod
    def _rich_item(
        cls,
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

        primary_month = cls._primary_month(query, availability)
        selected = next(
            (item for item in availability if item.month == primary_month),
            None,
        )
        metadata = surface.metadata or {}
        price = selected.price if selected and selected.price is not None else surface.price

        selected_load = selected.load_percent if selected else None
        if query.sort_by == "load_asc" and len(query.get_months()) > 1:
            loads = [
                item.load_percent
                for item in availability
                if item.month in query.get_months()
                and item.load_percent is not None
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

    @staticmethod
    def _alphabetical(value: Any) -> str:
        """Case-insensitive, whitespace-collapsed key for tie ordering."""
        return " ".join(
            str(value or "").casefold().replace("ё", "е").split()
        )

    @classmethod
    def _sort_and_limit(
        cls,
        items: list[dict[str, Any]],
        query: SearchQuery,
    ) -> list[dict[str, Any]]:
        # Equal percentage/price items must fall back to alphabetical order.
        def tail(item: dict[str, Any]):
            return (
                cls._alphabetical(item.get("city")),
                cls._alphabetical(item.get("address")),
                cls._alphabetical(item.get("side")),
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

    def search_rich(self, query: SearchQuery) -> list[dict[str, Any]]:
        surfaces = self._surfaces(query)
        availability = self._availability(surfaces, query)
        items = [
            self._rich_item(surface, availability.get(surface.id, []), query)
            for surface in surfaces
        ]
        return self._sort_and_limit(items, query)

    def search(self, query: SearchQuery) -> list[SearchResultItem]:
        """Execute structured search while retaining the old DTO contract."""
        rich_items = self.search_rich(query)
        return [
            SearchResultItem(
                id=int(item["id"]),
                external_id=item.get("external_id"),
                city=item.get("city"),
                address=item.get("address"),
                side=item.get("side"),
                media_type=item.get("media_type"),
                size=item.get("size"),
                price=item.get("price"),
                load_percent=item.get("load_percent"),
                status=item.get("status"),
                raw_value=item.get("raw_value"),
                photo_url=item.get("photo_url"),
                monthly_prices=item.get("monthly_prices", {}),
                monthly_statuses=item.get("monthly_statuses", {}),
            )
            for item in rich_items
        ]
