"""Интеграционный срез: посёлок из запроса -> фильтр по конструкциям рядом."""
from contextlib import nullcontext
from uuid import uuid4

from backend.chat import service as chat_service
from backend.chat.models import ChatMessageRequest
from backend.chat.service import ChatService
from engine.query.query import SearchQuery


class _Session:
    def __init__(self):
        self.id = uuid4()
        self.pending = None
        self.last_result_ids: list[int] = []


class _Store:
    def create(self):
        return _Session()

    def session_lock(self, session_id):
        return nullcontext()

    def response_for(self, session, request_id):
        return None

    def save_state(self, session):
        pass

    def remember_response(self, session, request_id, payload):
        pass


class _Bridge:
    def __init__(self):
        self.last_query = None
        self.items = [
            {"id": 101, "city": "Ростов-на-Дону", "address": "ул. Тестовая", "type": "Щит"},
            {"id": 999, "city": "Ростов-на-Дону", "address": "ул. Другая", "type": "Щит"},
        ]

    def search_rich(self, query):
        self.last_query = query
        return list(self.items)

    def default_year(self):
        return 2026


def _make_service(monkeypatch):
    bridge = _Bridge()
    service = ChatService(bridge=bridge, store=_Store())
    monkeypatch.setattr(service, "_refresh_dictionary", lambda: None)
    monkeypatch.setattr(
        service,
        "_parse",
        lambda text: (SearchQuery(), "rules", [], None),
    )
    monkeypatch.setattr(chat_service.llm, "answer", lambda *a, **kw: None)
    monkeypatch.setattr(chat_service.llm, "answers_enabled", lambda: False)
    return service, bridge


def test_area_filter_applied_to_chat_results(monkeypatch):
    service, bridge = _make_service(monkeypatch)
    monkeypatch.setattr(
        ChatService,
        "_area_search",
        staticmethod(
            lambda text, radius: (
                {101}, ["Красный Колос (test)"], {101: 1200.0}
            )
        ),
    )

    response = service.message(
        ChatMessageRequest(message="найди конструкции в районе поселка Красный Колос")
    )

    assert [item["id"] for item in response.results.items] == [101]
    assert any("радиус 5 км" in w.casefold() for w in response.warnings)
    assert "Красный Колос" in response.answer
    assert "радиус 5 км" in response.answer.casefold()
    # Место из запроса не должно уходить в обычный поиск по городу/адресу.
    assert bridge.last_query.city is None
    assert bridge.last_query.district is None
    assert bridge.last_query.address is None
    assert bridge.last_query.limit is None


def test_area_results_sorted_by_distance(monkeypatch):
    service, bridge = _make_service(monkeypatch)
    monkeypatch.setattr(
        ChatService,
        "_area_search",
        staticmethod(
            lambda text, radius: (
                {101, 999}, ["Красный Колос (test)"],
                {101: 4200.0, 999: 800.0},
            )
        ),
    )

    response = service.message(
        ChatMessageRequest(message="щиты в районе поселка Красный Колос")
    )

    assert [item["id"] for item in response.results.items] == [999, 101]


def test_no_area_intent_keeps_ordinary_search(monkeypatch):
    service, bridge = _make_service(monkeypatch)
    called = []

    def fake_area(text, radius):
        called.append(text)
        return set(), [], {}

    monkeypatch.setattr(ChatService, "_area_search", staticmethod(fake_area))

    response = service.message(ChatMessageRequest(message="щиты в Ростове"))

    assert [item["id"] for item in response.results.items] == [101, 999]
    assert called == []
