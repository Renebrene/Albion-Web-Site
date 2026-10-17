"""Search v2 service: catalog match + shared rich presenter."""

from __future__ import annotations

import importlib.resources
import time
from pathlib import Path
from typing import Any

from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.query import SearchQuery

from backend.search.catalog import SurfaceCatalog, get_catalog
from backend.search.presenter import rich_item, sort_and_limit
from backend.search.v2.matcher import filter_entries
from backend.search.v2.planner import resolve_query


def _load_dictionary() -> SynonymDictionary:
    try:
        resource = importlib.resources.files("engine.dictionary").joinpath(
            "synonyms.json"
        )
        dictionary = SynonymDictionary(str(resource))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        import engine

        path = Path(engine.__file__).parent / "dictionary" / "synonyms.json"
        dictionary = SynonymDictionary(path)

    dictionary.load()
    return dictionary


class SearchV2Service:
    """In-process search over a normalized catalog snapshot."""

    def __init__(
        self,
        *,
        catalog: SurfaceCatalog | None = None,
        dictionary: SynonymDictionary | None = None,
    ) -> None:
        self.catalog = catalog or get_catalog()
        self.dictionary = dictionary or _load_dictionary()

    def search(
        self,
        query: SearchQuery,
        *,
        strict: bool = True,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        started = time.monotonic()
        snapshot = self.catalog.snapshot()
        resolved = resolve_query(
            query,
            snapshot,
            dictionary=self.dictionary,
            strict=strict,
        )

        # Keep the caller's query in sync with the type that actually exists
        # (e.g. «скроллер» → «Скроллер» instead of «Сити-борд») so the chat
        # answer and follow-up suggestions name a real format.
        if resolved.media_type:
            query.media_type = resolved.media_type

        matched = filter_entries(snapshot, resolved)

        items = [
            rich_item(entry.surface, records, query)
            for entry, records in matched
        ]
        total = len(items)

        if (
            total == 0
            and strict
            and resolved.city
            and resolved.area
            and not resolved.unresolved
        ):
            resolved.warnings.append(
                f"В базе нет конструкций одновременно в городе "
                f"«{resolved.city}» и районе «{resolved.area}». "
                "Район может быть отдельной локацией — уточните запрос."
            )

        # limit is applied after computing total, so the client sees the
        # real number of matches rather than the truncated list length.
        items = sort_and_limit(items, query)

        meta = {
            "version": "v2",
            "catalog_version": snapshot.version,
            "total": total,
            "took_ms": round((time.monotonic() - started) * 1000, 1),
            "resolved": resolved.as_meta(),
            "warnings": resolved.warnings,
        }

        return items, meta

    def default_year(self) -> int:
        snapshot = self.catalog.snapshot()
        if snapshot.years:
            return max(snapshot.years)

        from datetime import date

        return date.today().year

    def search_rich(self, query: SearchQuery) -> list[dict[str, Any]]:
        """Chat-compatible entry point."""
        items, _meta = self.search(query, strict=True)
        return items
