"""Регрессионные тесты модуля roadrunner (3D-баннер «Светофорные объекты»).

Покрывают места, которые уже ломались:
- JSONB-колонки приходят из psycopg словарём, а не строкой;
- сценарии ищутся по slug без расширения .json;
- модель погоды детерминирована между воркерами;
- шаблон баннера содержит переменные, без которых падает рендер;
- админский CRUD сценариев и публичные CORS-заголовки.
"""
from __future__ import annotations

import datetime
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.roadrunner.scenario.engine import (
    ScenarioEngine,
    validate_scenario,
)
from backend.roadrunner.services import llm_agent, weather
from backend.roadrunner.services.db_json import as_dict
from backend.services.auth_api import require_admin
from backend.services.home_service import BANNER_CODE_CSP
from backend.tests.conftest import requires_db

client = TestClient(app)

BANNER_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "road_banner.html"
)


@pytest.fixture
def admin():
    """Подменить проверку прав, чтобы CSRF/cookie не влияли на тест."""
    app.dependency_overrides[require_admin] = lambda: {
        "id": 1,
        "role": "admin",
    }
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_admin, None)


# --- Чтение JSONB ---------------------------------------------------------


def test_as_dict_accepts_already_parsed_jsonb():
    assert as_dict({"llm_provider": "ollama"}) == {"llm_provider": "ollama"}


def test_as_dict_accepts_json_string_and_bytes():
    assert as_dict('{"a": 1}') == {"a": 1}
    assert as_dict(b'{"a": 1}') == {"a": 1}


def test_as_dict_handles_empty_values():
    assert as_dict(None) == {}
    assert as_dict("null") == {}


