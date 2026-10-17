"""Model/provider selection for the smart chat.

Profiles are configured by the operator in the environment (secrets never go
to the database). The admin UI only selects a profile/model; the selection is
stored in ``site_settings['chat_llm']``.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

from backend.services.data_service import (
    _read_cache_stamp,
    get_connection,
)


SETTINGS_KEY = "chat_llm"

_CACHE: dict[str, Any] = {
    "stamp": None,
    "ts": 0.0,
    "selection": None,
}

_CACHE_TTL = float(os.getenv("ALBION_LLM_SETTINGS_TTL", "30"))


def _default_local_profile() -> dict[str, Any]:
    return {
        "label": "Локальная модель (Ollama)",
        "provider": os.getenv("ALBION_CHAT_LLM_PROVIDER", "ollama").strip()
        or "ollama",
        "base_url": (
            os.getenv("ALBION_CHAT_LLM_BASE_URL", "http://127.0.0.1:11434")
            .strip()
            .rstrip("/")
        ),
        "model": os.getenv("ALBION_CHAT_LLM_MODEL", "qwen3:14b").strip()
        or "qwen3:14b",
        "allow_model_override": True,
    }


def get_profiles() -> dict[str, dict[str, Any]]:
    """Named profiles from ``ALBION_LLM_PROFILES`` plus the local default."""
    raw = os.getenv("ALBION_LLM_PROFILES", "").strip()
    profiles: dict[str, dict[str, Any]] = {}

    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    if isinstance(value, dict):
                        profiles[str(key)] = value
        except (ValueError, TypeError):
            profiles = {}

    profiles.setdefault("local", _default_local_profile())
    return profiles


def safe_profiles() -> list[dict[str, Any]]:
    """Profiles without secrets, for the admin UI."""
    result = []

    for key, profile in get_profiles().items():
        api_key_env = str(profile.get("api_key_env") or "").strip()
        result.append(
            {
                "id": key,
                "label": str(profile.get("label") or key),
                "provider": str(profile.get("provider") or "ollama"),
                "base_url": str(profile.get("base_url") or ""),
                "model": str(profile.get("model") or ""),
                "allow_model_override": bool(
                    profile.get("allow_model_override")
                ),
                "has_api_key": bool(
                    profile.get("api_key")
                    or (api_key_env and os.getenv(api_key_env))
                ),
            }
        )

    return result


def _read_selection() -> dict[str, Any] | None:
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM site_settings WHERE key = %s",
                (SETTINGS_KEY,),
            ).fetchone()
    except Exception:  # noqa: BLE001 — чат должен работать без БД настроек
        return None

    if not row or not row[0]:
        return None

    try:
        parsed = json.loads(row[0])
    except (ValueError, TypeError):
        return None

    return parsed if isinstance(parsed, dict) else None


def get_selection() -> dict[str, Any] | None:
    """Cached ``{"extract": {...}, "answer": {...}}`` selection."""
    stamp = _read_cache_stamp()
    now = time.monotonic()

    if (
        _CACHE["selection"] is not None
        and _CACHE["stamp"] == stamp
        and (now - _CACHE["ts"]) < _CACHE_TTL
    ):
        return _CACHE["selection"]

    # Cache the "no selection" state too; otherwise every chat turn would
    # query site_settings twice (extract + answer).
    selection = _read_selection() or {}
    _CACHE["stamp"] = stamp
    _CACHE["ts"] = now
    _CACHE["selection"] = selection
    return selection


def invalidate() -> None:
    _CACHE["selection"] = None
    _CACHE["stamp"] = None
    _CACHE["ts"] = 0.0


def resolve_stage(stage: str) -> dict[str, Any] | None:
    """Resolve the selected profile for extraction or answers.

    Returns ``None`` when no selection is stored; the caller then falls back
    to the legacy env configuration.
    """
    selection = get_selection()
    if not selection:
        return None

    stage_data = selection.get(stage)
    if not isinstance(stage_data, dict):
        return None

    profile_id = str(stage_data.get("profile") or "").strip()
    profile = get_profiles().get(profile_id)
    if not profile:
        return None

    model = str(stage_data.get("model") or profile.get("model") or "").strip()
    api_key_env = str(profile.get("api_key_env") or "").strip()
    api_key = str(profile.get("api_key") or "").strip()
    if not api_key and api_key_env:
        api_key = os.getenv(api_key_env, "").strip()

    return {
        "profile": profile_id,
        "provider": str(profile.get("provider") or "ollama").lower(),
        "base_url": str(profile.get("base_url") or "").rstrip("/"),
        "model": model,
        "api_key": api_key,
        "allow_model_override": bool(profile.get("allow_model_override")),
    }


def _validate_stage(stage: str, data: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(data.get("profile") or "").strip()
    profile = get_profiles().get(profile_id)

    if not profile:
        raise ValueError(f"Профиль «{profile_id}» не найден")

    model = str(data.get("model") or "").strip()

    if model:
        if not profile.get("allow_model_override"):
            configured = str(profile.get("model") or "").strip()
            if model != configured:
                raise ValueError(
                    f"Для профиля «{profile_id}» модель задаётся настройками "
                    "сервера"
                )
        if len(model) > 100:
            raise ValueError("Слишком длинное имя модели")
    else:
        model = str(profile.get("model") or "").strip()

    if not model:
        raise ValueError("Не выбрана модель")

    return {
        "profile": profile_id,
        "model": model if profile.get("allow_model_override") else None,
    }


def save_selection(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Ожидается объект настроек")

    selection = {
        "extract": _validate_stage(
            "extract", payload.get("extract") or {}
        ),
        "answer": _validate_stage(
            "answer", payload.get("answer") or {}
        ),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO site_settings (key, value, value_type, description)
            VALUES (%s, %s, 'json', 'Умный чат: выбранные модели')
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (SETTINGS_KEY, json.dumps(selection, ensure_ascii=False)),
        )

    invalidate()
    return selection


def list_local_models() -> list[str]:
    """Installed Ollama models (best effort, short timeout)."""
    profiles = get_profiles()
    local = profiles.get("local") or _default_local_profile()
    base_url = str(local.get("base_url") or "http://127.0.0.1:11434").rstrip("/")

    try:
        request = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — список моделей не критичен
        return []

    names = []

    for item in data.get("models") or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))

    return sorted(set(names))


def describe() -> dict[str, Any]:
    selection = get_selection()

    return {
        "profiles": safe_profiles(),
        "selection": selection,
        "local_models": list_local_models(),
    }
