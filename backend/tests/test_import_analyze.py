"""ANALYZE после импорта обновляет статистику всех заменяемых таблиц."""

from backend.importer import staging_to_postgres


class _FakeConnection:
    def __init__(self) -> None:
        self.sql = None

    def execute(self, sql: str) -> None:
        self.sql = sql


def test_analyze_loaded_tables_covers_import_tables():
    conn = _FakeConnection()

    staging_to_postgres.analyze_loaded_tables(conn)

    assert conn.sql is not None
    assert conn.sql.startswith("ANALYZE ")

    for table in staging_to_postgres.ANALYZE_TABLES:
        assert table in conn.sql
