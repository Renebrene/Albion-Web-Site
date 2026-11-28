"""Регрессия исправлений аудита безопасности.

Покрывает: санитизацию админского HTML, нейтрализацию формул в экспорте
заявок, валидацию путей архива/сценария и выбор реального IP за nginx.
"""
from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import load_workbook
from starlette.requests import Request

from backend import main
from backend.roadrunner.scenario.engine import (
    ScenarioEngine,
    ScenarioError,
)
from backend.services import import_archive_service as archives
from backend.services.html_sanitizer import sanitize_html
from backend.services.requests_service import export_requests


# ------------------------------------------------------------- HTML


def test_sanitize_html_removes_scripts_and_event_handlers():
    dirty = (
        '<div class="ok" onclick="alert(1)">'
        '<script>alert("xss")</script>'
        '<img src="javascript:alert(1)" onerror="alert(1)">'
        '<a href="javascript:alert(1)" target="_blank">ссылка</a>'
        '<iframe src="https://evil.test"></iframe>'
        '<p>безопасный <b>текст</b></p>'
        "</div>"
    )

    clean = sanitize_html(dirty)

    assert "<script" not in clean
    assert "onclick" not in clean
    assert "onerror" not in clean
    assert "javascript:" not in clean
    assert "<iframe" not in clean
    assert 'class="ok"' in clean
    assert "<b>текст</b>" in clean
    assert 'rel="noopener noreferrer"' in clean


def test_sanitize_html_keeps_safe_markup():
    html = (
        '<p>Описание</p><ul><li>пункт</li></ul>'
        '<a href="/storage/photo.jpg">фото</a>'
    )

    assert sanitize_html(html) == html


def test_sanitize_html_drops_nested_svg_without_breaking_siblings():
    result = sanitize_html(
        '<svg onload="alert(1)"><script>alert(1)</script></svg>'
        "<p>осталось</p>"
    )

    assert "<svg" not in result
    assert "<script" not in result
    assert "<p>осталось</p>" in result


# ------------------------------------------------------- экспорт заявок


def _fake_requests(monkeypatch, comment: str):
    rows = [
        {
            "id": 1,
            "created_at": "2026-11-27T00:00:00",
            "account_login": None,
            "title": "Заявка",
            "status": "new",
            "payload": {
                "name": "Иван",
                "phone": "+7 (900) 000-00-00",
                "email": "a@b.ru",
                "comment": comment,
                "items": [{"title": "=HYPERLINK(\"https://evil.test\")"}],
            },
        }
    ]

    monkeypatch.setattr(
        "backend.services.account_service.list_all_requests",
        lambda limit=1000: rows,
    )


def test_requests_csv_neutralizes_formulas(monkeypatch):
    payload = '=HYPERLINK("https://evil.test","click")'
    _fake_requests(monkeypatch, payload)

    content, name, _ = export_requests("csv")

    assert name == "zayavki.csv"
    text = content.decode("utf-8-sig")
    # csv.writer удваивает кавычки внутри поля.
    escaped = payload.replace('"', '""')
    assert "'" + escaped in text
    assert ";=" not in text


def test_requests_xlsx_has_no_formula_cells(monkeypatch):
    payload = '=HYPERLINK("https://evil.test","click")'
    _fake_requests(monkeypatch, payload)

    content, name, _ = export_requests("xlsx")

    assert name == "zayavki.xlsx"
    sheet = load_workbook(BytesIO(content)).active

    values = [cell.value for row in sheet.iter_rows() for cell in row]
    assert any(str(value).startswith("'" + payload) for value in values)
    assert all(cell.data_type != "f" for row in sheet.iter_rows() for cell in row)


# ------------------------------------------------------- ключ архива


def test_import_key_validation():
    for key in ("20261024-181734", "archive_1", "a.b-c"):
        assert archives.validate_import_key(key) == key

    for key in ("", "..", "a/../b", "/etc", "a b", "x\\y"):
        with pytest.raises(ValueError):
            archives.validate_import_key(key)


def test_archive_dir_stays_inside_root(tmp_path, monkeypatch):
    monkeypatch.setattr(archives, "CONSTRUCTIONS_ARCHIVE_ROOT", tmp_path)
    archive = tmp_path / "20261024-181734"
    archive.mkdir()

    assert archives._archive_dir("20261024-181734") == archive.resolve()

    with pytest.raises(ValueError):
        archives._archive_dir("..")


# ------------------------------------------------------------ сценарий


def test_scenario_from_file_reads_slug_without_extension():
    engine = ScenarioEngine.from_file("valentines-day")

    assert engine.scenario_id
    assert engine.events


def test_scenario_from_file_rejects_traversal_and_missing():
    for value in ("..", "../secret", "/etc/passwd", "nope", "a/b"):
        with pytest.raises(ScenarioError):
            ScenarioEngine.from_file(value)


# -------------------------------------------------------------- IP


def _request(path: str, host: str, headers: list[tuple[bytes, bytes]]) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": headers,
            "client": (host, 1234),
            "server": ("test", 8000),
            "scheme": "http",
        }
    )


def test_client_ip_trusts_real_ip_only_from_loopback():
    headers = [(b"x-real-ip", b"203.0.113.7")]

    assert main._client_ip(_request("/api/admin/login", "127.0.0.1", headers)) == "203.0.113.7"
    assert main._client_ip(_request("/api/admin/login", "198.51.100.10", headers)) == "198.51.100.10"
    assert main._client_ip(_request("/api/admin/login", "127.0.0.1", [])) == "127.0.0.1"
