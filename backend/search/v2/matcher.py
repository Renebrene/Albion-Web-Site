"""Pure-Python matching over the catalog snapshot."""

from __future__ import annotations

from engine.address.parser_v2 import AddressParserV2
from engine.house_number.matcher import HouseNumberMatcher
from engine.query.query import SearchQuery
from engine.storage.models import AvailabilityRecord

from backend.search.catalog import CatalogEntry, CatalogSnapshot
from backend.search.normalization import normalize_text, same_size
from backend.search.v2.planner import ResolvedQuery


def _address_allowed(entries: list[CatalogEntry], address: str) -> set[int]:
    parsed = AddressParserV2.parse(address)

    if not parsed.objects:
        return set()

    query_roots = {
        str(value).strip().lower()
        for value in parsed.all_street_roots
        if str(value).strip()
    }
    query_numbers = {
        str(value).strip().lower()
        for value in parsed.house_numbers
        if str(value).strip()
    }

    if not query_roots:
        return set()

    allowed: set[int] = set()

    for entry in entries:
        surface = entry.surface
        surface_roots = {
            str(value).strip().lower()
            for value in surface.street_roots
            if str(value).strip()
        }
        surface_numbers = {
            str(value).strip().lower()
            for value in surface.house_numbers
            if str(value).strip()
        }

        if not query_roots.issubset(surface_roots):
            continue

        if query_numbers:
            matched = True

            for query_number in query_numbers:
                best = HouseNumberMatcher.best_match(
                    query_number,
                    list(surface_numbers),
                )
                if best is None or best.score <= 0:
                    matched = False
                    break

            if not matched:
                continue

        if surface.id is not None:
            allowed.add(surface.id)

    return allowed


def _month_ok(record: AvailabilityRecord | None, resolved: ResolvedQuery) -> bool:
    if record is None:
        return False

    if resolved.source.availability and record.status != resolved.source.availability:
        return False

    if (
        resolved.source.load_threshold is not None
        and (
            record.load_percent is None
            or record.load_percent < resolved.source.load_threshold
        )
    ):
        return False

    if (
        resolved.source.max_load is not None
        and (
            record.load_percent is None
            or record.load_percent > resolved.source.max_load
        )
    ):
        return False

    return True


def _period_ok(entry: CatalogEntry, resolved: ResolvedQuery) -> bool:
    records = entry.records_for_year(resolved.year)
    query = resolved.source

    if not records:
        # v1 always joins availability for the requested year, so surfaces
        # without any record are not visible.
        return False

    by_month = {record.month: record for record in records}

    if resolved.months:
        valid = [
            month
            for month in resolved.months
            if _month_ok(by_month.get(month), resolved)
        ]

        if resolved.period_mode == "ALL":
            return set(valid) == set(resolved.months)

        return bool(valid)

    if query.availability:
        # FREE without a period is rejected earlier; keep the guard anyway.
        return False

    if query.load_threshold is not None or query.max_load is not None:
        return any(_month_ok(record, resolved) for record in records)

    return True


def _location_ok(entry: CatalogEntry, resolved: ResolvedQuery) -> bool:
    if resolved.strict:
        if resolved.city and entry.city_norm != normalize_text(resolved.city):
            return False

        if resolved.area:
            area = normalize_text(resolved.area)
            if entry.area_norm != area:
                return False

        return True

    # Relaxed mode mirrors v1: location words may match city/district/
    # address/title and are OR-ed.
    terms = [
        normalize_text(value)
        for value in (resolved.city, resolved.area)
        if value
    ]

    if not terms:
        return True

    haystack = " ".join(
        normalize_text(value)
        for value in (
            entry.surface.city,
            entry.surface.district,
            entry.surface.address,
            entry.surface.title,
        )
    )
    return any(term in haystack for term in terms)


def filter_entries(
    snapshot: CatalogSnapshot,
    resolved: ResolvedQuery,
) -> list[tuple[CatalogEntry, list[AvailabilityRecord]]]:
    if resolved.unresolved:
        return []

    query: SearchQuery = resolved.source
    candidates = list(snapshot.entries)

    if resolved.media_type:
        expected = normalize_text(resolved.media_type)
        candidates = [
            entry
            for entry in candidates
            if entry.type_norm == expected
        ]

    candidates = [
        entry
        for entry in candidates
        if _location_ok(entry, resolved)
    ]

    if resolved.size_dims is not None:
        candidates = [
            entry
            for entry in candidates
            if entry.size_dims is not None
            and same_size(entry.size_dims, resolved.size_dims)
        ]

    if query.min_price is not None:
        candidates = [
            entry
            for entry in candidates
            if entry.surface.price is not None
            and entry.surface.price >= query.min_price
        ]

    if query.max_price is not None:
        candidates = [
            entry
            for entry in candidates
            if entry.surface.price is not None
            and entry.surface.price <= query.max_price
        ]

    if query.address:
        allowed = _address_allowed(candidates, query.address)
        candidates = [
            entry
            for entry in candidates
            if entry.surface.id in allowed
        ]

    result: list[tuple[CatalogEntry, list[AvailabilityRecord]]] = []

    for entry in candidates:
        if _period_ok(entry, resolved):
            result.append((entry, entry.records_for_year(resolved.year)))

    return result
