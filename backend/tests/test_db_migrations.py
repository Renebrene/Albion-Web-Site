"""БД и миграции: подключение и идемпотентность миграций."""

from __future__ import annotations

from backend.migrations import migrate_contacts_v2
from backend.services.data_service import get_connection
from backend.tests.conftest import requires_db


@requires_db
def test_database_connection_works():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()

    assert row[0] == 1


@requires_db
def test_contacts_migration_is_idempotent():
    """Повторный прогон миграции не падает и не ломает схему."""
    with get_connection() as conn:
        migrate_contacts_v2.ensure_columns(conn)
        # Второй прогон должен пройти без ошибок (идемпотентность).
        migrate_contacts_v2.ensure_columns(conn)
