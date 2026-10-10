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
    district: str | None = None
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
        if self.availability not in {None, "FREE"}:
            raise ValueError("availability должен быть FREE или не задан")

        if self.sort_by not in {None, "price_asc", "load_asc"}:
            raise ValueError("sort_by должен быть price_asc или load_asc")

        if self.availability == "FREE" and self.month is None and not self.months:
            raise ValueError(
                "Для поиска свободных конструкций укажите месяц или период"
            )
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
            district=self.district,
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
    district: str | None = None
    address: str | None = None
    name: str | None = None
    side: str | None = None
    type: str | None = None
    media_type: str | None = None
    size: str | None = None
    lat: float | None = None
    lng: float | None = None
    latitude: float | None = None
    longitude: float | None = None

    price: int | None = None
    load_percent: int | None = None
    status: str | None = None
    raw_value: str | None = None
    photo_url: str | None = None
    photo: str | None = None
    photo_thumb: str | None = None
    photo_large: str | None = None
    map: str | None = None
    map_thumb: str | None = None
    map_card: str | None = None
    map_large: str | None = None
    light: str | None = None
    material: str | None = None
    monthly_loads: dict[int, int | None] = Field(default_factory=dict)
    month_texts: dict[int, str | None] = Field(default_factory=dict)

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

    @classmethod
    def from_rich(cls, item: dict[str, Any]) -> "SearchResult":
        """Serialize the site-compatible result used by chat and map UI."""
        return cls(
            id=int(item.get("id") or 0),
            external_id=item.get("external_id"),
            city=item.get("city"),
            district=item.get("district"),
            address=item.get("address"),
            name=item.get("name") or item.get("title"),
            side=item.get("side"),
            type=item.get("type"),
            media_type=item.get("media_type"),
            size=item.get("size"),
            lat=item.get("lat"),
            lng=item.get("lng"),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            price=item.get("price"),
            load_percent=item.get("load_percent"),
            status=item.get("status"),
            raw_value=item.get("raw_value"),
            photo_url=item.get("photo_url"),
            photo=item.get("photo"),
            photo_thumb=item.get("photo_thumb"),
            photo_large=item.get("photo_large"),
            map=item.get("map"),
            map_thumb=item.get("map_thumb"),
            map_card=item.get("map_card"),
            map_large=item.get("map_large"),
            light=item.get("light"),
            material=item.get("material"),
            monthly_prices=dict(item.get("monthly_prices") or {}),
            monthly_statuses=dict(item.get("monthly_statuses") or {}),
            monthly_loads=dict(item.get("monthly_loads") or {}),
            month_texts=dict(item.get("month_texts") or {}),
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

    @classmethod
    def from_rich_items(
        cls,
        items: list[dict[str, Any]],
    ) -> "SearchResponse":
        return cls(
            count=len(items),
            results=[
                SearchResult.from_rich(item)
                for item in items
            ],
        )


def execute_search(
    request: SearchRequest,
    bridge: AlbionSearchBridge | None = None,
) -> SearchResponse:
    """Execute one HTTP search request through the bridge."""

    search_bridge = bridge or AlbionSearchBridge()

    query = request.to_search_query()

    if hasattr(search_bridge, "search_rich"):
        items = search_bridge.search_rich(query)
        return SearchResponse.from_rich_items(items)

    # Preserve compatibility with small test/dummy bridges that implement
    # only the original SearchResultItem contract.
    return SearchResponse.from_items(search_bridge.search(query))
