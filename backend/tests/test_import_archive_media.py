"""Архивация медиа текущего импорта при успешном импорте.

Проверяем, что archive_import_media копирует превью импорта в его архив и
идемпотентна, а при отсутствии медиа не падает (возвращает None).
"""

from __future__ import annotations

from backend.importer import import_pipeline as ip


def _patch_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ip, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(
        ip, "ARCHIVE_DIR", tmp_path / "archive" / "constructions"
    )


def test_archive_import_media_copies_previews(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)

    thumb = (
        tmp_path
        / "storage"
        / "constructions"
        / "imports"
        / "20260101-000000"
        / "photo"
        / "thumb"
    )
    thumb.mkdir(parents=True)
    (thumb / "a.jpg").write_bytes(b"preview-bytes")

    out = ip.archive_import_media("20260101-000000")

    assert out is not None
    assert (out / "photo" / "thumb" / "a.jpg").read_bytes() == b"preview-bytes"

    # Идемпотентность: повторный вызов возвращает ту же папку.
    assert ip.archive_import_media("20260101-000000") == out


def test_archive_import_media_returns_none_without_media(
    tmp_path, monkeypatch
):
    _patch_paths(tmp_path, monkeypatch)

    assert ip.archive_import_media("20990101-000000") is None
