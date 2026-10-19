"""Fallback копирует старые превью в новый импорт."""

from __future__ import annotations

from backend.importer import construction_media_preview as preview


def test_reuse_one_copies_old_previews(tmp_path, monkeypatch):
    monkeypatch.setattr(preview, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(
        preview,
        "STORAGE_ROOT",
        tmp_path / "storage" / "constructions" / "imports",
    )

    old_paths = {}
    for variant in ("large", "card", "thumb"):
        old = tmp_path / "storage" / "old" / f"{variant}.jpg"
        old.parent.mkdir(parents=True, exist_ok=True)
        old.write_bytes(b"old-" + variant.encode())
        old_paths[variant] = str(old.relative_to(tmp_path))

    entry = {
        "surface_hash": "hash-1",
        "media_type": "photo",
        "old_paths": old_paths,
    }

    result = preview.reuse_one(entry, "20260101-000000")

    assert result["status"] == "ok"
    assert set(result["paths"]) == {"large", "card", "thumb"}

    for relative in result["paths"].values():
        copied = tmp_path / relative
        assert copied.is_file()
        assert copied.read_bytes().startswith(b"old-")
