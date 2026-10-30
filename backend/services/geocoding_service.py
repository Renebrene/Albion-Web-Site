"""Yandex Geocoder/Geosuggest proxy for Albion.

Keys are server-only. The browser never receives them; all provider calls go
through this module and are constrained to Rostov Oblast.
"""

from __future__ import annotations

import math
import os
import time
from typing import Any

import httpx


YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/v1/"
YANDEX_SUGGEST_URL = "https://suggest-maps.yandex.ru/v1/suggest"

# Bounding box of Rostov Oblast (same values as albion-locator-autonom).
ROSTOV_WEST = 38.22075
ROSTOV_SOUTH = 45.951688
ROSTOV_EAST = 44.319992
ROSTOV_NORTH = 50.214477

# Центр Ростова-на-Дону и охват для ранжирования подсказок. Bbox области
# как жёсткий фильтр не подходит: на запрос «Курчатова» Яндекс возвращал
# Волгодонск, а не ростовскую улицу. ll/spn задают приоритет, не отсекая
# другие города, если пользователь явно указал их в запросе.
ROSTOV_CENTER_LON = 39.7015
ROSTOV_CENTER_LAT = 47.2357
ROSTOV_BIAS_LL = f"{ROSTOV_CENTER_LON},{ROSTOV_CENTER_LAT}"
ROSTOV_BIAS_SPN = "0.5,0.5"


def _suggestion_in_rostov_oblast(*parts: str) -> bool:
    """Подсказка относится к Ростовской области (или самому Ростову)."""
    text = " ".join(str(part or "") for part in parts)
    text = text.casefold().replace("ё", "е")

    return (
        "ростовская область" in text
        or "ростов-на-дону" in text
        or "ростов на дону" in text
    )

TIMEOUT_SECONDS = 5.0
CACHE_TTL_SECONDS = 300.0
_CACHE: dict[str, tuple[float, Any]] = {}


class GeocodingError(Exception):
    status_code = 502


class GeocodingUnavailable(GeocodingError):
    status_code = 503


class GeocodingNotFound(GeocodingError):
    status_code = 404


class GeocodingRateLimited(GeocodingError):
    status_code = 429


class GeocodingTimeout(GeocodingError):
    status_code = 504


def geocoder_key() -> str:
    return (
        os.getenv("ALBION_YANDEX_GEOCODER_KEY", "").strip()
        or os.getenv("YANDEX_API_KEY", "").strip()
    )


def suggest_key() -> str:
    return (
        os.getenv("ALBION_YANDEX_SUGGEST_KEY", "").strip()
        or os.getenv("YANDEX_SUGGEST_API_KEY", "").strip()
    )


def _cache_get(key: str) -> Any | None:
    item = _CACHE.get(key)
    if item is None:
        return None
    expires, value = item
    if expires <= time.monotonic():
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    if len(_CACHE) > 500:
        now = time.monotonic()
        for old_key, (expires, _) in list(_CACHE.items()):
            if expires <= now:
                _CACHE.pop(old_key, None)
        if len(_CACHE) > 500:
            _CACHE.clear()
    _CACHE[key] = (time.monotonic() + CACHE_TTL_SECONDS, value)


def _provider_error(response: httpx.Response) -> None:
    if response.status_code == 429:
        raise GeocodingRateLimited(
            "Превышен лимит геокодирования Яндекса; повторите позже"
        )
    if response.status_code in {401, 403}:
        raise GeocodingUnavailable(
            "Ключ Яндекс Геокодера не имеет доступа к API"
        )
    if response.status_code >= 400:
        raise GeocodingError(
            f"Геокодер Яндекса вернул HTTP {response.status_code}"
        )


def _component_by_kinds(metadata: dict, kinds: set[str]) -> str:
    for component in ((metadata.get("Address") or {}).get("Components") or []):
        if isinstance(component, dict) and component.get("kind") in kinds:
            name = str(component.get("name") or "").strip()
            if name:
                return name
    return ""


