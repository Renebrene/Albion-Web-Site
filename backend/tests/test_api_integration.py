"""Интеграционные тесты публичного API (через FastAPI TestClient)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_api import require_admin
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


@requires_db
def test_home_slides_do_not_leak_banner_code():
    slides = client.get("/api/home").json()["slides"]

    for slide in slides:
        assert "code" not in slide
        assert isinstance(slide.get("has_code"), bool)


@requires_db
def test_home_banner_code_endpoint_serves_sandboxed_html():
    slides = client.get("/api/home").json()["slides"]
    slide = next((s for s in slides if s.get("has_code")), None)

    if slide is None:
        pytest.skip("нет слайда с кодом баннера")

    response = client.get(f"/api/home/slides/{slide['id']}/code")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "sandbox allow-scripts" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_home_banner_code_unknown_slide_is_404():
    assert client.get("/api/home/slides/999999/code").status_code == 404


@requires_db
def test_admin_banner_default_returns_standalone_html():
    app.dependency_overrides[require_admin] = lambda: {"id": 1}

    try:
        response = client.get("/api/admin/home/banner-default")
    finally:
        app.dependency_overrides.pop(require_admin, None)

    assert response.status_code == 200
    assert response.json()["code"].lstrip().startswith("<!DOCTYPE html>")


def test_unknown_api_path_returns_404():
    assert client.get("/api/definitely-not-here").status_code == 404
