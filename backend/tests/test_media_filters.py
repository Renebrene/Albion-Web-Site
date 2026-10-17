from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.auth_api import require_admin
from backend.services.media_service import _media_filter_sql


client = TestClient(app)


@pytest.fixture(autouse=True)
def _admin_auth():
    app.dependency_overrides[require_admin] = lambda: {"user": {"role": "admin"}}
    yield
    app.dependency_overrides.pop(require_admin, None)


def test_media_filter_sql_combines_filters_with_bound_values():
    where, params = _media_filter_sql(
        category_ids=[2, 7],
        category_id=9,
        search="  banner%  ",
        media_type="video",
        date_from=date(2026, 1, 2),
        date_to=date(2026, 1, 3),
    )

    assert "m.category_id && %s::bigint[]" in where
    assert "%s::bigint = ANY(m.category_id)" not in where
    assert "m.original_name ILIKE %s" in where
    assert "COALESCE(m.alt, '') ILIKE %s" in where
    assert "COALESCE(m.title, '') ILIKE %s" in where
    assert "m.mime_type LIKE 'video/%'" in where
    assert "m.created_at >= %s" in where
    assert "m.created_at < %s" in where
    assert params == [
        [2, 7],
        "%banner%%",
        "%banner%%",
        "%banner%%",
        date(2026, 1, 2),
        date(2026, 1, 4),
    ]


@pytest.mark.parametrize(
    ("media_type", "expected", "forbidden"),
    [
        ("photo", "m.mime_type LIKE 'image/%'", "m.mime_type LIKE 'video/%'"),
        ("video", "m.mime_type LIKE 'video/%'", "m.mime_type LIKE 'image/%'"),
        (
            "document",
            "m.mime_type NOT LIKE 'image/%' AND m.mime_type NOT LIKE 'video/%'",
            "m.mime_type LIKE 'image/%'",
        ),
        ("all", "", "m.mime_type"),
    ],
)
def test_media_type_sql(media_type: str, expected: str, forbidden: str):
    where, params = _media_filter_sql(media_type=media_type)
    assert expected in where
    assert forbidden not in where
    assert params == []


def test_admin_media_endpoint_passes_filters_and_returns_exact_total(monkeypatch):
    from backend import main

    captured = {}

    def fake_list_media(**kwargs):
        captured.update(kwargs)
        return ([{"id": 1}], 17)

    monkeypatch.setattr(main, "list_media", fake_list_media)
    response = client.get(
        "/api/admin/media",
        params={
            "limit": 10,
            "offset": 5,
            "category_id": 3,
            "category_ids": "2, 7,2",
            "search": "poster",
            "media_type": "photo",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "media": [{"id": 1}],
        "has_more": False,
        "total": 17,
    }
    assert captured == {
        "limit": 11,
        "offset": 5,
        "category_id": 3,
        "category_ids": [2, 7],
        "search": "poster",
        "media_type": "photo",
        "date_from": date(2026, 3, 1),
        "date_to": date(2026, 3, 31),
        "include_total": True,
    }


def test_admin_media_endpoint_keeps_legacy_category_id(monkeypatch):
    from backend import main

    captured = {}
    monkeypatch.setattr(main, "list_media", lambda **kwargs: (captured.update(kwargs) or [], 0))

    response = client.get("/api/admin/media", params={"category_id": 4})

    assert response.status_code == 200
    assert captured["category_id"] == 4
    assert captured["category_ids"] is None
    assert response.json()["total"] == 0


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"media_type": "audio"}, 422),
        ({"date_from": "2026-02-30"}, 422),
        ({"date_from": "2026-04-01", "date_to": "2026-03-31"}, 422),
        ({"category_ids": "1,nope"}, 422),
        ({"category_ids": "0"}, 422),
        ({"category_ids": ","}, 422),
    ],
)
def test_admin_media_endpoint_rejects_invalid_filters(params, expected_status):
    response = client.get("/api/admin/media", params=params)
    assert response.status_code == expected_status
