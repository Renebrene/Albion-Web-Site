"""Тесты пространственной выборки (read-only, без записей в БД)."""
import sys

import pytest

from backend.search import spatial


def test_haversine_m_and_radius_filter():
    d = spatial.haversine_m(0, 0, 1, 0)
    assert 110_000 < d < 112_000

    items = [
        {"id": "near", "latitude": 47.2357, "longitude": 39.7015},
        {"id": "far", "latitude": 49.5, "longitude": 39.7015},
        {"id": "zero", "latitude": 0.0, "longitude": 0.0},
        {"id": "bad", "latitude": None, "longitude": "x"},
    ]
    out = spatial.radius_filter(items, 47.2357, 39.7015, 50_000)
    assert "near" in [x["id"] for x in out]
    assert "far" not in [x["id"] for x in out]
    assert "zero" not in [x["id"] for x in out]
    assert "bad" not in [x["id"] for x in out]
    assert all(x["distance_m"] <= 50_000 for x in out)
    assert out == sorted(out, key=lambda x: x["distance_m"])


def test_sql_is_readonly_and_region_free():
    sql = spatial.construction_ids_near_sql().upper()
    assert "ST_DWITHIN" in sql
    assert "ST_DISTANCE" in sql
    assert "ST_MAKEPOINT" in sql
    assert "4326" in sql
    assert "%(LNG)" in sql and "%(LAT)" in sql and "%(RADIUS_M)" in sql
    assert "SURFACES" in sql and "CONSTRUCTIONS" in sql
    assert "GROUP BY" in sql and "ORDER BY DIST_M" in sql
    for token in ("INSERT", "UPDATE ", "DELETE", "CREATE", "ALTER", "DROP", "TRUNCATE"):
        assert token not in sql


def _connection():
    from backend.services.data_service import get_connection
    return get_connection()


def test_live_surface_ids_are_surface_ids():
    try:
        with _connection() as conn:
            center = conn.execute(
                "SELECT ST_Y(location), ST_X(location) FROM surfaces "
                "WHERE location IS NOT NULL ORDER BY id LIMIT 1"
            ).fetchone()
            if not center:
                pytest.skip("нет surfaces с координатами")
            lat, lng = float(center[0]), float(center[1])
            ids = spatial.find_surface_ids_near(conn, lat, lng, 50_000, limit=5)
            if not ids:
                pytest.skip("нет поверхностей в радиусе")
            rows = conn.execute(
                "SELECT id FROM surfaces WHERE id = ANY(%s::bigint[])",
                (ids,),
            ).fetchall()
    except Exception as exc:
        pytest.skip(f"БД недоступна: {exc}")

    assert {int(row[0]) for row in rows} == set(ids)


def test_live_readonly_postgis_select():
    try:
        with _connection() as conn:
            center = conn.execute(
                "SELECT ST_Y(location), ST_X(location) FROM surfaces "
                "WHERE location IS NOT NULL ORDER BY id LIMIT 1"
            ).fetchone()
            if not center:
                pytest.skip("нет surfaces с координатами")
            lat, lng = float(center[0]), float(center[1])
            ids = spatial.find_construction_ids_near(conn, lat, lng, 50_000, limit=5)
    except Exception as exc:
        pytest.skip(f"БД недоступна: {exc}")

    assert len(ids) >= 1
    assert len(ids) <= 5
    assert len(ids) == len(set(ids))
