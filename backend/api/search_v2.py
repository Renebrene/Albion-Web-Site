"""Search v2 HTTP endpoint and catalog diagnostics.

``POST /api/search`` (v1) intentionally keeps its response contract.
``POST /api/search/v2`` adds total/resolved/warnings metadata and uses the
in-process catalog with strict city+district semantics.
"""

from __future__ import annotations

import threading
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.search.api import SearchRequest, SearchResult
from backend.search.v2.service import SearchV2Service
from backend.services.auth_api import require_admin


router = APIRouter(prefix="/api/search", tags=["search-v2"])
admin_router = APIRouter(prefix="/api/admin/search", tags=["admin-search"])


class SearchV2Request(SearchRequest):
    location_mode: Literal["strict", "relaxed"] = "strict"
    explain: bool = False


class SearchV2Meta(BaseModel):
    version: str = "v2"
    catalog_version: str = ""
    total: int = 0
    took_ms: float = 0.0
    resolved: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SearchV2Response(BaseModel):
    count: int
    total: int
    results: list[SearchResult]
    meta: SearchV2Meta


_service: SearchV2Service | None = None
_service_lock = threading.Lock()


def get_search_v2_service() -> SearchV2Service:
    global _service

    if _service is None:
        with _service_lock:
            if _service is None:
                _service = SearchV2Service()

    return _service


@router.post("/v2", response_model=SearchV2Response)
def search_v2(payload: SearchV2Request) -> SearchV2Response:
    query = payload.to_search_query()

    if payload.location_mode == "relaxed":
        # Explicit compatibility mode: reuse the v1 bridge so clients can
        # compare old and new semantics side by side.
        from backend.search.api import get_default_bridge

        items = get_default_bridge().search_rich(query)
        meta = SearchV2Meta(
            version="v2-relaxed",
            total=len(items),
            resolved={},
            warnings=[
                "location_mode=relaxed использует прежнюю OR-семантику v1"
            ],
        )
    else:
        service = get_search_v2_service()
        items, raw_meta = service.search(query, strict=True)
        meta = SearchV2Meta(**raw_meta)

    results = [SearchResult.from_rich(item) for item in items]

    return SearchV2Response(
        count=len(results),
        total=meta.total,
        results=results,
        meta=meta,
    )


@admin_router.get("/catalog")
def catalog_info(auth=Depends(require_admin)):
    from backend.search.catalog import get_catalog

    return {"success": True, **get_catalog().describe()}


@admin_router.post("/catalog/reload")
def catalog_reload(auth=Depends(require_admin)):
    from backend.search.catalog import get_catalog

    snapshot = get_catalog().refresh()

    return {
        "success": True,
        "version": snapshot.version,
        "surfaces": len(snapshot.entries),
    }
