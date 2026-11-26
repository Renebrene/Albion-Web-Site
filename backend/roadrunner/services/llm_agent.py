"""
AI-агент для генерации сценариев программной дороги.

Поддерживает:
- YandexGPT Lite 8B (облако)
- Ollama (локальная модель)
- OpenAI-совместимые API

Генерирует JSON-сценарии по описанию на естественном языке.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

from backend.services.data_service import get_connection

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — генератор сценариев для 3D-анимации программной дороги «АЛЬБИОН».

Твоя задача — генерировать JSON-сценарии на основе описания пользователя.

Формат сценария (строго):
{
  "id": "rain-rush-hour",
  "name": "Дождь и час пик",
  "description": "Краткое описание",
  "duration": 60,
  "version": "1.0",
  "created_at": "2026-01-01T18:00:00",
  "author": "ai",
  "tags": ["rain"],
  "events": [
    {"t": 0, "do": "start_rain", "params": {"intensity": 0.6}},
    {"t": 0, "do": "change_time_of_day", "params": {"phase": "evening"}},
    {"t": 5, "do": "change_traffic_density", "params": {"density": 1.8}},
    {"t": 30, "do": "stop_rain", "params": {}},
    {"t": 60, "do": "end", "params": {}}
  ]
}

Доступные события (do):
- start_traffic, stop_traffic
- change_traffic_density (density: 0.1-3.0)
- change_speed (factor: 0.1-3.0)
- add_car, remove_car (color, type)
- add_bus, remove_bus (route, number)
- add_pedestrian, remove_pedestrian (direction: left/right/cross)
- change_traffic_light_phase (phase: green/yellow/red, intersection: 0-1)
- change_weather (condition: clear/cloudy/rain/snow/fog)
- start_rain, stop_rain (intensity: 0-1)
- start_snow, stop_snow (intensity: 0-1)
- change_time_of_day (phase: morning/day/evening/night)
- add_holiday_decor, remove_holiday_decor (type: trees/snowman/snow/flowers/flags/balloons/confetti/stars)
- end

Правила:
1. Сценарий должен быть логичным и последовательным.
2. Длительность — 30-300 секунд.
3. События должны быть упорядочены по времени.
4. Используй осмысленные id для машин/автобусов/пешеходов.
5. В каждом событии обязательно есть только поля "t" (число, секунды от
   начала) и "do" (действие из списка), плюс необязательный объект "params".
   Никогда не используй поля "time", "timestamp", "action", "type" или
   "description" вместо "t" и "do".
6. Значение "do" — только одно из перечисленных выше действий, без
   выдуманных названий.
7. Возвращай ТОЛЬКО JSON, без markdown-обёртки и пояснений.
"""


class LLMAgentError(Exception):
    """Ошибка AI-агента."""


