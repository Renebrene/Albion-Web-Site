from __future__ import annotations

import pytest

from backend.migrations import migrate_accounts_admin as migration
from backend.services.account_service import PASSWORD_HASH


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "SELECT id, login, role, is_active" in sql:
            return FakeResult(self.existing)
        if "INSERT INTO user_accounts" in sql:
            return FakeResult((42, "админ", "admin"))
        if "UPDATE user_accounts" in sql:
            return FakeResult()
        raise AssertionError(f"Unexpected SQL: {sql}")


def test_missing_bootstrap_secret_fails_before_db_mutation(monkeypatch):
    monkeypatch.delenv(migration.PASSWORD_ENV, raising=False)
    monkeypatch.setenv(migration.SECRET_ENV, "a" * 20)
    conn = FakeConnection()

    with pytest.raises(RuntimeError, match=migration.PASSWORD_ENV):
        migration.ensure_admin_account(conn)

    assert not any("INSERT INTO" in sql for sql, _params in conn.calls)


def test_new_account_requires_two_secrets_and_hashes_them(monkeypatch):
    password = "password-for-admin-123"
    secret = "recovery-secret-456"
    monkeypatch.setenv(migration.PASSWORD_ENV, password)
    monkeypatch.setenv(migration.SECRET_ENV, secret)
    conn = FakeConnection()

    action, account_id, login = migration.ensure_admin_account(conn)

    assert (action, account_id, login) == ("created", 42, "админ")
    insert = next((params for sql, params in conn.calls if "INSERT INTO" in sql), None)
    assert insert is not None
    assert insert[0] == "админ"
    assert insert[2] == "admin"
    assert PASSWORD_HASH.verify(password, insert[1])
    assert PASSWORD_HASH.verify(secret, insert[3])
    assert password not in repr(insert)
    assert secret not in repr(insert)


def test_existing_active_admin_is_preserved_without_secret_or_update(monkeypatch):
    monkeypatch.delenv(migration.PASSWORD_ENV, raising=False)
    monkeypatch.delenv(migration.SECRET_ENV, raising=False)
    conn = FakeConnection((7, "админ", "admin", True))

    result = migration.ensure_admin_account(conn)

    assert result == ("preserved", 7, "админ")
    assert not any("INSERT INTO" in sql or "UPDATE user_accounts" in sql for sql, _params in conn.calls)


def test_reset_existing_requires_secrets_and_updates_only_target(monkeypatch):
    monkeypatch.setenv(migration.PASSWORD_ENV, "new-admin-password-123")
    monkeypatch.setenv(migration.SECRET_ENV, "new-recovery-secret-456")
    conn = FakeConnection((7, "админ", "admin", True))

    result = migration.ensure_admin_account(conn, reset_existing=True)

    assert result == ("reset", 7, "админ")
    update = next((params for sql, params in conn.calls if "UPDATE user_accounts" in sql), None)
    assert update is not None
    assert update[2] == 7
    assert PASSWORD_HASH.verify("new-admin-password-123", update[0])
    assert PASSWORD_HASH.verify("new-recovery-secret-456", update[1])


@pytest.mark.parametrize(
    "existing",
    [
        (7, "админ", "client", True),
        (7, "админ", "admin", False),
    ],
)
def test_existing_conflicting_account_is_not_promoted(existing):
    conn = FakeConnection(existing)

    with pytest.raises(RuntimeError, match="не является активным admin"):
        migration.ensure_admin_account(conn)

    assert not any("INSERT INTO" in sql for sql, _params in conn.calls)


def test_secret_length_is_validated(monkeypatch):
    monkeypatch.setenv(migration.PASSWORD_ENV, "short")
    monkeypatch.setenv(migration.SECRET_ENV, "short")
    conn = FakeConnection()

    with pytest.raises(RuntimeError, match="минимум"):
        migration.ensure_admin_account(conn)

    assert not any("INSERT INTO" in sql for sql, _params in conn.calls)
