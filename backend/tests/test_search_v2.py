"""Search v2: normalization, strict locations, catalog matching, LLM guard."""

from __future__ import annotations

from pathlib import Path

import pytest

import engine
from engine.dictionary.synonym_dictionary import SynonymDictionary
from engine.query.query import SearchQuery
from engine.storage.models import AvailabilityRecord, SurfaceRecord

from backend.chat import llm
from backend.chat.models import ChatMessageRequest
from backend.chat.query_validation import meaningful, validate_llm_entities
from backend.chat.service import ChatService
from backend.chat.store import ChatStore
from backend.search.catalog import CatalogEntry, CatalogSnapshot
from backend.search.mapper import SiteSurfaceMapper
from backend.search.normalization import (
    LocationResolver,
    TypeResolver,
    normalize_text,
    parse_dimensions,
    same_size,
)
from backend.search.v2.service import SearchV2Service


def dictionary() -> SynonymDictionary:
    path = Path(engine.__file__).parent / "dictionary" / "synonyms.json"
    return SynonymDictionary(path)


def availability(surface_id: int, prices: dict[int, int]) -> dict:
    return {
        2026: {
            month: AvailabilityRecord(
                surface_id=surface_id,
                year=2026,
                month=month,
                status="FREE",
                price=price,
                load_percent=10,
            )
            for month, price in prices.items()
        }
    }


def surface(
    surface_id: int,
    *,
    city: str = "Ростов-на-Дону",
    district: str | None = "Ростов-на-Дону",
    media_type: str = "Щит",
    size: str = "6 X 3 Метр",
    price: int = 10000,
) -> SurfaceRecord:
    return SurfaceRecord(
        id=surface_id,
        city=city,
        district=district,
        title=f"Конструкция {surface_id}",
        address="Ленина пр-кт 1",
        side="A",
        media_type=media_type,
        size=size,
        price=price,
    )


def entry(record: SurfaceRecord, prices: dict[int, int]) -> CatalogEntry:
    area = None
    if "район" in normalize_text(record.city):
        area = normalize_text(record.city)
    elif record.district and "район" in normalize_text(record.district):
        area = normalize_text(record.district)

    return CatalogEntry(
        surface=record,
        type_norm=normalize_text(record.media_type),
        city_norm=normalize_text(record.city),
        district_norm=normalize_text(record.district),
        area_norm=area,
        size_dims=parse_dimensions(record.size),
        availability=availability(record.id, prices),
    )


def snapshot(entries: list[CatalogEntry]) -> CatalogSnapshot:
    return CatalogSnapshot(
        version="test",
        built_at=0.0,
        entries=tuple(entries),
        by_id={item.surface.id: item for item in entries},
        types={"Щит": 2},
        cities=tuple({item.surface.city for item in entries}),
        areas=tuple(
            item.surface.city for item in entries if item.area_norm is not None
        ),
        years=(2026,),
        size_parse_failures=0,
    )


class FakeCatalog:
    def __init__(self, snap: CatalogSnapshot):
        self._snap = snap

    def snapshot(self) -> CatalogSnapshot:
        return self._snap

    def default_year(self) -> int:
        return 2026


def service_with(entries: list[CatalogEntry]) -> SearchV2Service:
    return SearchV2Service(
        catalog=FakeCatalog(snapshot(entries)),
        dictionary=dictionary(),
    )


def test_size_dimensions_ignore_separator_and_order():
    assert same_size("1,2 X 1,8 Метр", "1.8x1.2")
    assert same_size("6 X 3 Метр", "3*6")
    assert same_size("3,77 X 2,8 Метр", "2.8x3.77")
    assert not same_size("6 X 3 Метр", "6 X 4 Метр")
    assert parse_dimensions("мусор") is None


def test_type_resolver_uses_real_catalog_type():
    resolver = TypeResolver(["Скроллер", "Сити-формат"], dictionary())

    resolved, warning = resolver.resolve("Сити-борд")
    assert resolved == "Скроллер"
    assert warning

    resolved, warning = resolver.resolve("скроллер")
    assert resolved == "Скроллер"
    assert warning is None

    resolved, warning = resolver.resolve("несуществующий")
    assert resolved is None
    assert warning and "отсутствует" in warning


def test_location_resolves_area_forms():
    resolver = LocationResolver(
        ["Ростов-на-Дону"],
        ["ОКТЯБРЬСКИЙ РАЙОН", "МЯСНИКОВСКИЙ РАЙОН"],
    )

    assert resolver.resolve_area("Октябрьском") == "ОКТЯБРЬСКИЙ РАЙОН"
    assert resolver.resolve_area("мясниковский") == "МЯСНИКОВСКИЙ РАЙОН"
    assert resolver.resolve_area("неизвестный") is None


def test_strict_city_and_area_are_combined_with_and():
    rostov = entry(surface(1), {10: 10000})
    district = entry(
        surface(2, city="ОКТЯБРЬСКИЙ РАЙОН", district="ОКТЯБРЬСКИЙ РАЙОН"),
        {10: 10000},
    )
    service = service_with([rostov, district])

    items, meta = service.search(
        SearchQuery(
            city="Ростов-на-Дону",
            district="Октябрьский",
            media_type="Щит",
        )
    )
    assert meta["total"] == 0
    assert meta["warnings"]

    items, meta = service.search(
        SearchQuery(district="Октябрьский", media_type="Щит")
    )
    assert meta["total"] == 1
    assert items[0]["district"] == "ОКТЯБРЬСКИЙ РАЙОН"


