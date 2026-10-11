"""Детектор аномалий координат (сильно выпадающие точки)."""

from __future__ import annotations

from backend.importer.constructions_excel_to_json import (
    find_coordinate_anomalies,
)


def _rec(lat, lng, address="Точка", side="A"):
    return {
        "latitude": lat,
        "longitude": lng,
        "address": address,
        "side": side,
    }


def test_no_anomalies_when_all_close():
    records = [_rec(47.2 + i * 0.01, 39.7 + i * 0.01) for i in range(10)]

    anomalies, center = find_coordinate_anomalies(records)

    assert anomalies == []
    assert center is not None


def test_detects_far_point():
    records = [_rec(47.2 + i * 0.01, 39.7 + i * 0.01) for i in range(10)]
    records.append(_rec(43.115, 131.885, address="Владивосток", side="B"))

    anomalies, center = find_coordinate_anomalies(records)

    assert len(anomalies) == 1
    assert anomalies[0]["address"] == "Владивосток"
    assert anomalies[0]["distance_km"] > 6000


def test_too_few_points():
    assert find_coordinate_anomalies([_rec(47.2, 39.7)]) == ([], None)
