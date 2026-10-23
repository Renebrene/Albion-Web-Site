"""Cookie-сессии админки (TZ 2.1).

Проверяем режим ALBION_AUTH_MODE=cookie: доступ по cookie, обязательный
CSRF-заголовок для изменяющих методов, отзыв сессии и запасной путь через
Bearer-заголовок.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_api import (
    ADMIN_AUTH_COOKIE,
    ADMIN_COOKIE,
    ADMIN_CSRF_COOKIE,
)
from backend.services.auth_service import create_session, get_session_csrf
from backend.tests.conftest import requires_db

client = TestClient(app)

pytestmark = requires_db


@pytest.fixture
def cookie_session(monkeypatch):
    """Активная cookie-сессия администратора + куки для запросов."""
    monkeypatch.setenv("ALBION_AUTH_MODE", "cookie")

    token = create_session(1, user_agent="pytest-cookie")
    csrf = get_session_csrf(token)

    cookies = {
        ADMIN_COOKIE: token,
        ADMIN_CSRF_COOKIE: csrf,
        ADMIN_AUTH_COOKIE: "1",
    }

    return {"token": token, "csrf": csrf, "cookies": cookies}


def test_cookie_session_authorizes_get(cookie_session):
    response = client.get("/api/admin/me", cookies=cookie_session["cookies"])

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"


def test_post_without_csrf_header_is_rejected(cookie_session):
    """Cookie браузер отправляет сам — без заголовка изменять нельзя."""
    response = client.post(
        "/api/admin/logout",
        cookies={
            ADMIN_COOKIE: cookie_session["token"],
            ADMIN_AUTH_COOKIE: "1",
        },
    )

    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]

    # Сессия при этом жива: запрос отбит, а не выполнен.
    still_alive = client.get("/api/admin/me", cookies=cookie_session["cookies"])
    assert still_alive.status_code == 200


def test_post_with_wrong_csrf_is_rejected(cookie_session):
    response = client.post(
        "/api/admin/logout",
        cookies=cookie_session["cookies"],
        headers={"X-CSRF-Token": "wrong-token"},
    )

    assert response.status_code == 403


def test_post_with_csrf_revokes_session(cookie_session):
    response = client.post(
        "/api/admin/logout",
        cookies=cookie_session["cookies"],
        headers={"X-CSRF-Token": cookie_session["csrf"]},
    )

    assert response.status_code == 200

    # Отозванная сессия больше не пускает.
    after = client.get("/api/admin/me", cookies=cookie_session["cookies"])
    assert after.status_code == 401


def test_logout_clears_cookies(cookie_session):
    response = client.post(
        "/api/admin/logout",
        cookies=cookie_session["cookies"],
        headers={"X-CSRF-Token": cookie_session["csrf"]},
    )

    cleared = {
        header.split("=", 1)[0].strip()
        for header in response.headers.get_list("set-cookie")
    }

    assert ADMIN_COOKIE in cleared
    assert ADMIN_CSRF_COOKIE in cleared


def test_bearer_header_still_works(cookie_session):
    """Запасной путь: открытые до переключения вкладки продолжают работать."""
    response = client.get(
        "/api/admin/me",
        headers={"Authorization": f"Bearer {cookie_session['token']}"},
    )

    assert response.status_code == 200


def test_bearer_mode_ignores_cookies(monkeypatch, cookie_session):
    """В bearer-режиме cookie-сессия не даёт доступа."""
    monkeypatch.setenv("ALBION_AUTH_MODE", "bearer")

    response = client.get("/api/admin/me", cookies=cookie_session["cookies"])

    assert response.status_code == 401
