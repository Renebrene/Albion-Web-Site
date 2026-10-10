from __future__ import annotations

from uuid import UUID

from engine.house_number.matcher import HouseNumberMatcher
from engine.storage.models import AvailabilityRecord, SurfaceRecord

from backend.chat.models import ChatMessageRequest
from backend.chat.service import ChatService
from backend.search.bridge import AlbionSearchBridge
from backend.search.api import SearchRequest


class FakeRepository:
    def get_availabilities_for_surfaces(self, **_kwargs):
        return {
            1: [
                AvailabilityRecord(
                    surface_id=1,
                    year=2026,
                    month=10,
                    status="FREE",
                    price=100,
                    load_percent=10,
                    raw_value="10%",
                ),
                AvailabilityRecord(
                    surface_id=1,
                    year=2026,
                    month=11,
                    status="FREE",
                    price=110,
                    load_percent=20,
                    raw_value="20%",
                ),
            ]
        }


class FakeService:
    def __init__(self):
        self.repository = FakeRepository()

    def search(self, _query):
        return [
            SurfaceRecord(
                id=1,
                city="Ростов-на-Дону",
                district="Октябрьский",
                title="Щит 1",
                address="Ленина 105",
                side="A",
                media_type="Щит",
                size="6 X 3 Метр",
                price=90,
                latitude=47.2,
                longitude=39.7,
                metadata={
                    "type": "Щит",
                    "photo_large": "photos/one.jpg",
                    "map_large": "maps/one.jpg",
                },
            )
        ]


def fake_bridge():
    bridge = AlbionSearchBridge.__new__(AlbionSearchBridge)
    bridge.service = FakeService()
    bridge.repository = bridge.service.repository
    return bridge


def test_rich_bridge_preserves_monthly_load_and_primary_month():
    bridge = fake_bridge()
    query = SearchRequest(
        district="Октябрьский",
        months=[10, 11],
        sort_by="load_asc",
    ).to_search_query()

    items = bridge.search_rich(query)

    assert items[0]["district"] == "Октябрьский"
    assert items[0]["load_percent"] == 15
    assert items[0]["monthly_loads"] == {10: 10, 11: 20}
    assert items[0]["photo_large"] == "photos/one.jpg"
    assert items[0]["lat"] == 47.2


def test_chat_clarification_can_be_resolved():
    service = ChatService(bridge=fake_bridge())
    first = service.message(ChatMessageRequest(message="Покажи конструкции 3x6"))

    assert first.pending is True
    assert first.clarification is not None

    second = service.message(
        ChatMessageRequest(session_id=first.session_id, message="статика")
    )

    assert second.pending is False
    assert second.query.media_type == "Щит"
    assert second.results.count == 1


def test_three_month_hyphen_query_is_normalized():
    service = ChatService(bridge=fake_bridge())
    query, _source, _warnings, _clarification = service._parse(
        "Покажи экраны в октябре-ноябре-декабре"
    )

    assert query.media_type == "Видеоэкран"
    assert query.months == [10, 11, 12]
    assert query.period_mode == "ALL"


def test_service_verb_and_limit_are_not_parsed_as_address():
    service = ChatService(bridge=fake_bridge())

    query, _source, _warnings, _clar = service._parse(
        "подбери 20 экранов в Ростове с наименьшей загруженностью"
    )

    assert query.address is None
    assert query.limit == 20
    assert query.sort_by == "load_asc"
    assert query.media_type == "Видеоэкран"
    assert query.city == "Ростов-на-Дону"


def test_show_verb_with_number_sets_limit():
    service = ChatService(bridge=fake_bridge())
    query, *_ = service._parse("покажи 5 щитов в Таганроге")
    assert query.limit == 5
    assert query.address is None


class SuggestBridge:
    """Empty on strict address+type, non-empty on relaxed variants."""

    def search_rich(self, query):
        if query.address and query.media_type:
            return []
        if query.media_type:
            return [
                {
                    "id": 1,
                    "type": query.media_type,
                    "media_type": query.media_type,
                    "city": "Ростов",
                    "address": "Сельмаш пр-кт 9",
                    "price": 13000,
                    "monthly_prices": {},
                    "monthly_statuses": {},
                }
            ]
        return [
            {
                "id": 2,
                "type": "Щит",
                "media_type": "Щит",
                "city": "Ростов",
                "address": "Привокзальная пл. 1",
                "price": 40000,
                "monthly_prices": {},
                "monthly_statuses": {},
            }
        ]


