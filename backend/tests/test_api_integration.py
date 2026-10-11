"""Интеграционные тесты публичного API (через FastAPI TestClient)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.conftest import requires_db

client = TestClient(app)

PUBLIC_JSON_ENDPOINTS = [
    "/api/health",
    "/api/settings",
    "/api/home",
    "/api/site-menu",
    "/api/constructions",
    "/api/contacts",
    "/api/about",
    "/api/news",
]


@requires_db
@pytest.mark.parametrize("path", PUBLIC_JSON_ENDPOINTS)
def test_public_endpoint_returns_json(path: str):
    response = client.get(path)

    assert response.status_code == 200, (path, response.status_code, response.text[:200])
    assert response.headers.get("content-type", "").startswith("application/json")


@requires_db
def test_constructions_endpoint_returns_list():
    response = client.get("/api/constructions")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_unknown_api_path_returns_404():
    assert client.get("/api/definitely-not-here").status_code == 404
