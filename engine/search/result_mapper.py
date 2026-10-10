from __future__ import annotations

from engine.storage.models import SearchResultItem
from engine.storage.models import (
    AvailabilityRecord,
    SurfaceRecord,
)


class SearchResultMapper:
    """
    Преобразует storage-independent engine records
    в существующий API DTO SearchResultItem.

    ВАЖНО:
    этот mapper является границей между новым engine
    и существующим HTTP/API контрактом.
    """

    @staticmethod
    def map(
        surface: SurfaceRecord,
        availability: AvailabilityRecord | None = None,
        monthly_availabilities: list[AvailabilityRecord] | None = None,
    ) -> SearchResultItem:

        monthly_prices: dict[int, int | None] = {}
        monthly_statuses: dict[int, str | None] = {}

        for item in monthly_availabilities or []:
            monthly_prices[item.month] = item.price
            monthly_statuses[item.month] = item.status

        if availability is not None:
            monthly_prices.setdefault(
                availability.month,
                availability.price,
            )
            monthly_statuses.setdefault(
                availability.month,
                availability.status,
            )

        # Если availability не задана, используем
        # базовую цену самой поверхности.
        price = (
            availability.price
            if availability is not None
            else surface.price
        )

        return SearchResultItem(
            id=surface.id,
            external_id=surface.external_id,
            city=surface.city,
            address=surface.address,
            side=surface.side,
            media_type=surface.media_type,
            size=surface.size,
            price=price,
            load_percent=(
                availability.load_percent
                if availability is not None
                else None
            ),
            status=(
                availability.status
                if availability is not None
                else None
            ),
            raw_value=(
                availability.raw_value
                if availability is not None
                else None
            ),
            photo_url=surface.photo_url,
            monthly_prices=monthly_prices,
            monthly_statuses=monthly_statuses,
        )

    @classmethod
    def map_many(
        cls,
        surfaces: list[SurfaceRecord],
        *,
        availabilities: dict[
            int,
            list[AvailabilityRecord],
        ] | None = None,
        primary_month: int | None = None,
    ) -> list[SearchResultItem]:

        availabilities = availabilities or {}

        result: list[SearchResultItem] = []

        for surface in surfaces:
            items = availabilities.get(surface.id, [])

            primary = None

            if primary_month is not None:
                primary = next(
                    (
                        item
                        for item in items
                        if item.month == primary_month
                    ),
                    None,
                )

            result.append(
                cls.map(
                    surface,
                    availability=primary,
                    monthly_availabilities=items,
                )
            )

        return result
