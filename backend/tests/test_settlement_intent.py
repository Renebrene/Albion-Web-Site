"""Тесты распознавания населённого пункта в запросе чата."""
from backend.chat.settlement_intent import parse_area_intent
from backend.search.spatial import RADIUS_M_DEFAULT


def test_user_example():
    intent = parse_area_intent("найди конструкции в районе поселка Красный Колос")
    assert intent is not None
    assert intent.settlement_norm == "красный колос"
    assert intent.radius_m == RADIUS_M_DEFAULT == 5_000


def test_yo_and_poselok_marker():
    intent = parse_area_intent("найди конструкции в районе посёлка Красный Колос")
    assert intent is not None and intent.settlement_norm == "красный колос"


def test_in_poselke_and_nearby():
    for text in (
        "щиты в посёлке Красный Колос",
        "покажи конструкции в селе Новый",
        "посёлок Красный Колос",
        "баннеры около Красного Колоса",
    ):
        assert parse_area_intent(text) is not None, text


def test_name_trimmed_at_type_and_period():
    intent = parse_area_intent(
        "щиты в посёлке Красный Колос свободные в июне"
    )
    assert intent is not None
    assert intent.settlement_norm == "красный колос"


def test_no_settlement():
    assert parse_area_intent("щиты 2x3") is None
    assert parse_area_intent("подбери щит 6x3") is None
    assert parse_area_intent("") is None
