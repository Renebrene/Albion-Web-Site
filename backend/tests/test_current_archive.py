"""Ручной архив текущей базы конструкций (create_current_archive)."""

from __future__ import annotations

import pytest

from backend.importer import import_pipeline as ip


def _patch_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ip, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(
        ip, "ARCHIVE_DIR", tmp_path / "archive" / "constructions"
    )


def test_create_current_archive_assembles_dump_source_media(
    tmp_path, monkeypatch
):
    _patch_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(ip, "active_import_key", lambda: "20260101-000000")

    def fake_dump(destination, selectors):
        assert selectors, "должны передаваться селекторы таблиц"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"dump")

    monkeypatch.setattr(ip, "_pg_dump", fake_dump)

    # source.xlsx в архиве активного импорта.
    active_archive = ip.ARCHIVE_DIR / "20260101-000000"
    active_archive.mkdir(parents=True)
    (active_archive / "source.xlsx").write_bytes(b"xls")

    # медиа активного импорта (с превью).
    thumb = (
        ip.PROJECT_DIR
        / "storage"
        / "constructions"
        / "imports"
        / "20260101-000000"
        / "photo"
        / "thumb"
    )
    thumb.mkdir(parents=True)
    (thumb / "a.jpg").write_bytes(b"img")

    result = ip.create_current_archive("test")
    dest = ip.ARCHIVE_DIR / result["import_key"]

    assert result["import_key"].startswith("test-")
    assert result["active_import_key"] == "20260101-000000"
    assert (dest / "database.dump").read_bytes() == b"dump"
    assert (dest / "source.xlsx").read_bytes() == b"xls"
    assert (dest / "media" / "photo" / "thumb" / "a.jpg").read_bytes() == b"img"


def test_create_current_archive_requires_active_import(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(ip, "active_import_key", lambda: None)

    with pytest.raises(RuntimeError):
        ip.create_current_archive("test")
