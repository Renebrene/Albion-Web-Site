from __future__ import annotations

import importlib.resources
import re
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.parser import QueryParser
from engine.query.query import SearchQuery
from engine.search.postgresql_chat_engine import PendingSearchQuery

from backend.chat import llm
from backend.chat.formatting import actions_for, format_answer
from backend.chat.models import (
    ChatActions,
    ChatClarification,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatQuery,
    ChatResults,
    ChatSuggestion,
    ClarificationOption,
)
from backend.chat.store import ChatSession, ChatStore, chat_store
from backend.search.bridge import AlbionSearchBridge
from backend.services.chat_log_service import log_turn


class ChatService:
    """Natural-language chat facade over the site's existing search bridge."""

    def __init__(
        self,
        *,
        bridge: AlbionSearchBridge | None = None,
        store: ChatStore | None = None,
    ) -> None:
        self.bridge = bridge or AlbionSearchBridge()
        self.store = store or chat_store
        self.dictionary = self._load_dictionary()
        self.parser = QueryParser(self.dictionary)

    @staticmethod
    def _load_dictionary() -> SynonymDictionary:
        try:
            resource = importlib.resources.files("engine.dictionary").joinpath(
                "synonyms.json"
            )
            return SynonymDictionary(str(resource))
        except (FileNotFoundError, ModuleNotFoundError, TypeError):
            import engine

            path = Path(engine.__file__).parent / "dictionary" / "synonyms.json"
            return SynonymDictionary(path)

    def _session(self, session_id: UUID | None) -> ChatSession:
        if session_id is None:
            return self.store.create()

        session = self.store.get(session_id)

        # A restarted/expired session must not break the conversation:
        # transparently start a new one so the new question still works.
        if session is None:
            return self.store.create()

        return session

    @staticmethod
    def _generic_district(text: str) -> str | None:
        """Extract the adjective stem of a "<word> район" phrase.

        Returns a stem such as "октябрьск" that the bridge matches as a
        substring of the site city/area name ("ОКТЯБРЬСКИЙ РАЙОН").
        """
        match = re.search(r"\b([а-яё]{4,})\s+район", text)
        if not match:
            return None

        word = match.group(1)
        endings = (
            "ского", "скому", "ским", "ском", "ской", "ская", "ский",
            "ские", "ских", "ого", "ому", "ыми", "ыми", "ым", "ом",
            "ий", "ых", "ая", "ое", "ые", "ей",
        )
        for ending in endings:
            if word.endswith(ending) and len(word) - len(ending) >= 4:
                return word[: -len(ending)]

        return word

    @staticmethod
    def _query_has_constraints(query: SearchQuery) -> bool:
        return any(
            value not in (None, "", [])
            for value in (
                query.city,
                query.district,
                query.address,
                query.media_type,
                query.size,
                query.month,
                query.months,
                query.availability,
                query.load_threshold,
                query.max_load,
                query.min_price,
                query.max_price,
                query.sort_by,
            )
        )

    @staticmethod
    def _canonical(dictionary: SynonymDictionary, key: str, value: Any) -> Any:
        if value is None:
            return None
        if key == "city":
            return dictionary.find_city(str(value)) or str(value)
        if key == "media_type":
            return (
                dictionary.find_type(str(value))
                or dictionary.find_keyword(str(value))
                or str(value)
            )
        return value

    def _query_from_llm(self, text: str, values: dict[str, Any]) -> SearchQuery:
        months = values.get("months") or []
        if not isinstance(months, list):
            months = []
        months = [int(month) for month in months if str(month).isdigit()]
        month = values.get("month")
        if len(months) == 1 and month is None:
            month, months = months[0], []

        availability = values.get("availability")
        if availability:
            availability = str(availability).upper()
            if availability in {"FREE", "СВОБОДНО", "СВОБОДНЫЕ"}:
                availability = "FREE"
            else:
                availability = None

        return SearchQuery(
            city=self._canonical(self.dictionary, "city", values.get("city")),
            district=values.get("district"),
            address=values.get("address"),
            media_type=self._canonical(
                self.dictionary, "media_type", values.get("media_type")
            ),
            size=values.get("size"),
            year=int(values.get("year") or 2026),
            month=int(month) if month is not None else None,
            months=months,
            period_mode="ALL" if len(months) > 1 else "ANY",
            availability=availability,
            load_threshold=values.get("min_load"),
            max_load=values.get("max_load"),
            min_price=values.get("min_price"),
            max_price=values.get("max_price"),
            sort_by=values.get("sort_by"),
            limit=values.get("limit"),
        )

    def _parse(
        self,
        text: str,
    ) -> tuple[SearchQuery, str, list[str], str | None]:
        warnings: list[str] = []
        query: SearchQuery | None = None
        clarification: str | None = None

        # The portable parser understands month forms separated by spaces or a
        # simple range. Normalize a three-month dash list before parsing so
        # common UI phrasing such as "октябрь-ноябрь-декабрь" is retained.
        normalized_text = re.sub(
            r"([а-яё]+)-([а-яё]+)-([а-яё]+)",
            r"\1 \2 \3",
            text.lower(),
        )
        normalized_text = re.sub(
            r"\bэкран(?:ы|ов|ами|ах)?\b",
            "видеоэкран",
            normalized_text,
        )

        try:
            parsed = self.parser.parse(normalized_text)
            query = parsed.query
            clarification = parsed.clarification
            # Site districts (e.g. "ОКТЯБРЬСКИЙ РАЙОН") are stored as cities.
            # The portable parser knows only a fixed list, so recover any
            # "<adjective> район" phrase and match it against the city name.
            if query is not None and not query.district:
                district = self._generic_district(normalized_text)
                if district:
                    query.district = district
            if len(query.get_months()) > 1 and re.search(
                r"(?:-|–|—|\sи\s)", text.lower()
            ) and "или" not in text.lower():
                query.period_mode = "ALL"
            # The parser's range helper handles two endpoints. For a chained
            # three-month phrase, recover the explicit month forms here.
            if len(query.get_months()) == 2:
                month_numbers = {
                    "январ": 1, "феврал": 2, "март": 3, "апрел": 4,
                    "ма": 5, "июн": 6, "июл": 7, "август": 8,
                    "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
                }
                found = []
                for token in re.findall(r"[а-яё]+", normalized_text):
                    for prefix, number in month_numbers.items():
                        if token.startswith(prefix):
                            found.append(number)
                            break
                if len(set(found)) >= 3:
                    query.month = None
                    query.months = sorted(set(found))
                    query.period_mode = "ALL"
        except ValueError as exc:
            warnings.append(str(exc))

        if query is not None and (
            clarification or self._query_has_constraints(query)
        ):
            return query, "rules", warnings, clarification

        extracted = llm.extract(text)
        if extracted.values:
            return (
                self._query_from_llm(text, extracted.values),
                "llm",
                warnings,
                None,
            )
        if extracted.warning:
            warnings.append(extracted.warning)

        raise ValueError(
            "Не удалось распознать запрос. Укажите город, адрес, тип "
            "конструкции или период."
        )

    @staticmethod
    def _clarification(query: SearchQuery, text: str) -> ChatClarification:
        return ChatClarification(
            type="media_type",
            text=text,
            options=[
                ClarificationOption(value="статика", label="Статика / щиты"),
                ClarificationOption(value="динамика", label="Динамика / призматроны"),
            ],
        )

    @staticmethod
    def _response(
        session: ChatSession,
        *,
        query: SearchQuery | None,
        answer: str,
        source: str,
        pending: bool = False,
        clarification: ChatClarification | None = None,
        items: list[dict[str, Any]] | None = None,
        suggestions: list[ChatSuggestion] | None = None,
        warnings: list[str] | None = None,
    ) -> ChatMessageResponse:
        items = items or []
        return ChatMessageResponse(
            session_id=session.id,
            message_id=uuid4(),
            pending=pending,
            answer=answer,
            source=source if source in {"rules", "llm", "fallback"} else "rules",
            query=ChatQuery.from_query(query) if query else None,
            clarification=clarification,
            results=ChatResults(count=len(items), items=items),
            suggestions=suggestions or [],
            actions=ChatActions(**actions_for(items)),
            warnings=warnings or [],
        )

    def _suggestions(
        self,
        query: SearchQuery,
        items: list[dict[str, Any]],
    ) -> list[ChatSuggestion]:
        """When nothing matched, propose relaxed alternatives.

        Example: «пиллар на Привокзальной» -> other pillars anywhere and
        other construction types on Привокзальная.
        """
        if items:
            return []

        result: list[ChatSuggestion] = []
        seen: set[int] = set()

        # Suggested alternatives must stay inside the requested city.
        # The broad location match also hits route names («Ростов-Таганрог»),
        # so filter strictly by the city field here.
        city_key = (
            str(query.city or "").strip().casefold().replace("ё", "е") or None
        )

        def relaxed(**changes: Any) -> list[dict[str, Any]]:
            # No limit here: the city filter must run before we take the
            # first few items, otherwise the limit cuts them off.
            try:
                variant = replace(query, limit=None, **changes)
            except ValueError:
                return []
            found = self.bridge.search_rich(variant)

            if city_key:
                found = [
                    item
                    for item in found
                    if str(item.get("city") or "")
                    .strip()
                    .casefold()
                    .replace("ё", "е")
                    == city_key
                ]

            fresh = [
                item
                for item in found
                if int(item.get("id") or 0) not in seen
            ]
            return fresh[:5]

        if query.address and query.media_type:
            similar = relaxed(address=None)
            if similar:
                seen.update(int(item["id"]) for item in similar)
                result.append(
                    ChatSuggestion(
                        type="similar_type",
                        title=f"Другие варианты: {query.media_type}",
                        items=similar,
                    )
                )

            same_address = relaxed(media_type=None)
            if same_address:
                seen.update(int(item["id"]) for item in same_address)
                result.append(
                    ChatSuggestion(
                        type="same_address",
                        title=f"Другие конструкции: {query.address.capitalize()}",
                        items=same_address,
                    )
                )
        elif query.address:
            similar = relaxed(address=None)
            if similar:
                result.append(
                    ChatSuggestion(
                        type="similar",
                        title="Похожие варианты",
                        items=similar,
                    )
                )
        elif query.media_type:
            other_types = relaxed(media_type=None)
            if other_types:
                city_suffix = (
                    f" в городе {query.city}" if query.city else ""
                )
                result.append(
                    ChatSuggestion(
                        type="other_types",
                        title=f"Другие типы конструкций{city_suffix}",
                        items=other_types,
                    )
                )

        return result

    def message(self, payload: ChatMessageRequest) -> ChatMessageResponse:
        session = self._session(payload.session_id)
        cached = self.store.response_for(session, payload.request_id)
        if cached is not None:
            return ChatMessageResponse.model_validate(cached)

        source = "rules"
        warnings: list[str] = []
        query: SearchQuery
        clarification_text: str | None = None

        if isinstance(session.pending, PendingSearchQuery):
            try:
                query = session.pending.resolve(payload.message, self.dictionary)
                session.pending = None
            except ValueError:
                (
                    query,
                    source,
                    warnings,
                    clarification_text,
                ) = self._parse(payload.message)
        else:
            (
                query,
                source,
                warnings,
                clarification_text,
            ) = self._parse(payload.message)

        context = payload.context
        if context is not None:
            if context.year is not None:
                query.year = context.year
            if context.selected_months and not query.has_period():
                if len(context.selected_months) == 1:
                    query.month = context.selected_months[0]
                else:
                    query.month = None
                    query.months = list(context.selected_months)
                    query.period_mode = "ALL"

        if clarification_text:
            session.pending = PendingSearchQuery(
                query=query,
                clarification_type="media_type",
                clarification_text=clarification_text,
            )
            response = self._response(
                session,
                query=query,
                answer=clarification_text,
                source=source,
                pending=True,
                clarification=self._clarification(query, clarification_text),
                warnings=warnings,
            )
        else:
            if query.availability == "FREE" and not query.has_period():
                raise ValueError(
                    "Для поиска свободных конструкций укажите месяц или период"
                )
            items = self.bridge.search_rich(query)
            suggestions = self._suggestions(query, items)

            answer = format_answer(query, items)
            if not items and suggestions:
                answer = (
                    "По заданным условиям ничего не найдено. "
                    "Ниже — похожие варианты."
                )

            response = self._response(
                session,
                query=query,
                answer=answer,
                source=source,
                items=items,
                suggestions=suggestions,
                warnings=warnings,
            )
            session.pending = None
            session.last_result_ids = [int(item["id"]) for item in items]

        if payload.request_id is not None:
            self.store.remember_response(
                session,
                payload.request_id,
                response.model_dump(mode="json"),
            )

        # Текстовый журнал «вопрос → ответ» для дальнейшего изучения.
        # Ошибка записи не должна ломать ответ пользователю.
        try:
            log_turn(
                session_id=session.id,
                chat_key=payload.chat_key,
                question=payload.message,
                answer=response.answer,
            )
        except Exception:  # noqa: BLE001
            pass

        return response

    def reset(self, session_id: UUID) -> bool:
        return self.store.reset(session_id)
