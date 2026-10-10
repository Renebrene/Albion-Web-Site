from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int | None = Field(default=None, ge=2000, le=2100)
    selected_months: list[int] = Field(default_factory=list)
    portfolio_surface_ids: list[int] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    request_id: UUID | None = None
    message: str = Field(min_length=1, max_length=2000)
    context: ChatContext | None = None


class ChatSessionResponse(BaseModel):
    session_id: UUID


class ClarificationOption(BaseModel):
    value: str
    label: str


class ChatClarification(BaseModel):
    type: str
    text: str
    options: list[ClarificationOption] = Field(default_factory=list)


class ChatQuery(BaseModel):
    city: str | None = None
    district: str | None = None
    address: str | None = None
    media_type: str | None = None
    size: str | None = None
    year: int
    month: int | None = None
    months: list[int] = Field(default_factory=list)
    period_mode: Literal["ANY", "ALL"] = "ANY"
    availability: str | None = None
    load_threshold: int | None = None
    max_load: int | None = None
    min_price: int | None = None
    max_price: int | None = None
    sort_by: str | None = None
    limit: int | None = None

    @classmethod
    def from_query(cls, query: Any) -> "ChatQuery":
        return cls(
            city=query.city,
            district=query.district,
            address=query.address,
            media_type=query.media_type,
            size=query.size,
            year=query.year,
            month=query.month,
            months=list(query.months),
            period_mode=query.period_mode,
            availability=query.availability,
            load_threshold=query.load_threshold,
            max_load=query.max_load,
            min_price=query.min_price,
            max_price=query.max_price,
            sort_by=query.sort_by,
            limit=query.limit,
        )


class ChatResults(BaseModel):
    count: int
    items: list[dict[str, Any]] = Field(default_factory=list)


class ChatActions(BaseModel):
    map: dict[str, Any] = Field(default_factory=dict)
    list: dict[str, Any] = Field(default_factory=dict)
    media: dict[str, Any] = Field(default_factory=dict)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    export: dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    session_id: UUID
    message_id: UUID
    pending: bool
    answer: str
    source: Literal["rules", "llm", "fallback"] = "rules"
    query: ChatQuery | None = None
    clarification: ChatClarification | None = None
    results: ChatResults = Field(default_factory=lambda: ChatResults(count=0))
    actions: ChatActions = Field(default_factory=ChatActions)
    warnings: list[str] = Field(default_factory=list)


class ChatResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
