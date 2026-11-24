"""
Сервис погоды для Roadrunner.

Поддерживает Open-Meteo (без ключа) и Яндекс Погоду (с ключом).
Кэширует данные на 10 минут.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from backend.services.data_service import PROJECT_DIR

logger = logging.getLogger(__name__)

CITY_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "city.json"
WEATHER_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "weather.json"

CACHE_TTL = 600  # 10 минут


def _hour_seed(now) -> int:
    """Детерминированное зерно на текущий час.

    Встроенный hash() зависит от PYTHONHASHSEED и различается между
    воркерами uvicorn, поэтому модель погоды/пробок «дрожала» бы.
    """
    return now.year * 1_000_000 + now.month * 10_000 + now.day * 100 + now.hour


def _noise(seed: int, modulo: int) -> int:
    """Псевдослучайное, но воспроизводимое число 0..modulo-1."""
    return (seed * 2_654_435_761) % modulo


@dataclass
class WeatherData:
    """Текущие погодные данные."""

    condition: str  # clear, cloudy, rain, snow, fog
    temperature_c: float
    humidity: int
    wind_speed_kmh: float
    precipitation_mm: float
    source: str  # open-meteo, yandex, model
    cached_at: float


@dataclass
class TrafficData:
    """Данные о пробках."""

    score: int  # 0-10
    label: str  # свободные, умеренные, пробки
    source: str
    cached_at: float


class WeatherService:
    """Получает погоду из разных источников."""

    def __init__(self):
        self._cache: dict[str, WeatherData] = {}
        self._city_config = self._load_city_config()

    def _load_city_config(self) -> dict:
        if not CITY_CONFIG_PATH.exists():
            return {"coordinates": {"lat": 47.2357, "lon": 39.7230}}

        with CITY_CONFIG_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    async def get_current(self) -> WeatherData:
        """Получить текущую погоду."""
        cache_key = "current"

        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached.cached_at < CACHE_TTL:
                return cached

        # Пробуем Open-Meteo (без ключа)
        try:
            data = await self._fetch_open_meteo()
            self._cache[cache_key] = data
            return data
        except Exception as exc:
            logger.warning("Open-Meteo не доступен: %s", exc)

        # Пробуем Яндекс (с ключом)
        yandex_key = os.getenv("YANDEX_WEATHER_KEY")
        if yandex_key:
            try:
                data = await self._fetch_yandex(yandex_key)
                self._cache[cache_key] = data
                return data
            except Exception as exc:
                logger.warning("Яндекс Погода не доступен: %s", exc)

        # Модель по координатам
        return self._model_weather()

    async def _fetch_open_meteo(self) -> WeatherData:
        """Open-Meteo API (без ключа)."""
        coords = self._city_config["coordinates"]
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={coords['lat']}&longitude={coords['lon']}"
            "&current=temperature_2m,relative_humidity_2m,weather_code,"
            "wind_speed_10m,precipitation"
            "&timezone=Europe%2FMoscow"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        current = data["current"]
        return WeatherData(
            condition=self._weather_code_to_condition(
                current["weather_code"]
            ),
            temperature_c=current["temperature_2m"],
            humidity=current["relative_humidity_2m"],
            wind_speed_kmh=current["wind_speed_10m"],
            precipitation_mm=current.get("precipitation", 0),
            source="open-meteo",
            cached_at=time.time(),
        )

    async def _fetch_yandex(self, key: str) -> WeatherData:
        """Яндекс Погода API."""
        coords = self._city_config["coordinates"]
        url = (
            f"https://weather.yandex.ru/api/json/v1.3/weather?"
            f"lat={coords['lat']}&lon={coords['lon']}&key={key}"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        forecast = data.get("forecast", [{}])[0]
        return WeatherData(
            condition=forecast.get("condition", "clear"),
            temperature_c=forecast.get("temp", 0),
            humidity=forecast.get("humidity", 50),
            wind_speed_kmh=forecast.get("wind_speed", 0),
            precipitation_mm=forecast.get("precip", 0),
            source="yandex",
            cached_at=time.time(),
        )

    def _model_weather(self) -> WeatherData:
        """Модель погоды по времени суток и сезону."""
        import datetime

        now = datetime.datetime.now()
        hour = now.hour
        month = now.month
        seed = _hour_seed(now)

        # Базовая температура по сезону
        base_temp = {
            12: 5, 1: 3, 2: 5, 3: 10, 4: 15, 5: 20,
            6: 25, 7: 28, 8: 27, 9: 22, 10: 15, 11: 8,
        }.get(month, 15)

        # Коррекция по времени суток
        temp_offset = 0
        if 6 <= hour <= 9:
            temp_offset = -3
        elif 12 <= hour <= 15:
            temp_offset = 3
        elif 18 <= hour <= 21:
            temp_offset = -2

        temperature = base_temp + temp_offset + (_noise(seed, 5) - 2)

        # Случайная погода
        condition = "clear"
        if month in (11, 12, 1, 2):
            condition = "snow" if _noise(seed, 3) == 0 else "cloudy"
        elif month in (6, 7, 8):
            condition = "rain" if _noise(seed, 4) == 0 else "clear"
        else:
            condition = "cloudy" if _noise(seed, 2) == 0 else "clear"

        return WeatherData(
            condition=condition,
            temperature_c=temperature,
            humidity=50 + _noise(seed, 30),
            wind_speed_kmh=5 + _noise(seed, 20),
            precipitation_mm=0,
            source="model",
            cached_at=time.time(),
        )

    @staticmethod
    def _weather_code_to_condition(code: int) -> str:
        """Превращает код погоды Open-Meteo в условие."""
        if code == 0:
            return "clear"
        elif 1 <= code <= 3:
            return "cloudy"
        elif 45 <= code <= 48:
            return "fog"
        elif 51 <= code <= 67:
            return "rain"
        elif 71 <= code <= 77:
            return "snow"
        elif 80 <= code <= 82:
            return "rain"
        elif 95 <= code <= 99:
            return "snow"
        return "clear"


class TrafficService:
    """Получает данные о пробках."""

    def __init__(self):
        self._cache: Optional[TrafficData] = None
        self._last_fetch = 0

    async def get_current(self) -> TrafficData:
        """Получить текущие пробки."""
        if self._cache and (time.time() - self._last_fetch) < CACHE_TTL:
            return self._cache

        # Пробуем Яндекс
        yandex_url = os.getenv("YANDEX_TRAFFIC_URL")
        if yandex_url:
            try:
                data = await self._fetch_yandex(yandex_url)
                self._cache = data
                self._last_fetch = time.time()
                return data
            except Exception as exc:
                logger.warning("Яндекс Пробки не доступен: %s", exc)

        # Модель по времени
        return self._model_traffic()

    async def _fetch_yandex(self, url: str) -> TrafficData:
        """Яндекс Пробки API."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        score = data.get("score", 5)
        return TrafficData(
            score=score,
            label=self._score_to_label(score),
            source="yandex",
            cached_at=time.time(),
        )

    def _model_traffic(self) -> TrafficData:
        """Модель пробок по времени."""
        import datetime

        now = datetime.datetime.now()
        hour = now.hour
        seed = _hour_seed(now)

        # Базовый балл
        base_score = 3

        # Час пик
        if 7 <= hour <= 10:
            base_score = 7
        elif 17 <= hour <= 20:
            base_score = 8
        elif 10 <= hour <= 17:
            base_score = 4
        else:
            base_score = 2

        # Случайные колебания
        score = base_score + (_noise(seed, 3) - 1)
        score = max(0, min(10, score))

        return TrafficData(
            score=score,
            label=self._score_to_label(score),
            source="model",
            cached_at=time.time(),
        )

    @staticmethod
    def _score_to_label(score: int) -> str:
        """Шкала Яндекс.Пробок: 0-3 / 4-6 / 7-9 / 10."""
        if score <= 3:
            return "свободно"
        elif score <= 6:
            return "умеренно"
        elif score <= 9:
            return "пробки"
        else:
            return "затор"
