"""Прямые ссылки на медиа не должны уходить в Yandex API."""

from __future__ import annotations

import json

from backend.importer import construction_media_downloader as downloader


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_direct_url_is_returned_without_yandex_api(monkeypatch):
    calls = []

    def fake_urlopen(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Yandex API не должен вызываться")

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)

    url = "https://cdn.example.com/media/photo.jpg"
    assert downloader.get_direct_link(url) == url
    assert calls == []


def test_yandex_disk_url_uses_download_api(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append(request.full_url)
        return _Response({"href": "https://downloader.example/file"})

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)

    url = "https://disk.yandex.ru/i/example"
    assert downloader.get_direct_link(url) == "https://downloader.example/file"
    assert len(calls) == 1
    assert "public_key=" in calls[0]


def test_non_http_url_is_rejected():
    try:
        downloader.get_direct_link("javascript:alert(1)")
    except ValueError:
        return

    raise AssertionError("Ожидался ValueError для не-http ссылки")
