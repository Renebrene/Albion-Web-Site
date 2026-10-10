from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class EntityExtraction:
    values: dict[str, Any]
    warning: str | None = None


def enabled() -> bool:
    return os.getenv("ALBION_CHAT_LLM_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _json_request(url: str, payload: dict[str, Any], headers=None) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    timeout = float(os.getenv("ALBION_CHAT_LLM_TIMEOUT", "10"))
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        content = value.get("message", {}).get("content")
        if content is None:
            choices = value.get("choices") or []
            content = (choices[0].get("message", {}).get("content")
                       if choices else None)
        if isinstance(content, dict):
            return content
        value = content

    if not isinstance(value, str):
        raise ValueError("LLM вернула ответ не в виде JSON")

    value = value.strip()
    if value.startswith("```"):
        value = value.strip("`").removeprefix("json").strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON должен быть объектом")
    return parsed


def extract(text: str) -> EntityExtraction:
    """Extract only query entities; never execute SQL or choose result IDs."""
    if not enabled():
        return EntityExtraction({}, "LLM отключена")

    provider = os.getenv("ALBION_CHAT_LLM_PROVIDER", "ollama").strip().lower()
    schema_hint = (
        '{"city":null,"district":null,"address":null,"media_type":null,'
        '"size":null,"months":[],"year":null,"availability":null,'
        '"min_price":null,"max_price":null,"min_load":null,'
        '"max_load":null,"sort_by":null,"limit":null}'
    )
    prompt = (
        "Извлеки только поисковые сущности из запроса пользователя. "
        "Не придумывай значения, SQL, URL или идентификаторы. "
        f"Верни JSON строго такой формы: {schema_hint}\nЗапрос: {text}"
    )

    try:
        if provider == "ollama":
            base = os.getenv(
                "ALBION_CHAT_LLM_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/")
            raw = _json_request(
                f"{base}/api/chat",
                {
                    "model": os.getenv("ALBION_CHAT_LLM_MODEL", "qwen3:1.7b"),
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0},
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                },
            )
        elif provider in {"openai", "openai_compatible"}:
            base = os.getenv("ALBION_CHAT_LLM_BASE_URL", "").rstrip("/")
            if not base:
                raise ValueError("ALBION_CHAT_LLM_BASE_URL не задан")
            raw = _json_request(
                f"{base}/chat/completions",
                {
                    "model": os.getenv("ALBION_CHAT_LLM_MODEL", ""),
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": text},
                    ],
                },
                headers={
                    "Authorization": (
                        f"Bearer {os.getenv('ALBION_CHAT_LLM_API_KEY', '')}"
                    )
                },
            )
        else:
            raise ValueError(f"Неизвестный LLM provider: {provider}")

        values = _extract_json(raw)
        allowed = {
            "city", "district", "address", "media_type", "size", "months",
            "year", "availability", "min_price", "max_price", "min_load",
            "max_load", "sort_by", "limit",
        }
        return EntityExtraction(
            {key: value for key, value in values.items() if key in allowed}
        )
    except (OSError, HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
        return EntityExtraction({}, f"LLM недоступна: {exc}")
