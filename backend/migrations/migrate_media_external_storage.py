"""Внешнее хранилище для медиатеки (Albion).

Добавляет аддитивные поля к ``media`` и ``media_variants``:

* ``storage_backend`` — ``local`` (по умолчанию) или ``albion``;
* ``external_url`` — публичная ссылка Albion;
* ``external_key`` — идентификатор объекта в Albion для удаления.

Миграция идемпотентна: повторный запуск ничего не меняет. Backfill не нужен:
старые строки получают ``local`` через DEFAULT.

Запуск: .venv/bin/python -m backend.migrations.migrate_media_external_storage
"""
from __future__ import annotations

from backend.services.data_service import get_connection


TABLES = ("media", "media_variants")

COLUMN_DEFINITIONS = (
    ("storage_backend", "TEXT NOT NULL DEFAULT 'local'"),
    ("external_url", "TEXT"),
    ("external_key", "TEXT"),
)

CHECK_CONSTRAINTS = {
    "media": "media_storage_backend_check",
    "media_variants": "media_variants_storage_backend_check",
}


def column_sql(table: str) -> str:
    additions = ", ".join(
        f"ADD COLUMN IF NOT EXISTS {name} {definition}"
        for name, definition in COLUMN_DEFINITIONS
    )
    return f"ALTER TABLE {table} {additions}"


COLUMN_STATEMENTS = tuple(column_sql(table) for table in TABLES)


def ensure_columns(cur) -> None:
    for statement in COLUMN_STATEMENTS:
        cur.execute(statement)


def ensure_check_constraint(cur, table: str, name: str) -> None:
    cur.execute(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conname = %s
          AND conrelid = %s::regclass
        """,
        (name, table),
    )

    if cur.fetchone() is None:
        cur.execute(
            f"""
            ALTER TABLE {table}
            ADD CONSTRAINT {name}
            CHECK (storage_backend IN ('local', 'albion')) NOT VALID
            """
        )

    # NOT VALID не проверяет старые строки; после backfill-совместимого
    # DEFAULT их значение всегда local. VALIDATE идемпотентен.
    cur.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}")


def apply(conn) -> None:
    with conn.cursor() as cur:
        ensure_columns(cur)

        for table in TABLES:
            ensure_check_constraint(cur, table, CHECK_CONSTRAINTS[table])


def main() -> None:
    with get_connection() as conn:
        apply(conn)

    print("Медиа: добавлены поля storage_backend/external_url/external_key")


if __name__ == "__main__":
    main()
