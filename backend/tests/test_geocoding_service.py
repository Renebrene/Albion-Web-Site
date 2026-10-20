"""Yandex geocoder/suggest proxy: parsing, region guard and missing keys."""

from __future__ import annotations

import asyncio

import pytest

from backend.services import geocoding_service as geo


@pytest.fixture(autouse=True)
def _clear_geocoding_cache():
    geo._CACHE.clear()
    _Client.calls.clear()
    yield
    geo._CACHE.clear()
    _Client.calls.clear()


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class _Client:
    calls: list[tuple[str, dict]] = []

    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def get(self, url: str, params: dict):
        self.calls.append((url, params))
        return _Response(self.payload, self.status_code)


GEOCODE_PAYLOAD = {
    "response": {
        "GeoObjectCollection": {
            "featureMember": [
                {
                    "GeoObject": {
                        "Point": {"pos": "39.696085 47.217855"},
                        "metaDataProperty": {
                            "GeocoderMetaData": {
                                "text": "Ростов-на-Дону, Большая Садовая ул., 1",
                                "precision": "exact",
                                "Address": {
                                    "Components": [
                                        {
                                            "kind": "province",
                                            "name": "Ростовская область",
                                        }
                                    ]
                                },
                            }
                        },
                    }
                }
            ]
        }
    }
}

SUGGEST_PAYLOAD = {
    "results": [
        {
            "title": {"text": "Ростов-на-Дону, Большая Садовая"},
            "subtitle": {"text": "улица"},
            "displayText": "Ростов-на-Дону, Большая Садовая",
            "uri": "ymapsbm1://geo?text=...",
        }
    ]
}


def test_geocode_parses_and_returns_coordinates(monkeypatch):
    client = _Client(GEOCODE_PAYLOAD)
    monkeypatch.setenv("ALBION_YANDEX_GEOCODER_KEY", "test-key")
    monkeypatch.setattr(geo.httpx, "AsyncClient", client)

    result = asyncio.run(geo.geocode_address("Большая Садовая 1"))

    assert result["lat"] == pytest.approx(47.217855)
    assert result["lon"] == pytest.approx(39.696085)
    assert result["address"].startswith("Ростов-на-Дону")
    assert result["source"] == "Yandex Geocoder"
    params = client.calls[0][1]
    # Без явного города «Курчатова» находилась в Волгодонске.
    assert "Ростов-на-Дону" in params["geocode"]
    assert "bbox" not in params
    assert "rspn" not in params


def test_geocode_rejects_outside_region(monkeypatch):
    payload = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": GEOCODE_PAYLOAD["response"][
                    "GeoObjectCollection"
                ]["featureMember"]
            }
        }
    }
    payload["response"]["GeoObjectCollection"]["featureMember"][0][
        "GeoObject"
    ]["Point"]["pos"] = "30.0 59.0"
    monkeypatch.setenv("ALBION_YANDEX_GEOCODER_KEY", "test-key")
    monkeypatch.setattr(geo.httpx, "AsyncClient", _Client(payload))

    with pytest.raises(geo.GeocodingNotFound):
        asyncio.run(geo.geocode_address("Москва, Красная площадь"))


def test_suggest_normalizes_yandex_payload(monkeypatch):
    monkeypatch.setenv("ALBION_YANDEX_SUGGEST_KEY", "test-key")
    client = _Client(SUGGEST_PAYLOAD)
    monkeypatch.setattr(geo.httpx, "AsyncClient", client)

    result = asyncio.run(geo.suggest_address("Большая"))

    assert result[0]["title"] == "Ростов-на-Дону, Большая Садовая"
    assert result[0]["display_name"] == "Ростов-на-Дону, Большая Садовая"

    params = client.calls[0][1]
    assert params["ll"] == geo.ROSTOV_BIAS_LL
    assert params["spn"] == geo.ROSTOV_BIAS_SPN
    # Регион в тексте запроса переносил выдачу в Волгодонск/другие города.
    assert "Ростовская область" not in params["text"]
    assert "bbox" not in params


def test_missing_geocoder_key_returns_unavailable(monkeypatch):
    monkeypatch.delenv("ALBION_YANDEX_GEOCODER_KEY", raising=False)
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)

    with pytest.raises(geo.GeocodingUnavailable):
        asyncio.run(geo.geocode_address("Большая Садовая 1"))


def test_reverse_without_key_returns_null_fields(monkeypatch):
    monkeypatch.delenv("ALBION_YANDEX_GEOCODER_KEY", raising=False)
    monkeypatch.delenv("YANDEX_API_KEY", raising=False)

    result = asyncio.run(geo.reverse_geocode(47.2, 39.7))

    assert result["address"] is None
    assert result["district"] is None
    assert result["detail"]
