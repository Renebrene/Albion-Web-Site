"""Смена stamp должна перечитывать overrides, даже если import_id тот же."""

from __future__ import annotations

from backend.services import construction_overrides as overrides


class _FakeConnection:
    def __init__(self) -> None:
        self.queries = 0

    def execute(self, *args, **kwargs):
        self.queries += 1
        return _FakeCursor()


class _FakeCursor:
    def fetchall(self):
        return [("hash-1", "photo", "large.jpg", "card.jpg", "thumb.jpg")]


class _FakeContext:
    def __init__(self, conn: _FakeConnection) -> None:
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc) -> None:
        return None


def test_stamp_change_bypasses_same_import_id_shortcut(monkeypatch):
    conn = _FakeConnection()

    monkeypatch.setattr(overrides, "_read_cache_stamp", lambda: "new-stamp")
    monkeypatch.setattr(overrides, "_active_import", lambda _conn: (1, "key"))
    monkeypatch.setattr(
        overrides,
        "get_connection",
        lambda: _FakeContext(conn),
    )
    monkeypatch.setattr(
        overrides,
        "_CACHE",
        {"key": 1, "stamp": "old-stamp", "map": {"stale": True}},
    )

    result = overrides.get_overrides_map()

    assert "stale" not in result
    assert result[("hash-1", "photo")]["large"] == "/large.jpg"
    assert conn.queries == 1
