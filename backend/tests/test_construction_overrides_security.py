from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import construction_overrides as svc


def test_surface_hash_allowlist_rejects_path_components():
    assert svc.validate_surface_hash("abc_DEF-123") == "abc_DEF-123"

    for value in ("", "../escape", "a/b", r"a\\b", "a\x00b", "a" * 129):
        with pytest.raises(ValueError):
            svc.validate_surface_hash(value)


def test_contained_path_rejects_traversal(tmp_path):
    root = tmp_path / "overrides"
    root.mkdir()
    assert svc._contained_path(root, "nested/file.jpg") == root / "nested/file.jpg"

    with pytest.raises(ValueError):
        svc._contained_path(root, "../../outside.jpg")


def test_read_storage_file_requires_storage_prefix(monkeypatch, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    allowed = storage / "image.jpg"
    allowed.write_bytes(b"image")
    monkeypatch.setattr(svc, "PROJECT_DIR", tmp_path)

    data, name = svc._read_storage_file("/storage/image.jpg")
    assert data == b"image"
    assert name == "image.jpg"

    for value in ("../../.env", "/etc/passwd", "https://example.test/a.jpg"):
        with pytest.raises(ValueError):
            svc._read_storage_file(value)


def test_read_storage_file_rejects_escape(monkeypatch, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    (tmp_path / "outside.jpg").write_bytes(b"outside")
    monkeypatch.setattr(svc, "PROJECT_DIR", tmp_path)

    with pytest.raises(ValueError):
        svc._read_storage_file("/storage/../outside.jpg")
