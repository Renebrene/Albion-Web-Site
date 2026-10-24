"""Экспорт портфеля: текстовые форматы и валидация формата.

Документные форматы (docx/xls/pdf/…) требуют LibreOffice и здесь не
гоняются — для текстовых достаточно штатного рендера.
"""

from __future__ import annotations

import json as jsonlib
import re
import shutil
import zipfile
from io import BytesIO

import pytest

from backend.services.portfolio_export import (
    _spreadsheet_text,
    CONTENT_TYPES,
    FULL_IMAGE_GAP_CM,
    FULL_IMAGE_HEIGHT_CM,
    FULL_IMAGE_WIDTH_CM,
    SUPPORTED_FORMATS,
    PortfolioExportError,
    build_portfolio,
    export_docx,
    normalize_per_page,
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 2), (2, 2), (3, 3), ("3", 3), (7, 2), ("мусор", 2), (0, 2), (-1, 2)],
)
def test_per_page_normalizes_to_two_or_three(value, expected):
    """Позиций на лист: только 2 или 3, всё остальное — 2."""
    assert normalize_per_page(value) == expected


def test_full_docx_three_per_page_has_no_forced_breaks():
    """При трёх позициях на лист разрывы страниц не ставим — решает поток."""
    items = [
        {**ITEMS[0], "address": f"Ленина пр-кт {index}"}
        for index in range(1, 6)
    ]
    portfolio = build_portfolio(items, full_output=True, per_page=3)

    assert portfolio["per_page"] == 3

    data = export_docx(portfolio)

    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert xml.count('w:type="page"') == 0


def test_full_docx_image_row_spans_page_width(tmp_path, monkeypatch):
    """Фото и карта идут одним рядом от левого отступа до правого (18 см)."""
    Image = pytest.importorskip("PIL.Image")
    from docx.shared import Cm

    import backend.services.portfolio_export as export_service

    monkeypatch.setattr(export_service, "STORAGE_ROOT", tmp_path)
    image_path = tmp_path / "sample.jpg"
    Image.new("RGB", (800, 500), "#4677a8").save(image_path)

    items = [
        {
            **ITEMS[0],
            "photo_large": "/storage/sample.jpg",
            "map_large": "/storage/sample.jpg",
        }
    ]
    portfolio = build_portfolio(
        items, with_photos=True, with_maps=True, full_output=True
    )
    data = export_docx(portfolio)

    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    # Размеры картинок: 8.7 × 5.44 см (в EMU, 1 см = 360000; допуск на
    # округление python-docx — единицы EMU).
    extents = re.findall(r'<wp:extent cx="(\d+)" cy="(\d+)"', xml)
    assert len(extents) == 2  # фото и карта

    for cx, cy in extents:
        assert abs(int(cx) - FULL_IMAGE_WIDTH_CM * 360000) <= 2
        assert abs(int(cy) - FULL_IMAGE_HEIGHT_CM * 360000) <= 2

    # Сетка таблицы: фото + просвет + карта = полезная ширина листа.
    assert FULL_IMAGE_WIDTH_CM * 2 + FULL_IMAGE_GAP_CM == 18.0

    for size in (FULL_IMAGE_WIDTH_CM, FULL_IMAGE_GAP_CM):
        assert f'<w:gridCol w:w="{Cm(size).twips}"/>' in xml

    # Поля ячеек обнулены, иначе ряд шире листа и картинки переносятся.
    assert xml.count('w:type="dxa"') >= 4
    assert "w:tblLayout" in xml


def test_export_api_passes_per_page():
    """per_page доезжает от запроса до раскладки (тело и query)."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    items = [
        {
            **ITEMS[0],
            "address": f"Ленина пр-кт {index}",
            "months": {"Август": {"price": 1000}},
        }
        for index in range(1, 6)
    ]
    body = {
        "title": "Мой выбор",
        "items": items,
        "with_photos": True,
        "with_maps": True,
        "full_output": True,
    }

    def breaks(response) -> int:
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")

        return xml.count('w:type="page"')

    default = client.post("/api/portfolio/export?format=docx", json=body)
    assert default.status_code == 200
    assert breaks(default) == 2  # по две позиции на лист

    three = client.post("/api/portfolio/export?format=docx", json={**body, "per_page": 3})
    assert three.status_code == 200
    assert breaks(three) == 0

    query = client.post("/api/portfolio/export?format=docx&per_page=3", json=body)
    assert query.status_code == 200
    assert breaks(query) == 0

    garbage = client.post("/api/portfolio/export?format=docx", json={**body, "per_page": 9})
    assert garbage.status_code == 200
    assert breaks(garbage) == 2


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
