"""Admin model/provider selection for the smart chat."""

from __future__ import annotations

import json

import pytest

from backend.chat import llm
from backend.services import chat_llm_settings as settings


PROFILES = {
    "local": {
        "label": "Local",
        "provider": "ollama",
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen3:14b",
        "allow_model_override": True,
    },
    "cloud": {
        "label": "Cloud Qwen",
        "provider": "openai_compatible",
        "base_url": "https://example.test/v1",
        "model": "qwen/qwen-2.5-7b-instruct",
        "api_key_env": "TEST_CLOUD_KEY",
    },
}


def test_profiles_expose_no_secrets(monkeypatch):
    monkeypatch.setenv("ALBION_LLM_PROFILES", json.dumps(PROFILES))
    monkeypatch.setenv("TEST_CLOUD_KEY", "secret")

    profiles = settings.get_profiles()
    safe = settings.safe_profiles()
    cloud = next(item for item in safe if item["id"] == "cloud")

    assert "api_key" not in cloud
    assert cloud["has_api_key"] is True
    assert "local" in profiles


def test_local_model_override_and_cloud_restriction(monkeypatch):
    monkeypatch.setenv("ALBION_LLM_PROFILES", json.dumps(PROFILES))

    local = settings._validate_stage(
        "extract", {"profile": "local", "model": "qwen3:8b"}
    )
    assert local == {"profile": "local", "model": "qwen3:8b"}

    with pytest.raises(ValueError):
        settings._validate_stage(
            "answer", {"profile": "cloud", "model": "other-model"}
        )

    cloud = settings._validate_stage("answer", {"profile": "cloud"})
    assert cloud == {"profile": "cloud", "model": None}


def test_resolve_stage_reads_selection(monkeypatch):
    monkeypatch.setenv("ALBION_LLM_PROFILES", json.dumps(PROFILES))
    monkeypatch.setenv("TEST_CLOUD_KEY", "secret")
    monkeypatch.setattr(
        settings,
        "get_selection",
        lambda: {
            "extract": {"profile": "local", "model": "qwen3:8b"},
            "answer": {"profile": "cloud", "model": None},
        },
    )

    extract = settings.resolve_stage("extract")
    answer = settings.resolve_stage("answer")

    assert extract["model"] == "qwen3:8b"
    assert extract["provider"] == "ollama"
    assert answer["model"] == "qwen/qwen-2.5-7b-instruct"
    assert answer["api_key"] == "secret"


def test_llm_stage_config_uses_admin_selection(monkeypatch):
    monkeypatch.setattr(
        "backend.services.chat_llm_settings.resolve_stage",
        lambda stage: {
            "profile": "cloud",
            "provider": "openai_compatible",
            "base_url": "https://example.test/v1",
            "model": "qwen/qwen-2.5-7b-instruct",
            "api_key": "secret",
        }
        if stage == "answer"
        else None,
    )

    config = llm._stage_config("answer")

    assert config.provider == "openai_compatible"
    assert config.base_url == "https://example.test/v1"
    assert config.model == "qwen/qwen-2.5-7b-instruct"
    assert config.api_key == "secret"
