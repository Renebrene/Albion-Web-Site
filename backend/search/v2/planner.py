"""Resolve a SearchQuery against the actual catalog values."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.query import SearchQuery

from backend.search.catalog import CatalogSnapshot
from backend.search.normalization import (
    LocationResolver,
    SizeDimensions,
    TypeResolver,
    parse_dimensions,
)


@dataclass
class ResolvedQuery:
    source: SearchQuery
    city: str | None = None
    area: str | None = None
    media_type: str | None = None
    size_dims: SizeDimensions | None = None
    year: int | None = None
    months: list[int] = field(default_factory=list)
    period_mode: str = "ANY"
    strict: bool = True
    unresolved: bool = False
    warnings: list[str] = field(default_factory=list)

    def as_meta(self) -> dict:
        return {
            "city": self.city,
            "district": self.area,
            "media_type": self.media_type,
            "size": (
                {
                    "major": self.size_dims.major,
                    "minor": self.size_dims.minor,
                }
                if self.size_dims
                else None
            ),
            "year": self.year,
            "months": list(self.months),
        }


def resolve_query(
    query: SearchQuery,
    snapshot: CatalogSnapshot,
    *,
    dictionary: SynonymDictionary | None = None,
    strict: bool = True,
) -> ResolvedQuery:
    resolved = ResolvedQuery(
        source=query,
        strict=strict,
        months=list(query.get_months()),
        period_mode=query.period_mode,
        year=query.year or (max(snapshot.years) if snapshot.years else None),
    )

    resolver = LocationResolver(snapshot.cities, snapshot.areas)

    if query.city:
        resolved.city = resolver.resolve_city(query.city)

        if resolved.city is None:
            resolved.unresolved = True
            resolved.warnings.append(
                f"Город «{query.city}» не найден в базе"
            )

    if query.district:
        resolved.area = resolver.resolve_area(query.district)

        if resolved.area is None:
            resolved.unresolved = True
            resolved.warnings.append(
                f"Район «{query.district}» не найден в базе"
            )

    if query.media_type:
        type_resolver = TypeResolver(snapshot.types, dictionary)
        resolved.media_type, warning = type_resolver.resolve(
            query.media_type
        )

        if resolved.media_type is None:
            resolved.unresolved = True

        if warning:
            resolved.warnings.append(warning)

    if query.size:
        resolved.size_dims = parse_dimensions(query.size)

        if resolved.size_dims is None:
            resolved.unresolved = True
            resolved.warnings.append(
                f"Размер «{query.size}» не распознан"
            )

    return resolved
