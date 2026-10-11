"""Таблица media_import_registry: наличие, колонки и валидность DDL миграции."""

from __future__ import annotations

from backend.migrations import migrate_media_import_registry as mig
from backend.services.data_service import get_connection
from backend.tests.conftest import requires_db

EXPECTED_COLUMNS = {
    "id",
    "filename",
    "row_hash",
    "media_type",
    "original_link",
    "address",
    "side",
    "status",
    "file_size",
    "downloaded_at",
    "created_at",
}


@requires_db
def test_table_exists_with_expected_columns():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='media_import_registry'
                """
            )
            columns = {row[0] for row in cur.fetchall()}

    assert EXPECTED_COLUMNS <= columns


@requires_db
def test_migration_ddl_is_valid_and_creates_table():
    """Прогоняем DDL миграции под временным именем и откатываем.

    Так проверяем сам CREATE-путь (на «боевой» таблице он не выполняется,
    т.к. она уже есть), не трогая данные.
    """
    smoke = "media_import_registry_smoke"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")

            try:
                for statement in mig.DDL:
                    cur.execute(
                        statement.replace("media_import_registry", smoke)
                    )

                cur.execute(
                    "SELECT to_regclass(%s)",
                    (f"public.{smoke}",),
                )
                assert cur.fetchone()[0] is not None
            finally:
                cur.execute("ROLLBACK")

            cur.execute("SELECT to_regclass(%s)", (f"public.{smoke}",))
            assert cur.fetchone()[0] is None
