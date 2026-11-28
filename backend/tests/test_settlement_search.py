"""Тесты виртуального/постепенного резолвера населённых пунктов.

Никаких сетевых вызовов и записей в БД: провайдеры подменены заглушками.
"""
import asyncio

import backend.services.settlement_search as ss


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _Client:
    def __init__(self, *, get_payload=None, post_payload=None):
        self._get_payload = get_payload
        self._post_payload = post_payload

    async def get(self, url, params=None):
        return _Response(self._get_payload)

    async def post(self, url, data=None):
        return _Response(self._post_payload)

    async def aclose(self):
        pass


def _yandex_member(lat, lng, name, region="Ростовская область", kind="locality"):
    return {
        "GeoObject": {
            "Point": {"pos": f"{lng} {lat}"},
            "metaDataProperty": {
                "GeocoderMetaData": {
                    "kind": kind,
                    "text": f"{name}, {region}",
                    "Address": {
                        "Components": [
                            {"kind": "province", "name": region},
                            {"kind": "locality", "name": name},
                        ]
                    },
                }
            },
        }
    }


YANDEX_PAYLOAD = {
    "response": {
        "GeoObjectCollection": {
            "featureMember": [
                _yandex_member(47.9, 40.1, "Красный Колос"),
                _yandex_member(48.1, 41.2, "Красный Колос"),  # второй such
                _yandex_member(48.8, 40.1, "Красный Колос", region="Воронежская область"),
                _yandex_member(47.9, 40.1, "Улица Ленина", kind="street"),
            ]
        }
    }
}

OSM_PAYLOAD = [
    {"category": "place", "type": "village", "name": "Красный Колос",
     "lat": "47.91", "lon": "40.11", "display_name": "Красный Колос, Ростовская область"},
    {"category": "place", "type": "hamlet", "name": "Красный Колос",
     "lat": "48.11", "lon": "41.21", "display_name": "Красный Колос, Ростовская область"},
    {"category": "place", "type": "village", "name": "Красный Колос",
     "lat": "51.0", "lon": "40.1", "display_name": "Красный Колос, Москва"},  # вне bbox
    {"category": "place", "type": "street", "name": "Красный Колос",
     "lat": "47.9", "lon": "40.1", "display_name": "Красный Колос, Ростовская область"},
]


def test_normalize_and_canonicalize():
    assert ss.normalize_name("посёлок Красный Колос") == "красный колос"
    assert ss.normalize_name("с. Новый, Ростовский район") == "новый"

    synonyms = {"cities": {"КРАСНЫЙ КОЛОС": ["красный колос", "пос. красный колос"]}}
    assert ss.canonicalize("пос. красный колос", synonyms=synonyms) == "КРАСНЫЙ КОЛОС"
    assert ss.canonicalize("красный колос", cities=["Красный Колос"]) == "Красный Колос"
    assert ss.canonicalize("неизвестный") == "неизвестный"


def test_bbox():
    assert ss.in_rostov_bbox(47.2357, 39.7015)
    assert not ss.in_rostov_bbox(55.7558, 37.6173)  # Москва
    assert not ss.in_rostov_bbox(float("nan"), 40.0)


def test_yandex_finds_all_same_names_in_region(monkeypatch):
    monkeypatch.setattr(ss, "geocoder_key", lambda: "test-key")
    client = _Client(get_payload=YANDEX_PAYLOAD)
    found = asyncio.run(ss.find_yandex_settlements("Красный Колос", client=client))
    assert len(found) == 2  # region/non-locality filtered out
    assert all(f.source == "Yandex Geocoder" for f in found)
    assert {(f.lat, f.lng) for f in found} == {(47.9, 40.1), (48.1, 41.2)}


def test_osm_finds_all_same_names_in_bbox():
    client = _Client(get_payload=OSM_PAYLOAD)
    found = asyncio.run(ss.find_osm_settlements("Красный Колос", client=client))
    assert len(found) == 2
    assert all(f.source == "OSM Nominatim" for f in found)
    assert {f.kind for f in found} == {"village", "hamlet"}
    assert all(ss.in_rostov_bbox(f.lat, f.lng) for f in found)


