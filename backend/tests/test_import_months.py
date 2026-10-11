"""Определение месяцев выгрузки (только присутствующие колонки)."""

from __future__ import annotations

from backend.importer.constructions_excel_to_json import month_columns


def test_only_present_months():
    columns = {"Октябрь": 16, "Ноябрь": 17, "Декабрь": 18, "Адрес": 4}

    assert month_columns(columns) == ["Октябрь", "Ноябрь", "Декабрь"]


def test_order_follows_canonical_months():
    columns = {"Декабрь": 3, "Август": 1}

    assert month_columns(columns) == ["Август", "Декабрь"]


def test_no_month_columns():
    assert month_columns({"Адрес": 1, "Цена за месяц": 2}) == []