def test_missing_match_returns_suggestions():
    service = ChatService(bridge=SuggestBridge())
    response = service.message(
        ChatMessageRequest(message="пиллар на Привокзальной")
    )

    assert response.results.count == 0
    assert len(response.suggestions) == 2
    assert response.suggestions[0].type == "similar_type"
    assert response.suggestions[1].type == "same_address"
    assert "не найдено" in response.answer.lower()


def test_unknown_session_starts_new_one():
    from uuid import uuid4

    service = ChatService(bridge=fake_bridge())
    response = service.message(
        ChatMessageRequest(
            session_id=uuid4(),
            message="Покажи щиты",
        )
    )

    # No error: a stale session transparently becomes a brand new session.
    assert response.session_id is not None
    assert response.results.count == 1


def test_load_sort_ties_are_alphabetical_and_limited_after_sort():
    items = [
        {"id": 1, "load_percent": 4, "price": 100, "city": "Ростов", "address": "Ясная 1", "side": "A"},
        {"id": 2, "load_percent": 4, "price": 100, "city": "Ростов", "address": "Айвазовского 2", "side": "A"},
        {"id": 3, "load_percent": 8, "price": 100, "city": "Ростов", "address": "Батуринская 3", "side": "A"},
        {"id": 4, "load_percent": 4, "price": 100, "city": "Ростов", "address": "Айвазовского 2", "side": "Б"},
        {"id": 5, "load_percent": None, "price": 100, "city": "Ростов", "address": "Азовская 5", "side": "A"},
    ]
    query = SearchRequest(sort_by="load_asc", limit=3).to_search_query()

    result = AlbionSearchBridge._sort_and_limit(list(items), query)

    assert [item["id"] for item in result] == [2, 4, 1]
    # NULL load and the higher percentage are pushed to the tail.
    assert result[-1]["load_percent"] == 4

    try:
        SearchRequest(availability="FREE")
    except Exception as exc:
        assert "месяц" in str(exc)
    else:
        raise AssertionError("FREE without period must be rejected")


def test_district_is_extracted_from_rayon_phrase():
    service = ChatService(bridge=fake_bridge())

    query, _source, _warnings, _clar = service._parse(
        "Покажи щиты в Октябрьском районе"
    )
    assert query.district == "октябрьский"

    query2, *_ = service._parse("покажи конструкции мясниковском районе")
    assert query2.district == "мясников"


def test_district_matches_site_city_field():
    surface = SurfaceRecord(
        id=1,
        city="ОКТЯБРЬСКИЙ РАЙОН",
        district="ОКТЯБРЬСКИЙ РАЙОН",
        title="Щит",
        address="Поворот на Мелиховку",
        side="A",
        media_type="Щит",
        size="6 X 3",
    )
    assert AlbionSearchBridge._matches_district(surface, "октябрьский")
    assert not AlbionSearchBridge._matches_district(surface, "пролетарский")


def test_house_number_range_contains_single_number():
    match = HouseNumberMatcher.score("105", "105-107")
    assert match.score == 80
    assert HouseNumberMatcher.best_match("105", ["105-107"]) is not None


def test_location_matches_address_and_title():
    surface = SurfaceRecord(
        id=2,
        city="МЯСНИКОВСКИЙ РАЙОН",
        district="МЯСНИКОВСКИЙ РАЙОН",
        title="Щит на трассе",
        address="Трасса М-23 (Ростов-Таганрог в сторону Ростова)",
        side="A",
        media_type="Щит",
        size="6 X 3",
    )
    # Not the city, but the address contains the location word.
    assert AlbionSearchBridge._matches_location(surface, ["таганрог"])
    assert not AlbionSearchBridge._matches_location(surface, ["батайск"])


def test_location_search_covers_city_address_and_title():
    the_surface = SurfaceRecord(
        id=3,
        city="Ростов-на-Дону",
        district="Ростов-на-Дону",
        title="Таганрогское шоссе",
        address="Таганрогская ул. 10",
        side="A",
        media_type="Щит",
        size="6 X 3",
    )
    assert AlbionSearchBridge._matches_location(the_surface, ["таганрог"])

    class Repo:
        def get_availabilities_for_surfaces(self, **_kwargs):
            return {}

    class Service:
        def __init__(self):
            self.repository = Repo()

        def search(self, _query):
            return [the_surface]

    bridge = AlbionSearchBridge.__new__(AlbionSearchBridge)
    bridge.service = Service()
    bridge.repository = bridge.service.repository

    query = SearchRequest(city="Таганрог", media_type="Щит").to_search_query()
    assert len(bridge.search_rich(query)) == 1
