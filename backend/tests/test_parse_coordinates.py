"""Разбор координат из выгрузки 1С."""

from __future__ import annotations

import pytest

from backend.importer.constructions_excel_to_json import parse_coordinates


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("47.776737, 39.879076", (47.776737, 39.879076)),
        ("47.2566,39.7688", (47.2566, 39.7688)),
        # десятичная запятая в долготе
        ("47.2117, 39,7363", (47.2117, 39.7363)),
        # точка с запятой как разделитель
        ("47.2117; 39.7363", (47.2117, 39.7363)),
    ],
)
def test_parse_coordinates_ok(raw, expected):
    assert parse_coordinates(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        None,
        "нет данных",
        "47.2117",  # одна часть
        "100.0, 39.7",  # широта вне диапазона
        "47.2, 200.0",  # долгота вне диапазона
    ],
)
def test_parse_coordinates_rejects(raw):
    assert parse_coordinates(raw) == (None, None)
