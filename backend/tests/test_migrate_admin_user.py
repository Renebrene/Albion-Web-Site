from __future__ import annotations

import pytest

from backend.migrations import migrate_admin_user as migration
from backend.services.auth_service import PASSWORD_HASH


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT id, login FROM admin_users" in sql:
            return Result(self.existing)
        if "INSERT INTO admin_users" in sql:
            return Result((11, params[0], "admin"))
        raise AssertionError(sql)


def configured(monkeypatch, password="long-panel-password-123"):
    monkeypatch.setenv(migration.LOGIN_ENV, "albion_panel_x7k29")
    monkeypatch.setenv(migration.PASSWORD_ENV, password)
    monkeypatch.setenv(migration.NAME_ENV, "Panel Administrator")


def test_missing_secret_fails_before_write(monkeypatch):
    monkeypatch.delenv(migration.LOGIN_ENV, raising=False)
    monkeypatch.delenv(migration.PASSWORD_ENV, raising=False)
    monkeypatch.delenv(migration.NAME_ENV, raising=False)
    conn = Connection()

    with pytest.raises(RuntimeError, match=migration.LOGIN_ENV):
        migration.ensure_admin_user(conn)

    assert not any("INSERT" in sql for sql, _ in conn.calls)


def test_short_login_and_password_are_rejected(monkeypatch):
    configured(monkeypatch, password="short")
    monkeypatch.setenv(migration.LOGIN_ENV, "short")
    conn = Connection()

    with pytest.raises(RuntimeError):
        migration.ensure_admin_user(conn)
    assert not any("INSERT" in sql for sql, _ in conn.calls)


def test_new_admin_is_hashed_and_created(monkeypatch):
    configured(monkeypatch)
    conn = Connection()

    result = migration.ensure_admin_user(conn)

    assert result == ("created", 11, "albion_panel_x7k29")
    insert = next(params for sql, params in conn.calls if "INSERT" in sql)
    assert insert[0] == "albion_panel_x7k29"
    assert insert[2] == "Panel Administrator"
    assert PASSWORD_HASH.verify("long-panel-password-123", insert[1])
    assert "long-panel-password-123" not in repr(insert)


def test_duplicate_login_fails_without_update(monkeypatch):
    configured(monkeypatch)
    conn = Connection((11, "albion_panel_x7k29"))

    with pytest.raises(RuntimeError, match="уже существует"):
        migration.ensure_admin_user(conn)

    assert not any("INSERT" in sql for sql, _ in conn.calls)
