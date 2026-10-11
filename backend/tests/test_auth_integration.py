"""Интеграционные тесты авторизации админки."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.tests.conftest import requires_db

client = TestClient(app)


def test_admin_me_without_token_is_rejected():
    """Защищённый эндпоинт без токена не отдаёт данные."""
    response = client.get("/api/admin/me")

    assert response.status_code in (401, 403)


def test_admin_endpoint_without_token_is_rejected():
    response = client.get("/api/admin/settings")

    assert response.status_code in (401, 403)


@requires_db
def test_admin_login_with_wrong_credentials():
    response = client.post(
        "/api/admin/login",
        json={"login": "__no_such_admin__", "password": "__wrong__"},
    )

    assert response.status_code == 401
    assert "token" not in response.json()
