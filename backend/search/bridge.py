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

from backend.search.presenter import (
    alphabetical,
    primary_month,
    rich_item,
    sort_and_limit,
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
        return primary_month(query, availability)

    @classmethod
    def _rich_item(
        cls,
        surface: SurfaceRecord,
        availability: list[AvailabilityRecord],
        query: SearchQuery,
    ) -> dict[str, Any]:
        return rich_item(surface, availability, query)

    @staticmethod
    def _alphabetical(value: Any) -> str:
        return alphabetical(value)

    @classmethod
    def _sort_and_limit(
        cls,
        items: list[dict[str, Any]],
        query: SearchQuery,
    ) -> list[dict[str, Any]]:
        return sort_and_limit(items, query)

    def search_rich(self, query: SearchQuery) -> list[dict[str, Any]]:
        if query.year is None:
            from datetime import date

            resolver = getattr(self.repository, "default_year", None)
            year = resolver() if callable(resolver) else date.today().year
            query = replace(query, year=year)

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
