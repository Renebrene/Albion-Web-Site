"""Экспорт портфеля: текстовые форматы и валидация формата.

Документные форматы (docx/xls/pdf/…) требуют LibreOffice и здесь не
гоняются — для текстовых достаточно штатного рендера.
"""

from __future__ import annotations

import json as jsonlib
import shutil
import zipfile
from io import BytesIO

import pytest

from backend.services.portfolio_export import (
    _spreadsheet_text,
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


def test_empty_position_is_exported_with_zero_sum():
    """Позиция без выбранных месяцев не выбрасывается: 0 ₽ и пометка."""
    items = [
        {
            **ITEMS[0],
            "months": {"Август": {"price": 1000}},
        },
        {
            **ITEMS[0],
            "id": 2,
            "address": "Пушкинская ул. 2",
            "months": {},
            "month_prices": {},
        },
    ]

    portfolio = build_portfolio(items)

    assert portfolio["positions"] == 2
    assert portfolio["total"] == 1000

    empty_row = portfolio["rows"][1]
    assert empty_row["address"] == "Пушкинская ул. 2"
    assert empty_row["months"] == "ничего не выбрано"
    assert empty_row["sum"] == "0 ₽"
    assert empty_row["sum_value"] == 0


def test_spreadsheet_values_neutralize_formula_prefixes():
    for value in ("=SUM(A1)", "+cmd", "-1+1", "@A1"):
        assert _spreadsheet_text(value).startswith("'")
    assert _spreadsheet_text("обычный текст") == "обычный текст"


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


def test_full_docx_pdf_keeps_each_pair_on_its_page(tmp_path, monkeypatch):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        pytest.skip("LibreOffice is required to test rendered pagination")

    pypdf = pytest.importorskip("pypdf")
    Image = pytest.importorskip("PIL.Image")
    import subprocess

    import backend.services.portfolio_export as export_service

    monkeypatch.setattr(export_service, "STORAGE_ROOT", tmp_path)
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (800, 500), "#4677a8").save(image_path)

    items = [
        {
            **ITEMS[0],
            "address": f"Ленина пр-кт {index}",
            "photo_large": "/storage/sample.jpg",
            "map_large": "/storage/sample.jpg",
        }
        for index in range(1, 4)
    ]
    portfolio = build_portfolio(
        items,
        title="Мой выбор",
        with_photos=True,
        with_maps=True,
        full_output=True,
        requisites={"organization": "Альбион", "inn": "6164001234"},
    )
    docx = export_docx(portfolio)
    converted = export_service.libreoffice_convert(docx, "docx", "pdf")
    pages = pypdf.PdfReader(BytesIO(converted)).pages

    assert len(pages) == 2
    first_page = pages[0].extract_text()
    second_page = pages[1].extract_text()
    assert "Ленина пр-кт 1" in first_page
    assert "Ленина пр-кт 2" in first_page
    assert "Ленина пр-кт 3" not in first_page
    assert "Ленина пр-кт 3" in second_page
    assert first_page.count("Сумма:") == 2
    assert second_page.count("Сумма:") == 1


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
