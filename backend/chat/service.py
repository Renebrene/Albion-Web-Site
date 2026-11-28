from __future__ import annotations

import asyncio
import importlib.resources
import logging
import re
import threading
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.parser import QueryParser
from engine.query.query import SearchQuery
from engine.search.postgresql_chat_engine import PendingSearchQuery

from backend.chat import llm
from backend.chat.formatting import actions_for, format_answer
from backend.chat.query_validation import (
    meaningful,
    validate_llm_entities,
)
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
from backend.chat.settlement_intent import parse_area_intent
from backend.chat.store import ChatSession, ChatStore, chat_store
from backend.search.bridge import AlbionSearchBridge
from backend.search.spatial import find_surface_ids_near
from backend.services.chat_log_service import log_turn
from backend.services.data_service import get_connection
from backend.services.settlement_search import search_settlements
from backend.services.synonyms_service import (
    PACKAGED_VERSION,
    load_active_dictionary,
)

logger = logging.getLogger(__name__)


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
        self._dictionary_version = PACKAGED_VERSION
        self._dictionary_lock = threading.Lock()

    def _refresh_dictionary(self) -> None:
        """Подхватывает словарь, изменённый в админке.

        Версия — ``updated_at`` записи ``site_settings``. Проверка стоит
        перед каждым сообщением: словарь небольшой, а один лишний SELECT
        несущественен на фоне поиска и LLM. Все воркеры видят правку,
        потому что источник — БД, а не файл в процессе.
        """
        dictionary, version = load_active_dictionary()

        if version == self._dictionary_version:
            return

        with self._dictionary_lock:
            if version == self._dictionary_version:
                return

            self.dictionary = dictionary
            self.parser = QueryParser(dictionary)
            self._dictionary_version = version

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

    def _default_year(self) -> int:
        for candidate in (
            getattr(self.bridge, "default_year", None),
            getattr(getattr(self.bridge, "repository", None), "default_year", None),
        ):
            if callable(candidate):
                return int(candidate())

        return date.today().year

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
    def _unresolved_location_cue(
        text: str,
        query: SearchQuery | None,
    ) -> str | None:
        """Detect a location/landmark phrase the rules parser missed.

        Never silently broaden «щит в Азове» to all shields just because the
        requested place is absent from the synonym dictionary.
        """
        normalized = str(text or "").casefold().replace("ё", "е")
        address = query.address if query is not None else None
        city = query.city if query is not None else None
        district = query.district if query is not None else None

        if not address and re.search(
            r"\b(?:у|около|возле|рядом\s+с)\s+"
            r"(?:вокзал\w*|станци\w*|аэропорт\w*)",
            normalized,
        ):
            return "ориентир (вокзал/станция)"

        if city or district or address:
            return None

        match = re.search(
            r"\b(?:в|из|на)\s+(?:городе\s+)?([а-яё-]{3,})",
            normalized,
        )
        if not match:
            return None

        token = match.group(1)
        month_prefixes = (
            "январ", "феврал", "март", "апрел", "ма", "июн",
            "июл", "август", "сентябр", "октябр", "ноябр", "декабр",
        )
        if token.startswith(month_prefixes):
            return None

        if token in {
            "наличии", "резерве", "свободно", "свободные", "целом",
            "среднем", "области", "городе", "районе",
        }:
            return None

        return f"локация «{token}»"

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
        """Build a query from already-validated LLM entities."""
        months = list(values.get("months") or [])
        month = values.get("month")

        if month is not None:
            months = [month]

        if len(months) == 1:
            month, months = months[0], []

        return SearchQuery(
            city=values.get("city"),
            district=values.get("district"),
            address=values.get("address"),
            media_type=values.get("media_type"),
            size=values.get("size"),
            year=values.get("year"),
            month=month,
            months=months,
            period_mode="ALL" if len(months) > 1 else "ANY",
            availability=values.get("availability"),
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

        unresolved_location = self._unresolved_location_cue(
            normalized_text,
            query,
        )

        if (
            query is not None
            and (clarification or self._query_has_constraints(query))
            and unresolved_location is None
        ):
            return query, "rules", warnings, clarification

        extracted = llm.extract(text)
        clean, llm_warnings = validate_llm_entities(
            extracted.values,
            self.dictionary,
        )
        warnings.extend(llm_warnings)

        if unresolved_location:
            has_location = any(
                clean.get(key)
                for key in ("city", "district", "address")
            )
            if unresolved_location.startswith("ориентир"):
                has_location = bool(clean.get("address"))

            if not has_location:
                raise ValueError(
                    f"Не удалось распознать {unresolved_location}. "
                    "Уточните город или укажите адрес/улицу."
                )

        # A dict full of nulls is NOT a successful extraction: without this
        # check SearchQuery has no constraints and returns the whole catalog.
        if meaningful(clean):
            try:
                return (
                    self._query_from_llm(text, clean),
                    "llm",
                    warnings,
                    None,
                )
            except (TypeError, ValueError) as exc:
                warnings.append(f"LLM-разбор отброшен: {exc}")

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
        answer_source: str | None = None,
    ) -> ChatMessageResponse:
        items = items or []
        return ChatMessageResponse(
            session_id=session.id,
            message_id=uuid4(),
            pending=pending,
            answer=answer,
            source=source if source in {"rules", "llm", "fallback"} else "rules",
            answer_source=(
                answer_source
                if answer_source in {"rules", "llm"}
                else None
            ),
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
        self._refresh_dictionary()

        # Serialize turns of the same session. In PostgreSQL mode the lock is
        # an advisory lock, so it also works across uvicorn workers.
        if payload.session_id is None:
            session = self.store.create()
            lock = self.store.session_lock(session.id)
        else:
            session = None
            lock = self.store.session_lock(payload.session_id)

        with lock:
            if session is None:
                session = self._session(payload.session_id)

            return self._message_locked(payload, session)

    @staticmethod
    def _area_search(
        text: str,
        radius_m: int,
    ) -> tuple[set[int], list[str]]:
        """Разрешить посёлок из запроса и найти поверхности вокруг него.

        Важно: id поверхностей совпадают с id в результатах чата.

        Ничего не сохраняется. Ошибки источников не ломают обычный чат:
        при неудаче возвращаем пустое множество.
        """
        intent = parse_area_intent(text)
        if intent is None:
            return set(), []

        try:
            settlements = asyncio.run(
                search_settlements(intent.settlement, limit=20)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось разрешить населённый пункт: %s", exc)
            return set(), []

        if not settlements:
            return set(), []

        ids: set[int] = set()
        try:
            with get_connection() as conn:
                for place in settlements:
                    ids.update(
                        find_surface_ids_near(
                            conn, place.lat, place.lng, radius_m
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Пространственный поиск недоступен: %s", exc)
            return set(), []

        notes = [
            f"{place.name} ({place.source})" for place in settlements[:3]
        ]
        return ids, notes

    def _message_locked(
        self,
        payload: ChatMessageRequest,
        session: ChatSession,
    ) -> ChatMessageResponse:
        cached = self.store.response_for(session, payload.request_id)
        if cached is not None:
            return ChatMessageResponse.model_validate(cached)

        # Проверка триггера Roadrunner (ключевые слова "светофор", "дорога" и т.д.)
        from backend.chat.roadrunner_trigger import (
            EXIT_PROMPT,
            EXAMPLE_PROMPTS,
            check_roadrunner_trigger,
            format_roadrunner_suggestion,
            is_exit_command,
            match_example_scenario,
        )
        from uuid import uuid4

        in_roadrunner_mode = payload.mode == "roadrunner"

        if in_roadrunner_mode and is_exit_command(payload.message):
            return ChatMessageResponse(
                session_id=session.id,
                message_id=payload.request_id or uuid4(),
                message=payload.message,
                answer=(
                    "Вы вышли из режима Roadrunner. Снова обычный режим — "
                    "спрашивайте про рекламные поверхности и доступность."
                ),
                source="rules",
                pending=False,
                roadrunner_mode="exited",
            )

        # В пасхалку входим только по явному «светофор»; внутри режима
        # работают все ключевые слова Roadrunner и готовые сценарии.
        entered = "светофор" in payload.message.lower()
        trigger = check_roadrunner_trigger(payload.message)
        # Готовый сценарий может не содержать ключевых слов Roadrunner —
        # ищем его по точному тексту подсказки отдельно.
        matched_scenario = (
            match_example_scenario(payload.message) if in_roadrunner_mode else None
        )
        active_scenario = trigger.scenario or matched_scenario
        applied_scenario = None

        if in_roadrunner_mode or entered:
            if entered:
                # Текст при входе в пасхалку — фиксированный, кнопки-подсказки
                # добавляются отдельно через prompt_suggestions.
                response_text = (
                    "🎬 Режим Roadrunner активен. Опишите сценарий или "
                    "выберите готовый вариант ниже.\n"
                    "После окончания сценария баннер вернётся к настройкам "
                    "по умолчанию из базы данных."
                )
            else:
                response_text = (
                    format_roadrunner_suggestion(trigger) if trigger.active else (
                        "🎬 Режим Roadrunner активен. Опишите сценарий или "
                        "выберите готовый вариант ниже."
                    )
                )

            # Точный выбор готового сценария применяется сразу; баннер сам
            # вернётся к настройкам из БД после окончания сценария.
            if active_scenario:
                try:
                    from backend.roadrunner.services.scenario_state import (
                        apply_scenario,
                    )

                    state = apply_scenario(active_scenario)
                    applied_scenario = state
                    response_text = (
                        f"✅ Применён сценарий «{active_scenario['name']}» "
                        f"({state['duration']} с).\n\n"
                        "После завершения баннер вернётся к поведению по "
                        "умолчанию, прописанному в базе данных."
                    )
                except Exception:
                    logger.exception("Не удалось применить сценарий чата")
                    response_text = (
                        "Сценарий выбран, но не удалось сохранить его как "
                        "активный. Повторите попытку."
                    )

            return ChatMessageResponse(
                session_id=session.id,
                message_id=payload.request_id or uuid4(),
                message=payload.message,
                answer=response_text,
                source="rules",
                pending=False,
                prompt_suggestions=[
                    *(trigger.prompts or EXAMPLE_PROMPTS),
                    EXIT_PROMPT,
                ],
                roadrunner_mode="active",
                roadrunner_scenario=applied_scenario,
            )

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

        if query.year is None:
            query.year = self._default_year()

        # Вариант B: посёлок берётся из запроса, радиус 50 км задаётся
        # на лету, ничего не сохраняется. Место из текста НЕ должно
        # ограничивать обычный поиск по городу/адресу — иначе одноимённые
        # посёлки дадут пустой результат.
        area_ids: set[int] | None = None
        area_label: str | None = None
        area_hint = parse_area_intent(payload.message)
        if area_hint is not None:
            ids, notes = self._area_search(payload.message, area_hint.radius_m)
            if ids:
                area_ids = ids
                query = replace(
                    query,
                    city=None,
                    district=None,
                    address=None,
                    limit=None,
                )
                area_label = (
                    "Результаты вокруг населённого пункта из запроса: "
                    + "; ".join(notes)
                    + f". Радиус {area_hint.radius_m // 1000} км."
                )
                warnings.append(area_label)

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
            search_with_meta = getattr(self.bridge, "search_with_meta", None)
            if callable(search_with_meta):
                items, search_meta = search_with_meta(query)
                warnings.extend(search_meta.get("warnings") or [])
            else:
                items = self.bridge.search_rich(query)

            if area_ids is not None:
                items = [
                    item
                    for item in items
                    if int(item.get("id") or 0) in area_ids
                ]

            suggestions = self._suggestions(query, items)

            answer = format_answer(query, items)
            answer_source = "rules"

            if not items and suggestions:
                answer = (
                    "По заданным условиям ничего не найдено. "
                    "Ниже — похожие варианты."
                )

            # Optional "live" phrasing over the already found results.
            # llm.answer() never queries the DB and returns None on failure.
            if items:
                generated = llm.answer(
                    payload.message,
                    query,
                    items,
                    total=len(items),
                )

                if generated:
                    answer = generated
                    answer_source = "llm"

            if area_label and items:
                answer = f"{area_label}\n\n{answer}"

            response = self._response(
                session,
                query=query,
                answer=answer,
                source=source,
                items=items,
                suggestions=suggestions,
                warnings=warnings,
                answer_source=answer_source,
            )
            session.pending = None
            session.last_result_ids = [int(item["id"]) for item in items]

        # Save pending/last_result_ids regardless of request_id: a follow-up
        # clarification must survive even when the client did not send one.
        self.store.save_state(session)

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