def test_v2_matches_size_and_returns_total_before_limit():
    first = entry(surface(1), {10: 10000})
    second = entry(surface(2, size="1,2 X 1,8 Метр"), {10: 12000})
    service = service_with([first, second])

    items, meta = service.search(SearchQuery(size="3x6", limit=1))

    assert meta["total"] == 1
    assert len(items) == 1

    items, meta = service.search(SearchQuery(size="1.8x1.2"))
    assert meta["total"] == 1
    assert items[0]["size"] == "1,2 X 1,8 Метр"


def test_primary_month_is_first_requested_month():
    item = entry(surface(1), {10: 10000, 11: 12000})
    service = service_with([item])

    items, _ = service.search(
        SearchQuery(months=[11, 10], period_mode="ANY")
    )

    assert items[0]["price"] == 12000
    assert items[0]["monthly_prices"] == {10: 10000, 11: 12000}


def test_llm_all_null_is_not_meaningful():
    values = {
        "city": None,
        "media_type": None,
        "months": [],
        "year": 2026,
    }
    assert meaningful(values) is False

    clean, warnings = validate_llm_entities(values, dictionary())
    assert clean == {}
    assert warnings == []


def test_llm_values_are_clamped_and_canonicalized():
    values = {
        "city": "ростов",
        "media_type": "скроллер",
        "month": 13,
        "year": 1999,
        "limit": 100000,
        "sort_by": "hack",
        "availability": "занято",
        "max_price": "20000",
    }

    clean, warnings = validate_llm_entities(values, dictionary())

    assert clean["city"] == "Ростов-на-Дону"
    assert clean["media_type"] == "Сити-борд"
    assert "month" not in clean
    assert "year" not in clean
    assert "limit" not in clean
    assert "sort_by" not in clean
    assert "availability" not in clean
    assert clean["max_price"] == 20000
    assert warnings


def test_memory_store_is_bounded_and_serializes_session():
    bounded = ChatStore(max_sessions=2)

    for _ in range(3):
        bounded.create()

    assert len(bounded._sessions) <= 2

    store = ChatStore()
    first = store.create()

    with store.session_lock(first.id):
        inside = store.get(first.id)
        assert inside is not None


def test_map_many_uses_preloaded_maps_and_deduplicates():
    row = {
        "id": 1,
        "uuid": None,
        "city": "Ростов-на-Дону",
        "district": "Ростов-на-Дону",
        "title": "Щит",
        "address": "Ленина пр-кт 1",
        "side": "A",
        "media_type": "Щит",
        "type": "Щит",
        "size": "6 X 3 Метр",
        "price": "15 400",
        "external_id": "1",
        "latitude": 47.2,
        "longitude": 39.7,
        "light": "да",
        "material": None,
        "address_key": None,
        "surface_hash": "hash-1",
        "is_active": True,
        "created_at": None,
        "updated_at": None,
    }

    surfaces = SiteSurfaceMapper.map_many(
        [row, row],
        fields_map={},
        overrides_map={},
        media_map={},
    )

    assert len(surfaces) == 1
    assert surfaces[0].price == 15400


def test_v2_search_over_large_catalog_is_fast():
    entries = [
        entry(
            surface(
                index,
                city="Ростов-на-Дону" if index % 2 else "Таганрог",
                size="6 X 3 Метр" if index % 3 else "1,2 X 1,8 Метр",
            ),
            {10: 10000, 11: 12000},
        )
        for index in range(1, 2001)
    ]
    service = service_with(entries)

    _items, meta = service.search(
        SearchQuery(media_type="Щит", size="3x6", months=[10], limit=20)
    )

    assert meta["total"] > 0
    assert meta["took_ms"] < 200


def test_llm_answer_uses_grounded_results(monkeypatch):
    class FakeBridge:
        def default_year(self):
            return 2026

        def search_rich(self, query):
            return [
                {
                    "id": 1,
                    "type": "Щит",
                    "city": "Ростов-на-Дону",
                    "address": "Ленина пр-кт 1",
                    "side": "A",
                    "size": "6 X 3 Метр",
                    "price": 15400,
                    "status": "Свободно",
                    "month_texts": {11: "Свободно"},
                }
            ]

    monkeypatch.setattr(
        llm,
        "answer",
        lambda question, query, items, **kwargs: (
            "Нашёл один свободный щит на Ленина, 15 400 ₽."
        ),
    )

    service = ChatService(bridge=FakeBridge(), store=ChatStore())
    response = service.message(
        ChatMessageRequest(message="свободные щиты в Ростове на ноябрь")
    )

    assert response.answer_source == "llm"
    assert "Нашёл один" in response.answer


def test_llm_answer_is_none_when_disabled(monkeypatch):
    monkeypatch.setenv("ALBION_CHAT_LLM_ENABLED", "false")

    assert (
        llm.answer("вопрос", SearchQuery(city="Ростов-на-Дону"), [{"id": 1}])
        is None
    )


def test_chat_rejects_all_null_llm_response(monkeypatch):
    class FakeBridge:
        def default_year(self):
            return 2026

        def search_rich(self, query):
            return []

    monkeypatch.setattr(
        llm,
        "extract",
        lambda text: llm.EntityExtraction(
            {"city": None, "media_type": None, "months": []}
        ),
    )

    service = ChatService(bridge=FakeBridge(), store=ChatStore())

    with pytest.raises(ValueError):
        service.message(ChatMessageRequest(message="непонятный запрос"))
