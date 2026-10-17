from __future__ import annotations

import pytest

from backend.search import repository


class _FakeEngine:
    pass


def test_search_pool_defaults_are_bounded(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return _FakeEngine()

    monkeypatch.delenv("ALBION_DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("ALBION_DB_MAX_OVERFLOW", raising=False)
    monkeypatch.setattr(repository, "create_engine", fake_create_engine)

    engine = repository.SitePostgreSQLSearchRepository._create_engine()

    assert isinstance(engine, _FakeEngine)
    assert captured["kwargs"]["pool_size"] == 1
    assert captured["kwargs"]["max_overflow"] == 0


def test_search_pool_environment_overrides_are_honored(monkeypatch):
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return _FakeEngine()

    monkeypatch.setenv("ALBION_DB_POOL_SIZE", "3")
    monkeypatch.setenv("ALBION_DB_MAX_OVERFLOW", "2")
    monkeypatch.setattr(repository, "create_engine", fake_create_engine)

    repository.SitePostgreSQLSearchRepository._create_engine()

    assert captured["pool_size"] == 3
    assert captured["max_overflow"] == 2


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("ALBION_DB_POOL_SIZE", "0"),
        ("ALBION_DB_POOL_SIZE", "bad"),
        ("ALBION_DB_MAX_OVERFLOW", "-1"),
        ("ALBION_DB_MAX_OVERFLOW", "bad"),
    ],
)
def test_search_pool_rejects_invalid_environment(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        repository.SitePostgreSQLSearchRepository._create_engine()