def _in_rostov_oblast(metadata: dict) -> bool:
    return any(
        isinstance(component, dict)
        and component.get("kind") in {"province", "area"}
        and str(component.get("name", "")).strip().casefold().replace("ё", "е")
        == "ростовская область"
        for component in ((metadata.get("Address") or {}).get("Components") or [])
    )


def _as_float(value: str) -> float:
    return float(value)


async def suggest_address(query: str, limit: int = 8) -> list[dict[str, str]]:
    """Yandex Geosuggest, normalized for the Albion address dropdown."""
    key = suggest_key()
    if not key:
        raise GeocodingUnavailable(
            "Не настроен ALBION_YANDEX_SUGGEST_KEY для подсказок адреса"
        )

    query = " ".join(str(query or "").split())[:120]
    if len(query) < 3:
        return []

    # Ранжируем подсказки вокруг Ростова-на-Дону. Регион в тексте запроса
    # не дописываем: «Курчатова, Ростовская область» Geosuggest понимает
    # как поиск по области и первым отдаёт Волгодонск.
    cache_key = f"suggest:{limit}:{query.casefold()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "text": query,
        "apikey": key,
        "lang": "ru_RU",
        "results": max(1, min(10, int(limit))),
        "ll": ROSTOV_BIAS_LL,
        "spn": ROSTOV_BIAS_SPN,
        "attrs": "uri",
        "print_address": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(YANDEX_SUGGEST_URL, params=params)
    except httpx.TimeoutException as exc:
        raise GeocodingTimeout(
            "Сервис подсказок Яндекса не ответил вовремя"
        ) from exc
    except httpx.HTTPError as exc:
        raise GeocodingError(
            "Не удалось связаться с сервисом подсказок Яндекса"
        ) from exc

    _provider_error(response)

    try:
        payload = response.json()
    except ValueError as exc:
        raise GeocodingError(
            "Сервис подсказок Яндекса вернул некорректный ответ"
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise GeocodingError(
            "Сервис подсказок Яндекса вернул некорректный ответ"
        )

    suggestions: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        subtitle = item.get("subtitle")
        display = item.get("displayText")
        if isinstance(title, dict):
            title = title.get("text")
        if isinstance(subtitle, dict):
            subtitle = subtitle.get("text")
        title = str(title or "").strip()
        subtitle = str(subtitle or "").strip()
        display = str(display or "").strip() or ", ".join(
            part for part in (title, subtitle) if part
        )
        if not display or display.casefold() in seen:
            continue
        uri = str(item.get("uri") or "")
        # Для поиска адреса организации не подходят: их display_name
        # содержит название и рубрику, а не адрес.
        if uri.startswith("ymapsbm1://org"):
            continue
        # Подсказки только по Ростовской области: Москва, Краснодар и
        # соседние регионы в списке не нужны.
        if not _suggestion_in_rostov_oblast(title, subtitle, display):
            continue
        seen.add(display.casefold())
        suggestions.append(
            {
                "id": str(uri or display)[:240],
                "title": title or display,
                "subtitle": subtitle,
                "display_name": display[:320],
                "query": display[:320],
            }
        )
        if len(suggestions) >= limit:
            break

    _cache_set(cache_key, suggestions)
    return suggestions


async def geocode_address(query: str) -> dict[str, Any]:
    """Address -> coordinates, constrained to Rostov Oblast."""
    key = geocoder_key()
    if not key:
        raise GeocodingUnavailable(
            "Не настроен ALBION_YANDEX_GEOCODER_KEY для поиска по адресу"
        )

    query = " ".join(str(query or "").split())[:320]
    if len(query) < 3:
        raise GeocodingNotFound("Адрес слишком короткий")

    # По умолчанию уточняем городом: запрос «Курчатова» без него Яндекс
    # находил в Волгодонске. Если пользователь указал другой город
    # («Ленина, Таганрог»), он имеет приоритет над добавленным Ростовом.
    normalized = query.casefold().replace("ё", "е")
    geocode_query = query
    if (
        "ростов-на-дону" not in normalized
        and "ростов на дону" not in normalized
    ):
        geocode_query += ", Ростов-на-Дону"
    if "россия" not in normalized:
        geocode_query += ", Россия"

    cache_key = f"geocode:{geocode_query.casefold()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "apikey": key,
        "geocode": geocode_query,
        "format": "json",
        "lang": "ru_RU",
        "results": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(YANDEX_GEOCODER_URL, params=params)
    except httpx.TimeoutException as exc:
        raise GeocodingTimeout(
            "Сервис геокодирования Яндекса не ответил вовремя"
        ) from exc
    except httpx.HTTPError as exc:
        raise GeocodingError(
            "Не удалось связаться с сервисом геокодирования Яндекса"
        ) from exc

    _provider_error(response)

    try:
        data = response.json()
        members = data["response"]["GeoObjectCollection"]["featureMember"]
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(
            "Сервис геокодирования Яндекса вернул некорректный ответ"
        ) from exc

    if not members:
        raise GeocodingNotFound("Адрес не найден в Ростовской области")

    try:
        geo_object = members[0]["GeoObject"]
        lon, lat = map(_as_float, geo_object["Point"]["pos"].split())
        metadata = geo_object["metaDataProperty"]["GeocoderMetaData"]
        address = str(metadata.get("text") or query)[:320]
        precision = str(metadata.get("precision") or "unknown")[:40]
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError(
            "Не удалось определить координаты выбранного адреса"
        ) from exc

    if not (
        math.isfinite(lat)
        and math.isfinite(lon)
        and ROSTOV_SOUTH <= lat <= ROSTOV_NORTH
        and ROSTOV_WEST <= lon <= ROSTOV_EAST
        and _in_rostov_oblast(metadata)
    ):
        raise GeocodingNotFound(
            "Адрес не найден в Ростовской области; уточните адрес и регион"
        )

    result = {
        "lat": lat,
        "lon": lon,
        "address": address,
        "city": _component_by_kinds(metadata, {"locality"}) or None,
        "district": _component_by_kinds(metadata, {"district", "area"}) or None,
        "precision": precision,
        "source": "Yandex Geocoder",
    }
    _cache_set(cache_key, result)
    return result


async def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Coordinates -> address/district. Returns null fields without a key."""
    key = geocoder_key()
    if not key:
        return {
            "address": None,
            "district": None,
            "source": None,
            "detail": "ALBION_YANDEX_GEOCODER_KEY не настроен",
        }

    cache_key = f"reverse:{round(lat, 5)}:{round(lon, 5)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params_base = {
        "apikey": key,
        "geocode": f"{lon},{lat}",
        "format": "json",
        "lang": "ru_RU",
        "results": 1,
        "sco": "longlat",
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            members: list[dict[str, Any]] = []
            for extra in ({"kind": "house"}, {}):
                response = await client.get(
                    YANDEX_GEOCODER_URL,
                    params={**params_base, **extra},
                )
                _provider_error(response)
                members = (
                    response.json()
                    .get("response", {})
                    .get("GeoObjectCollection", {})
                    .get("featureMember", [])
                )
                if members:
                    break
    except GeocodingError:
        raise
    except httpx.TimeoutException as exc:
        raise GeocodingTimeout(
            "Сервис обратного геокодирования не ответил вовремя"
        ) from exc
    except httpx.HTTPError as exc:
        raise GeocodingError(
            "Не удалось связаться с сервисом обратного геокодирования"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise GeocodingError(
            "Сервис обратного геокодирования вернул некорректный ответ"
        ) from exc

    if not members:
        return {
            "address": None,
            "district": None,
            "source": "Yandex Geocoder",
        }

    try:
        geo_object = members[0]["GeoObject"]
        metadata = geo_object["metaDataProperty"]["GeocoderMetaData"]
        address = str(metadata.get("text") or "").strip() or None
        district = _component_by_kinds(metadata, {"district", "area"}) or None
    except (KeyError, TypeError) as exc:
        raise GeocodingError(
            "Не удалось разобрать адрес выбранной точки"
        ) from exc

    result = {
        "address": address,
        "district": district,
        "source": "Yandex Geocoder",
    }
    _cache_set(cache_key, result)
    return result
