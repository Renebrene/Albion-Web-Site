"""Ошибка скачивания не должна терять пути к старому медиа."""

from __future__ import annotations

from backend.importer import construction_media_download as download


def test_download_entry_keeps_old_paths_for_fallback(monkeypatch):
    monkeypatch.setattr(download, "old_previews_exist", lambda record: True)

    tasks = [
        {
            "surface_id": 1,
            "surface_hash": "hash-1",
            "address": "Тестовый адрес",
            "side": "A",
            "media_type": "photo",
            "url": "https://cdn.example.com/new.jpg",
        }
    ]
    old_media = {
        ("hash-1", "photo"): {
            "original_url": "https://cdn.example.com/old.jpg",
            "original_name": "old.jpg",
            "mime_type": "image/jpeg",
            "file_size": 123,
            "width": 1200,
            "height": 800,
            "large_path": "storage/old/large.jpg",
            "card_path": "storage/old/card.jpg",
            "thumb_path": "storage/old/thumb.jpg",
        }
    }

    entries, reuse_count, download_count = download.plan_media_tasks(
        tasks,
        old_media,
    )

    assert reuse_count == 0
    assert download_count == 1
    assert entries[0]["decision"] == "download"
    assert entries[0]["old_paths"] == {
        "large": "storage/old/large.jpg",
        "card": "storage/old/card.jpg",
        "thumb": "storage/old/thumb.jpg",
    }
    assert entries[0]["old_original_url"] == "https://cdn.example.com/old.jpg"


def test_reuse_entry_keeps_old_original_url(monkeypatch):
    monkeypatch.setattr(download, "old_previews_exist", lambda record: True)

    tasks = [
        {
            "surface_id": 1,
            "surface_hash": "hash-1",
            "address": "Тестовый адрес",
            "side": "A",
            "media_type": "photo",
            "url": "https://cdn.example.com/old.jpg",
        }
    ]
    old_media = {
        ("hash-1", "photo"): {
            "original_url": "https://cdn.example.com/old.jpg",
            "original_name": "old.jpg",
            "mime_type": "image/jpeg",
            "file_size": 123,
            "width": 1200,
            "height": 800,
            "large_path": "storage/old/large.jpg",
            "card_path": "storage/old/card.jpg",
            "thumb_path": "storage/old/thumb.jpg",
        }
    }

    entries, reuse_count, download_count = download.plan_media_tasks(
        tasks,
        old_media,
    )

    assert reuse_count == 1
    assert download_count == 0
    assert entries[0]["decision"] == "reuse"
    assert entries[0]["old_original_url"] == "https://cdn.example.com/old.jpg"
