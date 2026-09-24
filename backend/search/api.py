from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.query.query import SearchQuery
from engine.storage.models import SearchResultItem

from backend.search.bridge import AlbionSearchBridge


class SearchRequest(BaseModel):
    """HTTP request model for Albion search."""

    model_config = ConfigDict(extra="forbid")

    city: str | None = None
    address: str | None = None

    media_type: str | None = None
    size: str | None = None

    year: int = 2026

    month: int | None = Field(default=None, ge=1, le=12)
    months: list[int] = Field(default_factory=list)

    period_mode: str = "ANY"

    availability: str | None = None

    load_threshold: int | None = Field(default=None, ge=0, le=100)
    max_load: int | None = Field(default=None, ge=0, le=100)

    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)

    sort_by: str | None = None
    limit: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_period(self) -> "SearchRequest":
        if self.month is not None and self.months:
            raise ValueError(
                "Нельзя одновременно задавать month и months"
            )

        for month in self.months:
            if not 1 <= month <= 12:
                raise ValueError(
                    f"Некорректный месяц: {month}"
                )

        if self.period_mode not in {"ANY", "ALL"}:
            raise ValueError(
                "period_mode должен быть ANY или ALL"
            )

        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                "min_price не может быть больше max_price"
            )

        return self

    def to_search_query(self) -> SearchQuery:
        return SearchQuery(
            city=self.city,
            address=self.address,
            media_type=self.media_type,
            size=self.size,
            year=self.year,
            month=self.month,
            months=list(self.months),
            period_mode=self.period_mode,
            availability=self.availability,
            load_threshold=self.load_threshold,
            max_load=self.max_load,
            min_price=self.min_price,
            max_price=self.max_price,
            sort_by=self.sort_by,
            limit=self.limit,
        )


class SearchResult(BaseModel):
    """HTTP representation of one search result."""

    id: int
    external_id: str | None = None
    city: str | None = None
    address: str | None = None
    side: str | None = None
    media_type: str | None = None
    size: str | None = None

    price: int | None = None
    load_percent: int | None = None
    status: str | None = None
    raw_value: str | None = None
    photo_url: str | None = None

    monthly_prices: dict[int, int | None] = Field(
        default_factory=dict
    )
    monthly_statuses: dict[int, str | None] = Field(
        default_factory=dict
    )

    @classmethod
    def from_item(cls, item: SearchResultItem) -> "SearchResult":
        return cls(
            id=item.id,
            external_id=item.external_id,
            city=item.city,
            address=item.address,
            side=item.side,
            media_type=item.media_type,
            size=item.size,
            price=item.price,
            load_percent=item.load_percent,
            status=item.status,
            raw_value=item.raw_value,
            photo_url=item.photo_url,
            monthly_prices=dict(item.monthly_prices),
            monthly_statuses=dict(item.monthly_statuses),
        )


class SearchResponse(BaseModel):
    """HTTP response for Albion search."""

    count: int
    results: list[SearchResult]

    @classmethod
    def from_items(
        cls,
        items: list[SearchResultItem],
    ) -> "SearchResponse":
        return cls(
            count=len(items),
            results=[
                SearchResult.from_item(item)
                for item in items
            ],
        )


def execute_search(
    request: SearchRequest,
    bridge: AlbionSearchBridge | None = None,
) -> SearchResponse:
    """Execute one HTTP search request through the bridge."""

    search_bridge = bridge or AlbionSearchBridge()

    items = search_bridge.search(
        request.to_search_query()
    )

    return SearchResponse.from_items(items)
