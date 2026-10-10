from __future__ import annotations

from engine.query.query import SearchQuery


class SearchService:
    """Unified search entry point for the storage-independent query model."""

    def __init__(self, repository):
        self.repository = repository

    def search(self, query: SearchQuery):
        if not isinstance(query, SearchQuery):
            raise TypeError("SearchService.search() ожидает SearchQuery")

        months = query.get_months()
        common = {
            "address": query.address,
            "city": query.city,
            "media_type": query.media_type,
            "size": query.size,
            "min_price": query.min_price,
            "max_price": query.max_price,
        }

        if query.availability == "FREE":
            if query.month is not None:
                return self.repository.find_free(
                    year=query.year,
                    month=query.month,
                    **common,
                    load_threshold=query.load_threshold,
                    max_load=query.max_load,
                )

            if months:
                method = (
                    self.repository.find_free_all
                    if query.period_mode == "ALL"
                    else self.repository.find_free_any
                )
                return method(
                    year=query.year,
                    months=months,
                    **common,
                    load_threshold=query.load_threshold,
                    max_load=query.max_load,
                )

            raise ValueError(
                "Для поиска свободных конструкций укажите месяц или период"
            )

        if query.availability not in {None, "FREE"}:
            raise ValueError(
                f"Неподдерживаемый availability: {query.availability}"
            )

        if months:
            method = (
                self.repository.find_by_filters_all
                if query.period_mode == "ALL"
                else self.repository.find_by_filters_any
            )
            return method(
                year=query.year,
                months=months,
                **common,
                load_threshold=query.load_threshold,
                max_load=query.max_load,
            )

        return self.repository.find_by_filters_with_availability(
            year=query.year,
            month=query.month,
            **common,
            load_threshold=query.load_threshold,
            max_load=query.max_load,
        )
