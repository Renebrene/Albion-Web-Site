from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.parser import ParseResult, QueryParser
from engine.query.query import SearchQuery
from engine.search.result_mapper import SearchResultMapper
from engine.search.service import SearchService


@dataclass
class PendingSearchQuery:
    """
    Незавершённый запрос нового PostgreSQL search engine.

    Хранит уже распарсированный SearchQuery.
    """

    query: SearchQuery
    clarification_type: str
    clarification_text: str

    def resolve(
        self,
        answer: str,
        dictionary: SynonymDictionary,
    ) -> SearchQuery:
        if self.clarification_type != "media_type":
            raise ValueError(
                f"Неизвестный тип уточнения: "
                f"{self.clarification_type}"
            )

        if not answer or not answer.strip():
            raise ValueError(
                "Ответ на уточнение не может быть пустым"
            )

        normalized = (
            answer
            .strip()
            .lower()
            .replace("ё", "е")
        )

        tokens = set(normalized.split())

        static_variants = {
            "статика",
            "статику",
            "статике",
            "статикой",
            "статичная",
            "статичные",
            "статичный",
            "щит",
            "щита",
            "щиту",
            "щитом",
            "щиты",
        }

        dynamic_variants = {
            "динамика",
            "динамику",
            "динамике",
            "динамикой",
            "динамичная",
            "динамичные",
            "динамичный",
            "призматрон",
            "призматрона",
            "призматрону",
            "призматроном",
            "призматроны",
        }

        media_type = None

        if tokens & static_variants:
            media_type = dictionary.find_keyword("статика")

        elif tokens & dynamic_variants:
            media_type = dictionary.find_keyword("динамика")

        if media_type is None:
            raise ValueError(
                "Не удалось определить тип конструкции "
                f"из ответа: {answer!r}"
            )

        return SearchQuery(
            city=self.query.city,
            district=self.query.district,
            address=self.query.address,
            media_type=media_type,
            size=self.query.size,
            year=self.query.year,
            month=self.query.month,
            months=list(self.query.months),
            period_mode=self.query.period_mode,
            availability=self.query.availability,
            load_threshold=self.query.load_threshold,
            max_load=self.query.max_load,
            min_price=self.query.min_price,
            max_price=self.query.max_price,
            sort_by=self.query.sort_by,
            limit=self.query.limit,
        )


@dataclass
class PostgreSQLSearchResult:
    query: SearchQuery | None
    results: list[Any] | None
    clarification: str | None = None
    pending_query: PendingSearchQuery | None = None
    source: str = "postgresql"


class PostgreSQLSearchChatEngine:
    """
    Новый deterministic search engine поверх PostgreSQL.

    Не использует:
        database.database.engine
        SemanticQuery
        SemanticQueryAdapter
        SemanticQueryParser
        SearchQueryExecutor
        SQLAlchemy Surface model

    Использует:
        engine.query.QueryParser
        engine.query.SearchQuery
        engine.search.SearchService
        PostgreSQL repository
        SearchResultMapper
    """

    def __init__(
        self,
        *,
        parser: QueryParser,
        service: SearchService,
        dictionary: SynonymDictionary | None = None,
    ):
        self.parser = parser
        self.service = service
        self.dictionary = dictionary

    def process(
        self,
        text: str,
    ) -> PostgreSQLSearchResult:

        if not text or not text.strip():
            raise ValueError(
                "Поисковый запрос не может быть пустым"
            )

        parsed: ParseResult = self.parser.parse(text)

        query = parsed.query

        # -----------------------------------------------------
        # QueryParser сам сообщает о необходимости уточнения.
        # -----------------------------------------------------

        if parsed.clarification:

            pending = PendingSearchQuery(
                query=query,
                clarification_type="media_type",
                clarification_text=parsed.clarification,
            )

            return PostgreSQLSearchResult(
                query=query,
                results=None,
                clarification=parsed.clarification,
                pending_query=pending,
                source="postgresql",
            )

        return self._execute(query)

    def resolve(
        self,
        pending_query: PendingSearchQuery,
        answer: str,
    ) -> PostgreSQLSearchResult:

        if self.dictionary is None:
            raise ValueError(
                "PostgreSQLSearchChatEngine требует "
                "SynonymDictionary для resolve()"
            )

        query = pending_query.resolve(
            answer=answer,
            dictionary=self.dictionary,
        )

        return self._execute(query)

    def _execute(
        self,
        query: SearchQuery,
    ) -> PostgreSQLSearchResult:

        surfaces = self.service.search(query)

        months = query.get_months()

        availability = {}

        if surfaces:
            repository = self.service.repository

            availability = (
                repository.get_availabilities_for_surfaces(
                    surface_ids=[
                        surface.id
                        for surface in surfaces
                        if surface.id is not None
                    ],
                    year=query.year,
                    months=months or None,
                )
            )

        results = SearchResultMapper.map_many(
            surfaces,
            availabilities=availability,
            primary_month=query.month,
        )

        # Сортировка выполняется после формирования итоговых
        # SearchResultItem и до применения limit.
        if query.sort_by == "price_asc":
            results.sort(
                key=lambda item: (
                    item.price is None,
                    item.price if item.price is not None else 0,
                    item.city or "",
                    item.address or "",
                    item.side or "",
                    item.id,
                )
            )

        elif query.sort_by == "load_asc":
            results.sort(
                key=lambda item: (
                    item.load_percent is None,
                    item.load_percent
                    if item.load_percent is not None
                    else 101,
                    item.city or "",
                    item.address or "",
                    item.side or "",
                    item.id,
                )
            )

        if query.limit is not None:
            results = results[:query.limit]

        return PostgreSQLSearchResult(
            query=query,
            results=results,
            clarification=None,
            pending_query=None,
            source="postgresql",
        )
