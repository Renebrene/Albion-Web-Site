"""Поиск населённых пунктов на лету (только для поиска конструкций).

НЕ сохраняет ничего в БД. Все источники ограничиваются Ростовской областью.
При нескольких одинаковых названиях возвращаются ВСЕ кандидаты.

Источники:
  1) Яндекс Геокодер (по области, results>1, kind=locality;
     НЕ добавляем «Ростов-на-Дону» как город — иначе теряются одноимённые посёлки);
  2) OSM Nominatim (bbox Ростовской области, category=place,
     type=city|town|village|hamlet|isolated_dwelling|locality;
     Overpass оставлен как резервный конструктор запроса);
  3) локальные имена из `cities` / синонимов — только канонизация имени
     (координат у них нет).

Модуль не импортируется ничем, пока не подключён к чату.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from backend.services.data_service import PROJECT_DIR
from backend.services.geocoding_service import (
    ROSTOV_EAST,
    ROSTOV_NORTH,
    ROSTOV_SOUTH,
    ROSTOV_WEST,
    GeocodingError,
    _component_by_kinds,
    _in_rostov_oblast,
    _provider_error,
    geocoder_key,
)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "AlbionConstructionSearch/1.0 (site search)"
TIMEOUT_SECONDS = 15.0
MAX_RESULTS_DEFAULT = 20
RADIUS_M_DEFAULT = 50_000  # 50 км, вариант B

PMTILES_ARCHIVE = PROJECT_DIR / "storage" / "map" / "rostov.pmtiles"
PMTILES_SCRIPT = Path(__file__).with_name("pmtiles_places.mjs")
PMTILES_ZOOM = 10  # на z10 видны сёла/хутора; на z8/z9 их нет


def _pmtiles_bbox_arg() -> str:
    return f"{ROSTOV_SOUTH},{ROSTOV_WEST},{ROSTOV_NORTH},{ROSTOV_EAST}"

SETTLEMENT_PLACES = (
    "city", "town", "village", "hamlet", "isolated_dwelling", "locality"
)
AREA_MARKERS = ("район", "округ", "р-н", "р-н.")
NAME_PREFIXES_RE = re.compile(
    r"\b(г|город|пос|посёлок|поселок|с|село|д|деревня|ст|станица|х|хутор|рп|нп)\.?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Settlement:
    name: str
    lat: float
    lng: float
    kind: str = "locality"
    source: str = ""
    address: str = ""

    def key(self) -> tuple[str, float, float]:
        return (normalize_name(self.name), round(self.lat, 4), round(self.lng, 4))


def normalize_name(value: str) -> str:
    s = str(value or "").strip().lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[«»\"']", "", s)
    # Имя населённого пункта — до первой запятой (дальше уточнение района/области).
    s = s.split(",")[0].strip()
    s = NAME_PREFIXES_RE.sub("", s)
    for marker in AREA_MARKERS:
        s = re.sub(rf"\b{re.escape(marker)}\b", "", s)
    return re.sub(r"\s+", " ", s).strip(" ,.;")


def in_rostov_bbox(lat: float, lng: float) -> bool:
    return (
        math.isfinite(lat)
        and math.isfinite(lng)
        and ROSTOV_SOUTH <= lat <= ROSTOV_NORTH
        and ROSTOV_WEST <= lng <= ROSTOV_EAST
    )


def canonicalize(name: str, synonyms: Optional[dict] = None,
                 cities: Optional[Iterable[str]] = None) -> str:
    """Привести имя к канонической форме по синонимам/списку городов."""
    key = normalize_name(name)
    if not key:
        return ""

    alias_map: dict[str, str] = {}
    if synonyms:
        for canonical, aliases in (synonyms.get("cities") or {}).items():
            alias_map[normalize_name(canonical)] = canonical
            for alias in aliases or []:
                alias_map[normalize_name(alias)] = canonical

    if key in alias_map:
        return alias_map[key]

    if cities:
        for city in cities:
            ck = normalize_name(city)
            if ck == key or (len(key) >= 4 and ck.startswith(key)) \
                    or (len(ck) >= 4 and key.startswith(ck)):
                return str(city)

    return name.strip()


def dedupe(items: Iterable[Settlement], limit: int = MAX_RESULTS_DEFAULT) -> list[Settlement]:
    seen: set[tuple[str, float, float]] = set()
    out: list[Settlement] = []
    for item in items:
        if item.key() in seen:
            continue
        seen.add(item.key())
        out.append(item)

    ranked = sorted(
        out,
        key=lambda s: (
            0 if s.kind in {"city", "town"} else 1,
            {
                "Yandex Geocoder": 0,
                "OSM Nominatim": 1,
                "OSM Overpass": 1,
                "PMTiles places": 2,
            }.get(s.source, 3),
            s.name.casefold(),
        ),
    )
    return ranked[:max(1, limit)]


# --- Яндекс ------------------------------------------------------------------

def _parse_yandex(payload: Any, query_name: str) -> list[Settlement]:
    try:
        members = payload["response"]["GeoObjectCollection"]["featureMember"]
    except (KeyError, TypeError, ValueError):
        return []

    out: list[Settlement] = []
    for member in members or []:
        try:
            obj = member["GeoObject"]
            lng, lat = map(float, obj["Point"]["pos"].split())
            metadata = obj["metaDataProperty"]["GeocoderMetaData"]
        except (KeyError, TypeError, ValueError):
            continue

        kind = str(metadata.get("kind") or "")
        locality = _component_by_kinds(metadata, {"locality"})
        # Только населённые пункты: улицы/здания/организации не подходят.
        if kind != "locality":
            continue
        if not _in_rostov_oblast(metadata) or not in_rostov_bbox(lat, lng):
            continue

        name = locality or str(metadata.get("text") or query_name)
        out.append(Settlement(
            name=name[:200],
            lat=lat,
            lng=lng,
            kind="locality",
            source="Yandex Geocoder",
            address=str(metadata.get("text") or "")[:320],
        ))
    return out


async def find_yandex_settlements(
    name: str,
    limit: int = MAX_RESULTS_DEFAULT,
    client: Optional[httpx.AsyncClient] = None,
) -> list[Settlement]:
    """Все совпадения в Ростовской области (не один результат!)."""
    key = geocoder_key()
    if not key:
        return []

    query = " ".join(str(name or "").split())[:200]
    if len(query) < 3:
        return []

    params = {
        "apikey": key,
        "geocode": f"{query}, Ростовская область, Россия",
        "format": "json",
        "lang": "ru_RU",
        "results": max(1, min(50, int(limit))),
    }

    owns = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    try:
        response = await http.get("https://geocode-maps.yandex.ru/v1/", params=params)
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Не удалось найти населённый пункт: {exc}") from exc
    finally:
        if owns:
            await http.aclose()

    _provider_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise GeocodingError("Некорректный ответ Яндекс Геокодера") from exc

    return dedupe(_parse_yandex(payload, query), limit)


# --- OSM Overpass ------------------------------------------------------------

def build_overpass_query(name: str) -> str:
    escaped = re.escape(str(name or "").strip()).replace("\\ ", " ")
    places = "|".join(SETTLEMENT_PLACES)
    bbox = f"{ROSTOV_SOUTH},{ROSTOV_WEST},{ROSTOV_NORTH},{ROSTOV_EAST}"
    return (
        "[out:json][timeout:25];\n"
        f'nwr["place"~"^({places})$"]["name"~"{escaped}",i]({bbox});\n'
        "out center tags;"
    )


def _parse_osm(payload: Any, limit: int) -> list[Settlement]:
    if not isinstance(payload, dict):
        return []
    out: list[Settlement] = []
    for el in payload.get("elements") or []:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") or {}
        kind = str(tags.get("place") or "").strip()
        name = str(tags.get("name:ru") or tags.get("name") or "").strip()
        if not name or kind not in SETTLEMENT_PLACES:
            continue
        lat = el.get("lat")
        lng = el.get("lon")
        if lat is None or lng is None:
            center = el.get("center") or {}
            lat, lng = center.get("lat"), center.get("lon")
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        if not in_rostov_bbox(lat, lng):
            continue
        out.append(Settlement(
            name=name[:200], lat=lat, lng=lng, kind=kind,
            source="OSM Overpass",
        ))
    return dedupe(out, limit)


def parse_nominatim(payload: Any, limit: int) -> list[Settlement]:
    if not isinstance(payload, list):
        return []

    out: list[Settlement] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("category") or "") != "place":
            continue
        kind = str(row.get("type") or "").strip()
        if kind not in SETTLEMENT_PLACES:
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        try:
            lat, lng = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not in_rostov_bbox(lat, lng):
            continue
        out.append(Settlement(
            name=name[:200],
            lat=lat,
            lng=lng,
            kind=kind,
            source="OSM Nominatim",
        ))
    return dedupe(out, limit)


async def find_osm_settlements(
    name: str,
    limit: int = MAX_RESULTS_DEFAULT,
    client: Optional[httpx.AsyncClient] = None,
    nominatim_url: str = NOMINATIM_URL,
) -> list[Settlement]:
    """Все совпадения по OSM в bbox Ростовской области (Nominatim).

    Overpass API часто отвечает 406/502 в этой среде, поэтому основной
    путь — Nominatim search с `bounded=1` и viewbox области.
    """
    query = " ".join(str(name or "").split())[:200]
    if len(query) < 3:
        return []

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": max(1, min(50, int(limit))),
        "accept-language": "ru",
        "addressdetails": 0,
        # Nominatim ждёт viewbox как west,south,east,north
        "viewbox": f"{ROSTOV_WEST},{ROSTOV_SOUTH},{ROSTOV_EAST},{ROSTOV_NORTH}",
        "bounded": 1,
    }

    owns = client is None
    http = client or httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": NOMINATIM_USER_AGENT},
    )
    try:
        response = await http.get(nominatim_url, params=params)
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Не удалось найти населённый пункт в OSM: {exc}") from exc
    finally:
        if owns:
            await http.aclose()

    _provider_error(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise GeocodingError("Некорректный ответ OSM Nominatim") from exc
    return parse_nominatim(payload, limit)


# --- офлайн: локальный PMTiles `places` -------------------------------------

def find_pmtiles_settlements(
    name: str,
    limit: int = MAX_RESULTS_DEFAULT,
    *,
    archive: Optional[Path] = None,
    zoom: int = PMTILES_ZOOM,
) -> list[Settlement]:
    """Прочитать населённые пункты из локального PMTiles (без записей в БД).

    Вызывает небольшой Node-скрипт с `pmtiles` + `@mapbox/vector-tile` из
    `frontend/node_modules`. При отсутствии архива/Node просто вернёт [].
    """
    archive = archive or PMTILES_ARCHIVE
    if not archive or not Path(archive).exists() or not PMTILES_SCRIPT.exists():
        return []

    query = " ".join(str(name or "").split())[:200]
    if len(query) < 3:
        return []

    node = os.getenv("ALBION_NODE_BIN", "node")
    command = [
        node,
        str(PMTILES_SCRIPT),
        "--archive", str(archive),
        "--name", query,
        "--zoom", str(zoom),
        "--limit", str(max(1, limit)),
        "--bbox", _pmtiles_bbox_arg(),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_DIR),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    try:
        payload = json.loads(completed.stdout or "[]")
    except (TypeError, ValueError):
        return []

    if isinstance(payload, dict):
        return []

    out: list[Settlement] = []
    for row in payload or []:
        if not isinstance(row, dict):
            continue
        try:
            lat, lng = float(row["lat"]), float(row["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        if not in_rostov_bbox(lat, lng):
            continue
        out.append(Settlement(
            name=str(row.get("name") or "")[:200],
            lat=lat,
            lng=lng,
            kind=str(row.get("kind") or "locality"),
            source="PMTiles places",
        ))
    return dedupe(out, limit)


# --- unified entry point ----------------------------------------------------

async def search_settlements(
    name: str,
    limit: int = MAX_RESULTS_DEFAULT,
    *,
    yandex_client: Optional[httpx.AsyncClient] = None,
    osm_client: Optional[httpx.AsyncClient] = None,
) -> list[Settlement]:
    """Все кандидаты из всех источников, объединённые и обездублированные.

    Ничего не пишет в БД. Ошибки одного источника не роняют другой.
    """
    out: list[Settlement] = []

    for finder, kw in (
        (find_yandex_settlements, {"client": yandex_client}),
        (find_osm_settlements, {"client": osm_client}),
    ):
        try:
            out.extend(await finder(name, limit=limit, **kw))
        except GeocodingError:
            pass

    # Офлайн-источник: локальный слой places; ошибки/отсутствие архива игнорируем.
    try:
        out.extend(find_pmtiles_settlements(name, limit=limit))
    except Exception:  # noqa: BLE001
        pass

    return dedupe(out, limit)
