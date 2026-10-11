"""Экспорт портфеля: текстовые форматы и валидация формата.

Документные форматы (docx/xls/pdf/…) требуют LibreOffice и здесь не
гоняются — для текстовых достаточно штатного рендера.
"""

from __future__ import annotations

import json as jsonlib

import pytest

from backend.services.portfolio_export import (
    CONTENT_TYPES,
    SUPPORTED_FORMATS,
    PortfolioExportError,
    render,
)

ITEMS = [
    {
        "id": 1,
        "city": "Ростов-на-Дону",
        "address": "Ленина пр-кт 1",
        "side": "A",
        "type": "Щит",
        "size": "3x6",
        "month_prices": {"Август": 1000},
    }
]


def test_content_types_cover_all_supported_formats():
    assert set(SUPPORTED_FORMATS) == set(CONTENT_TYPES)


@pytest.mark.parametrize("fmt", ["csv", "txt", "md", "json"])
def test_text_formats_render_non_empty_bytes(fmt: str):
    data = render(ITEMS, fmt, title="Тест")

    assert isinstance(data, bytes)
    assert len(data) > 0


def test_json_format_is_valid_json():
    data = render(ITEMS, "json", title="Тест")

    parsed = jsonlib.loads(data.decode("utf-8"))
    assert parsed is not None


def test_unknown_format_is_rejected():
    with pytest.raises(PortfolioExportError):
        render(ITEMS, "nope")
