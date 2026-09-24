from __future__ import annotations

from typing import Iterable

from engine.query.query import SearchQuery
from engine.search.service import SearchService
from engine.storage.models import SearchResultItem, SurfaceRecord

from backend.search.repository import SitePostgreSQLSearchRepository


class AlbionSearchBridge:
    """
    Anti-Corruption Layer между сайтом и portable albion-search.

    Сайт работает через SearchQuery/SearchResultItem,
    а схема PostgreSQL сайта преобразуется repository/mapper-слоем.
    """

    def __init__(
        self,
        repository: SitePostgreSQLSearchRepository | None = None,
    ) -> None:
        self.repository = repository or SitePostgreSQLSearchRepository()
        self.service = SearchService(self.repository)

    def search(self, query: SearchQuery) -> list[SearchResultItem]:
        if not isinstance(query, SearchQuery):
            raise TypeError(
                "AlbionSearchBridge.search() ожидает SearchQuery"
            )

        surfaces = self.service.search(query)

        if not surfaces:
            return []

        surface_ids = [
            surface.id
            for surface in surfaces
            if surface.id is not None
        ]

        if not surface_ids:
            return [
                self._to_result_item(surface, {})
                for surface in surfaces
            ]

        months = query.get_months()

        availability = self.repository.get_availabilities_for_surfaces(
            surface_ids=surface_ids,
            year=query.year,
            months=months or None,
        )

        return [
            self._to_result_item(
                surface,
                availability.get(surface.id, []),
            )
            for surface in surfaces
        ]

    @staticmethod
    def _to_result_item(
        surface: SurfaceRecord,
        availability: Iterable,
    ) -> SearchResultItem:
        monthly_prices: dict[int, int | None] = {}
        monthly_statuses: dict[int, str | None] = {}

        for item in availability:
            monthly_prices[item.month] = item.price
            monthly_statuses[item.month] = item.status

        selected_month = None
        if monthly_statuses:
            selected_month = min(monthly_statuses)

        return SearchResultItem(
            id=surface.id if surface.id is not None else 0,
            external_id=surface.external_id,
            city=surface.city,
            address=surface.address,
            side=surface.side,
            media_type=surface.media_type,
            size=surface.size,
            price=surface.price,
            load_percent=None,
            status=(
                monthly_statuses.get(selected_month)
                if selected_month is not None
                else None
            ),
            raw_value=None,
            photo_url=surface.photo_url,
            monthly_prices=monthly_prices,
            monthly_statuses=monthly_statuses,
        )