def test_overpass_query_is_region_limited():
    q = ss.build_overpass_query("Красный Колос")
    assert "45.951688,38.22075,50.214477,44.319992" in q
    assert '"place"~"^(city|town|village|hamlet|isolated_dwelling|locality)$"' in q
    assert "Красный Колос" in q
    assert "out center tags" in q


def test_search_all_sources_merged_and_deduped(monkeypatch):
    monkeypatch.setattr(ss, "geocoder_key", lambda: "test-key")
    yandex_payload = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    _yandex_member(47.9, 40.1, "Красный Колос"),
                    _yandex_member(48.1, 41.2, "Красный Колос"),
                ]
            }
        }
    }
    osm_payload = [
        {"category": "place", "type": "village", "name": "Красный Колос",
         "lat": "47.91", "lon": "40.12"},
        {"category": "place", "type": "town", "name": "Красный Колос",
         "lat": "49.0", "lon": "42.0"},
    ]
    monkeypatch.setattr(ss, "find_pmtiles_settlements", lambda name, limit=20: [])
    found = asyncio.run(ss.search_settlements(
        "Красный Колос",
        yandex_client=_Client(get_payload=yandex_payload),
        osm_client=_Client(get_payload=osm_payload),
    ))
    assert len(found) == 4
    assert {f.source for f in found} == {"Yandex Geocoder", "OSM Nominatim"}
    assert len({f.key() for f in found}) == 4


def test_search_one_source_failure_does_not_break_other(monkeypatch):
    monkeypatch.setattr(ss, "geocoder_key", lambda: "test-key")
    monkeypatch.setattr(ss, "find_pmtiles_settlements", lambda name, limit=20: [])

    class _Broken(_Client):
        async def get(self, url, params=None):
            raise ss.httpx.HTTPError("network down")

    found = asyncio.run(ss.search_settlements(
        "Красный Колос",
        yandex_client=_Client(get_payload=YANDEX_PAYLOAD),
        osm_client=_Broken(get_payload=OSM_PAYLOAD),
    ))
    assert len(found) == 2
    assert all(f.source == "Yandex Geocoder" for f in found)


def test_pmtiles_no_archive_returns_empty(monkeypatch):
    fake = type("_FakePath", (), {"exists": lambda self: False})()
    monkeypatch.setattr(ss, "PMTILES_SCRIPT", fake)
    assert ss.find_pmtiles_settlements("Красный Колос") == []


def test_pmtiles_reads_two_same_names(monkeypatch):
    payload = [
        {"name": "Красный Колос", "kind": "village", "lat": 47.4007, "lng": 39.9472},
        {"name": "Красный Колос", "kind": "village", "lat": 49.0511, "lng": 41.1283},
        {"name": "Красный Колос", "kind": "village", "lat": 55.7, "lng": 37.6},  # вне области
    ]

    class _Completed:
        stdout = __import__("json").dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(
        __import__("pathlib").Path, "exists", lambda self: True
    )
    monkeypatch.setattr(ss.subprocess, "run", lambda *a, **kw: _Completed())
    found = ss.find_pmtiles_settlements("Красный Колос")
    assert len(found) == 2
    assert {f.source for f in found} == {"PMTiles places"}


def test_search_includes_pmtiles_source(monkeypatch):
    monkeypatch.setattr(ss, "geocoder_key", lambda: "")

    def fake_pmtiles(name, limit=20):
        return [
            ss.Settlement("Красный Колос", 47.4007, 39.9472,
                          source="PMTiles places"),
        ]

    monkeypatch.setattr(ss, "find_pmtiles_settlements", fake_pmtiles)
    found = asyncio.run(ss.search_settlements(
        "Красный Колос", osm_client=_Client(get_payload=[])
    ))
    assert found
    assert found[0].source == "PMTiles places"


def test_no_database_write_in_module():
    source = open(ss.__file__, encoding="utf-8").read()
    upper = source.upper()
    for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE"):
        assert token not in upper