def test_get_llm_config_reads_roadrunner_settings_key(monkeypatch):
    """Настройки LLM лежат в ключе 'roadrunner', а не 'llm_config'."""
    stored = {
        "llm_provider": "openai",
        "llm_model": "gpt-test",
        "llm_url": "http://llm.test",
        "llm_api_key": "secret-test",
        "temperature": 0.7,
    }

    class _Cursor:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return (stored,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            return _Cursor()

    monkeypatch.setattr(llm_agent, "get_connection", lambda: _Connection())

    config = llm_agent.get_llm_config()

    assert config["provider"] == "openai"
    assert config["model"] == "gpt-test"
    assert config["url"] == "http://llm.test"
    assert config["api_key"] == "secret-test"
    assert config["temperature"] == 0.7


def test_scenario_engine_from_db_accepts_jsonb_dict(monkeypatch):
    """from_db() не должна вызывать json.loads() на уже готовом dict."""
    scenario = {
        "id": "pytest-scenario",
        "duration": 30,
        "events": [{"t": 0, "do": "end"}],
    }

    class _Cursor:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return (scenario,)

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            return _Cursor()

    monkeypatch.setattr(
        "backend.roadrunner.scenario.engine.get_connection",
        lambda: _Connection(),
    )

    engine = ScenarioEngine.from_db(42)

    assert engine.scenario_id == "pytest-scenario"
    assert engine.duration == 30
    assert engine.events == scenario["events"]


# --- Сценарии -------------------------------------------------------------


def test_chat_trigger_offers_example_prompts():
    from backend.chat.roadrunner_trigger import (
        EXAMPLE_PROMPTS,
        check_roadrunner_trigger,
        match_example_scenario,
    )

    trigger = check_roadrunner_trigger("светофор")

    assert trigger.active
    assert len(trigger.prompts) == len(EXAMPLE_PROMPTS) >= 3
    assert trigger.prompts[0] in EXAMPLE_PROMPTS

    scenario = match_example_scenario(EXAMPLE_PROMPTS[0])
    assert scenario is not None
    assert scenario["events"]
    assert scenario["events"][-1]["do"] == "end"


def test_inactive_chat_trigger_has_no_prompts():
    from backend.chat.roadrunner_trigger import check_roadrunner_trigger

    trigger = check_roadrunner_trigger(" свободные щиты на декабрь ")

    assert not trigger.active
    assert trigger.prompts == []


@requires_db
def test_active_scenario_roundtrip():
    from backend.roadrunner.services import scenario_state

    scenario_state.clear_active_scenario()
    try:
        payload = scenario_state.apply_scenario(
            {"id": "pytest-active", "duration": 30, "events": []}
        )
        active = scenario_state.get_active_scenario()

        assert payload["duration"] == 30
        assert active is not None
        assert active["scenario"]["id"] == "pytest-active"
    finally:
        scenario_state.clear_active_scenario()

    assert scenario_state.get_active_scenario() is None


def test_scenario_engine_from_file_accepts_slug_without_extension():
    engine = ScenarioEngine.from_file("rostov-evening-rain")

    assert engine.scenario_id == "rostov-evening-rain"
    assert len(engine.events) >= 10


def test_validate_scenario_accepts_remove_pedestrian():
    payload = {
        "id": "test",
        "name": "test",
        "duration": 10,
        "events": [
            {"t": 0, "do": "add_pedestrian"},
            {"t": 5, "do": "remove_pedestrian"},
        ],
    }

    assert validate_scenario(payload) == []


# --- Погода ---------------------------------------------------------------


def test_weather_noise_is_deterministic():
    now = datetime.datetime(2026, 11, 24, 20, 41)

    assert weather._hour_seed(now) == 2026112420
    assert weather._noise(12345, 5) == weather._noise(12345, 5)
    assert 0 <= weather._noise(12345, 5) < 5


@pytest.mark.parametrize(
    "score, label",
    [(0, "свободно"), (3, "свободно"), (4, "умеренно"),
     (6, "умеренно"), (7, "пробки"), (9, "пробки"), (10, "затор")],
)
def test_traffic_score_uses_yandex_gradation(score, label):
    service = weather.TrafficService.__new__(weather.TrafficService)
    assert service._score_to_label(score) == label


def test_model_weather_is_stable_within_hour():
    service = weather.WeatherService.__new__(weather.WeatherService)

    first = service._model_weather()
    second = service._model_weather()

    def snapshot(data):
        return (
            data.condition,
            data.temperature_c,
            data.humidity,
            data.wind_speed_kmh,
            data.source,
        )

    assert snapshot(first) == snapshot(second)


# --- Шаблон баннера -------------------------------------------------------


def test_banner_template_has_runtime_variables_and_month_fix():
    code = BANNER_TEMPLATE.read_text(encoding="utf-8")

    # Без этих объявлений скрипт падал до первой отрисовки.
    for declaration in (
        "let dirty = true;",
        "let inView = true;",
        "let frames = 0;",
        "let last = performance.now();",
    ):
        assert declaration in code

    # Часы и дата в HUD больше не показываются.
    assert "hudClock" not in code
    assert "hudDate" not in code
    assert "hudTrafficDot" in code


def test_banner_csp_allows_same_origin_requests():
    assert "connect-src 'self'" in BANNER_CODE_CSP
    assert "sandbox allow-scripts" in BANNER_CODE_CSP


# --- Публичные эндпоинты --------------------------------------------------


def test_weather_proxy_sets_cors_header(monkeypatch):
    class _FakeWeather:
        async def get_current(self):
            return weather.WeatherData(
                condition="clear",
                temperature_c=10,
                humidity=50,
                wind_speed_kmh=5,
                precipitation_mm=0,
                source="test",
                cached_at=0,
            )

    async def _fake_service():
        return _FakeWeather()

    monkeypatch.setattr(
        "backend.api.roadrunner.get_weather_service", _fake_service
    )

    response = client.get("/api/roadrunner/weather-proxy")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.json()["weather_code"] == 0


def test_traffic_sets_cors_header(monkeypatch):
    from backend.roadrunner.services.weather import TrafficData

    class _FakeTraffic:
        async def get_current(self):
            return TrafficData(
                score=3, label="умеренно", source="test", cached_at=0
            )

    async def _fake_service():
        return _FakeTraffic()

    monkeypatch.setattr(
        "backend.api.roadrunner.get_traffic_service", _fake_service
    )

    response = client.get("/api/roadrunner/traffic")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


# --- Интеграция с БД ------------------------------------------------------


@requires_db
def test_settings_roundtrip(admin):
    before = client.get("/api/roadrunner/settings")

    assert before.status_code == 200
    settings = before.json()["settings"]
    assert isinstance(settings, dict)

    saved = client.put("/api/roadrunner/settings", json=settings)
    assert saved.status_code == 200, saved.text

    after = client.get("/api/roadrunner/settings").json()["settings"]
    assert after == settings


@requires_db
def test_scenario_create_get_list_delete(admin):
    slug = "pytest-roadrunner-" + uuid.uuid4().hex
    payload = {
        "id": slug,
        "name": "Тестовый сценарий",
        "duration": 10,
        "events": [{"t": 0, "do": "end"}],
    }

    created = client.post("/api/roadrunner/scenarios", json=payload)
    assert created.status_code == 200, created.text
    db_id = created.json()["db_id"]
    assert db_id

    try:
        fetched = client.get(f"/api/roadrunner/scenarios/{db_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["scenario"][0]["do"] == "end"

        listed = client.get("/api/roadrunner/scenarios").json()["scenarios"]
        assert any(item.get("db_id") == db_id for item in listed)
    finally:
        deleted = client.delete(f"/api/roadrunner/scenarios/{db_id}")
        assert deleted.status_code == 200, deleted.text

    assert client.get(f"/api/roadrunner/scenarios/{db_id}").status_code == 404


@requires_db
def test_delete_missing_file_scenario_returns_404(admin):
    response = client.delete(
        "/api/roadrunner/scenarios/pytest-no-such-scenario"
    )

    assert response.status_code == 404
    assert "файловые" in response.json()["detail"].lower()
