"""In-process search catalog.

The site has roughly 1200–1600 active surfaces. Loading them once into a
normalized snapshot removes all SQL from the hot search path and makes v2
independent of per-row override/media lookups.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from engine.storage.models import AvailabilityRecord, SurfaceRecord

from backend.search.normalization import (
    SizeDimensions,
    normalize_text,
    parse_dimensions,
)
from backend.services.data_service import _read_cache_stamp


@dataclass(frozen=True)
class CatalogEntry:
    surface: SurfaceRecord
    type_norm: str
    city_norm: str
    district_norm: str
    area_norm: str | None
    size_dims: SizeDimensions | None
    availability: dict[int, dict[int, AvailabilityRecord]] = field(
        default_factory=dict
    )

    def records_for_year(self, year: int | None) -> list[AvailabilityRecord]:
        if year is None:
            result: list[AvailabilityRecord] = []
            for records in self.availability.values():
                result.extend(records.values())
            return result

        return list(self.availability.get(int(year), {}).values())


@dataclass(frozen=True)
class CatalogSnapshot:
    version: str
    built_at: float
    entries: tuple[CatalogEntry, ...]
    by_id: dict[int, CatalogEntry]
    types: dict[str, int]
    cities: tuple[str, ...]
    areas: tuple[str, ...]
    years: tuple[int, ...]
    size_parse_failures: int


class SurfaceCatalog:
    """Thread-safe lazily rebuilt catalog shared by one worker."""

    def __init__(self, repository=None, ttl_seconds: float | None = None):
        self.repository = repository
        self.ttl = float(
            ttl_seconds
            if ttl_seconds is not None
            else os.getenv("ALBION_SEARCH_CATALOG_TTL", "60")
        )
        self._snapshot: CatalogSnapshot | None = None
        self._stamp: str | None = None
        self._built_at = 0.0
        self._lock = threading.RLock()

    @staticmethod
    def _current_stamp() -> str:
        return _read_cache_stamp()

    def snapshot(self) -> CatalogSnapshot:
        stamp = self._current_stamp()
        now = time.monotonic()

        cached = self._snapshot
        if (
            cached is not None
            and self._stamp == stamp
            and (now - self._built_at) < self.ttl
        ):
            return cached

        with self._lock:
            cached = self._snapshot
            now = time.monotonic()

            if (
                cached is not None
                and self._stamp == stamp
                and (now - self._built_at) < self.ttl
            ):
                return cached

            from backend.search.catalog_loader import load_snapshot

            snapshot = load_snapshot(self.repository, stamp)

            self._snapshot = snapshot
            self._stamp = stamp
            self._built_at = now
            return snapshot

    def refresh(self) -> CatalogSnapshot:
        with self._lock:
            self._snapshot = None
            self._stamp = None
            self._built_at = 0.0
        return self.snapshot()

    def describe(self) -> dict[str, Any]:
        snapshot = self.snapshot()

        return {
            "version": snapshot.version,
            "built_at": snapshot.built_at,
            "surfaces": len(snapshot.entries),
            "types": snapshot.types,
            "cities": list(snapshot.cities),
            "areas": list(snapshot.areas),
            "years": list(snapshot.years),
            "size_parse_failures": snapshot.size_parse_failures,
        }


_catalog: SurfaceCatalog | None = None
_catalog_lock = threading.Lock()


def get_catalog(repository=None) -> SurfaceCatalog:
    global _catalog

    if _catalog is None:
        with _catalog_lock:
            if _catalog is None:
                from backend.search.repository import (
                    SitePostgreSQLSearchRepository,
                )

                _catalog = SurfaceCatalog(
                    repository or SitePostgreSQLSearchRepository()
                )

    return _catalog


def invalidate_catalog() -> None:
    if _catalog is not None:
        _catalog.refresh()
