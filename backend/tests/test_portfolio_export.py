"""Экспорт портфеля: текстовые форматы и валидация формата.

Документные форматы (docx/xls/pdf/…) требуют LibreOffice и здесь не
гоняются — для текстовых достаточно штатного рендера.
"""

from __future__ import annotations

import json as jsonlib
import zipfile
from io import BytesIO

import pytest

from backend.services.portfolio_export import (
    CONTENT_TYPES,
    SUPPORTED_FORMATS,
    PortfolioExportError,
    build_portfolio,
    export_docx,
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


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_full_docx_starts_each_pair_on_new_page(count: int):
    items = [
        {**ITEMS[0], "address": f"Ленина пр-кт {index}"}
        for index in range(1, count + 1)
    ]
    portfolio = build_portfolio(items, full_output=True)
    data = export_docx(portfolio)

    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    page_break_count = xml.count('w:type="page"')
    assert page_break_count == (count - 1) // 2
    for index in range(1, count + 1):
        assert f"Ленина пр-кт {index}" in xml


def test_full_reportlab_pdf_keeps_two_item_groups_on_distinct_pages():
    pytest.importorskip("reportlab")
    from backend.services.portfolio_export import export_pdf

    items = [
        {**ITEMS[0], "address": f"Ленина пр-кт {index}"}
        for index in range(1, 5)
    ]
    portfolio = build_portfolio(items, full_output=True)
    data = export_pdf(portfolio)

    assert data.startswith(b"%PDF-")


def test_unknown_format_is_rejected():
    with pytest.raises(PortfolioExportError):
        render(ITEMS, "nope")