class LLMAgent:
    """Генератор сценариев через LLM."""

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "qwen2.5:7b",
        url: str = "http://localhost:11434",
        api_key: str = "",
        temperature: float = 0.35,
    ):
        self.provider = provider
        self.model = model
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature

    async def generate(
        self, request: str, max_tokens: int = 2048
    ) -> dict[str, Any]:
        """
        Сгенерировать сценарий по описанию.

        Args:
            request: Описание сценария на естественном языке.
            max_tokens: Максимальное количество токенов.

        Returns:
            Словарь с сценарием.

        Raises:
            LLMAgentError: Если генерация не удалась.
        """
        if self.provider == "ollama":
            return await self._call_ollama(request, max_tokens)
        elif self.provider == "yandexgpt":
            return await self._call_yandex(request, max_tokens)
        elif self.provider == "openai":
            return await self._call_openai(request, max_tokens)
        else:
            raise LLMAgentError(f"Неизвестный провайдер: {self.provider}")

    async def _call_ollama(self, request: str, max_tokens: int) -> dict:
        """Ollama локальная модель."""
        model_name = str(self.model or "").lower()
        payload = {
            "model": self.model,
            "stream": False,
            # JSON-режим Ollama: ответ всегда валидный JSON без markdown.
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens,
            },
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request},
            ],
        }

        # qwen3/deepseek-r1 тратят весь лимит токенов на размышления, и в
        # content не остаётся JSON. Для генератора рассуждения не нужны.
        if "qwen3" in model_name or "r1" in model_name:
            payload["think"] = False

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.url}/api/chat", json=payload
            )
            response.raise_for_status()
            data = response.json()

        if data.get("done_reason") == "length":
            raise LLMAgentError(
                "Нейросеть вернула неполный ответ (лимит токенов)"
            )

        content = str(data.get("message", {}).get("content", ""))
        if not content.strip():
            raise LLMAgentError("Нейросеть вернула пустой ответ")

        return self._parse_response(content)

    async def _call_yandex(self, request: str, max_tokens: int) -> dict:
        """YandexGPT Lite 8B."""
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "modelUri": f"gs://{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": self.temperature,
                "maxTokens": str(max_tokens),
            },
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request},
            ],
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                self.url, json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("result", {}).get("data", [{}])[0].get(
            "text", ""
        )
        return self._parse_response(content)

    async def _call_openai(self, request: str, max_tokens: int) -> dict:
        """OpenAI-совместимый API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_response(content)

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Извлечь JSON из ответа."""
        content = (content or "").strip()
        if not content:
            raise LLMAgentError("Нейросеть вернула пустой ответ")

        # Убираем markdown-обёртку если есть
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.startswith("```")]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMAgentError(f"Не удалось распарсить JSON: {exc}") from exc


def _config_max_tokens(stored: dict | None = None) -> int:
    """Лимит токенов из админки (по умолчанию 2048)."""
    value = (stored or {}).get("max_tokens", 2048)
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return 2048
    return max(256, min(limit, 100000))


def get_llm_config() -> dict:
    """Загрузить конфигурацию LLM из БД или env."""
    # Сначала пробуем БД
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT settings FROM roadrunner_settings WHERE key = 'roadrunner'"
            ).fetchone()

        if row:
            from backend.roadrunner.services.db_json import as_dict

            stored = as_dict(row[0])
            # Настройки из админки лежат в общем блоке 'roadrunner' с
            # ключами llm_provider/llm_model/llm_url/llm_api_key.
            return {
                "provider": stored.get("llm_provider", "ollama"),
                "model": stored.get("llm_model", "qwen2.5:7b"),
                "url": stored.get("llm_url", "http://localhost:11434"),
                "api_key": stored.get("llm_api_key", ""),
                "temperature": stored.get("temperature", 0.35),
                "max_tokens": _config_max_tokens(stored),
            }
    except Exception:
        pass

    # Фоллбэк на env
    provider = os.getenv("ROADRUNNER_LLM_PROVIDER", "ollama")
    model = os.getenv("ROADRUNNER_LLM_MODEL", "qwen2.5:7b")
    url = os.getenv("ROADRUNNER_LLM_URL", "http://localhost:11434")
    api_key = os.getenv("ROADRUNNER_LLM_API_KEY", "")

    return {
        "provider": provider,
        "model": model,
        "url": url,
        "api_key": api_key,
        "temperature": 0.35,
        "max_tokens": _config_max_tokens(),
    }


def create_llm_agent() -> LLMAgent:
    """Создать AI-агент из общей конфигурации LLM.

    Генератор сценариев и AI-редактор кода используют одну и ту же модель —
    ту, что выбрана в настройках АИ (``llm_provider`` / ``llm_model``).
    """
    config = get_llm_config()

    return LLMAgent(
        provider=config.get("provider", "ollama"),
        model=config.get("model", "qwen2.5:7b"),
        url=config.get("url", "http://localhost:11434"),
        api_key=config.get("api_key", ""),
        temperature=config.get("temperature", 0.35),
    )
