"""Build a normalized in-memory snapshot from PostgreSQL."""

from __future__ import annotations

import time
from collections import Counter

from sqlalchemy import text

from engine.storage.models import AvailabilityRecord, SurfaceRecord

from backend.search.catalog import CatalogEntry, CatalogSnapshot
from backend.search.mapper import SiteSurfaceMapper
from backend.search.normalization import (
    is_area_name,
    normalize_text,
    parse_dimensions,
)


def _load_surface_rows(repository) -> list:
    sql = repository._surface_select() + """
        WHERE s.is_active = TRUE
        ORDER BY ci.name, s.external_number, s.side, s.id
    """

    with repository.engine.connect() as conn:
        return conn.execute(text(sql)).mappings().all()


def _load_availability(repository) -> dict[int, dict[int, dict[int, AvailabilityRecord]]]:
    sql = """
        SELECT
            sa.id,
            sa.uuid,
            sa.surface_id,
            sa.year,
            sa.month,
            sa.status,
            sa.price,
            sa.load_percent,
            sa.raw_value,
            sa.created_at,
            sa.updated_at,
            sa.is_active
        FROM surface_availability sa
        WHERE sa.is_active = TRUE
        ORDER BY sa.surface_id, sa.year, sa.month
    """

    with repository.engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()

    result: dict[int, dict[int, dict[int, AvailabilityRecord]]] = {}

    for row in rows:
        item = repository._availability(row)
        by_year = result.setdefault(item.surface_id, {})
        by_year.setdefault(item.year, {})[item.month] = item

    return result


def _entry(
    surface: SurfaceRecord,
    availability: dict[int, dict[int, AvailabilityRecord]],
    size_failures: int,
) -> tuple[CatalogEntry, int]:
    area_value = None

    if is_area_name(surface.city):
        area_value = surface.city
    elif is_area_name(surface.district):
        area_value = surface.district

    size_dims = parse_dimensions(surface.size)

    if surface.size and size_dims is None:
        size_failures += 1

    return (
        CatalogEntry(
            surface=surface,
            type_norm=normalize_text(surface.media_type),
            city_norm=normalize_text(surface.city),
            district_norm=normalize_text(surface.district),
            area_norm=normalize_text(area_value) if area_value else None,
            size_dims=size_dims,
            availability=availability,
        ),
        size_failures,
    )


def load_snapshot(repository, stamp: str = "") -> CatalogSnapshot:
    """Load all active surfaces and availability in a few queries."""
    from backend.search.repository import SitePostgreSQLSearchRepository

    if repository is None:
        repository = SitePostgreSQLSearchRepository()

    rows = _load_surface_rows(repository)

    fields_map, overrides_map, media_map = repository._load_lookup_maps()
    surfaces = SiteSurfaceMapper.map_many(
        rows,
        fields_map=fields_map,
        overrides_map=overrides_map,
        media_map=media_map,
    )

    availability = _load_availability(repository)

    entries: list[CatalogEntry] = []
    size_failures = 0

    for surface in surfaces:
        entry, size_failures = _entry(
            surface,
            availability.get(surface.id or 0, {}),
            size_failures,
        )
        entries.append(entry)

    type_counter = Counter(
        str(entry.surface.media_type or "").strip()
        for entry in entries
        if str(entry.surface.media_type or "").strip()
    )
    cities = sorted(
        {
            str(entry.surface.city).strip()
            for entry in entries
            if str(entry.surface.city or "").strip()
        }
    )
    areas = sorted(
        {
            value
            for entry in entries
            for value in (entry.surface.city, entry.surface.district)
            if value and is_area_name(value)
        }
    )
    years = sorted(
        {
            year
            for by_surface in availability.values()
            for year in by_surface
        }
    )

    max_updated = max(
        (
            entry.surface.updated_at
            for entry in entries
            if entry.surface.updated_at is not None
        ),
        default=None,
    )

    version = stamp or f"{len(entries)}:{max_updated}"

    return CatalogSnapshot(
        version=version,
        built_at=time.time(),
        entries=tuple(entries),
        by_id={
            entry.surface.id: entry
            for entry in entries
            if entry.surface.id is not None
        },
        types=dict(type_counter),
        cities=tuple(cities),
        areas=tuple(areas),
        years=tuple(years),
        size_parse_failures=size_failures,
    )
