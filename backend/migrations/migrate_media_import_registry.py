"""Идемпотентная миграция: таблица media_import_registry.

Таблица используется импортёром и ремонтом схемы (``CONSTRUCTIONS_TABLES``,
``constructions_schema``), но её DDL в репозитории отсутствовал: на
существующей базе она есть, а при развёртывании «с нуля» её не создаёт ни
одна миграция. Скрипт досоздаёт таблицу и последовательность, если их нет;
на уже существующей базе — ничего не делает.

Запуск:
    .venv/bin/python -m backend.migrations.migrate_media_import_registry
"""
from __future__ import annotations

from backend.services.data_service import get_connection


# Порядок важен: сначала последовательность, затем таблица с DEFAULT на неё.
DDL = [
    "CREATE SEQUENCE IF NOT EXISTS media_import_registry_id_seq",
    """
    CREATE TABLE IF NOT EXISTS media_import_registry (
        id            bigint NOT NULL
                      DEFAULT nextval('media_import_registry_id_seq'),
        filename      text NOT NULL,
        row_hash      text NOT NULL,
        media_type    text NOT NULL,
        original_link text,
        address       text,
        side          text,
        status        text NOT NULL,
        file_size     bigint,
        downloaded_at timestamp with time zone,
        created_at    timestamp with time zone NOT NULL DEFAULT now(),
        CONSTRAINT media_import_registry_pkey PRIMARY KEY (id),
        CONSTRAINT media_import_registry_media_type_check
            CHECK (media_type IN ('photo', 'map'))
    )
    """,
    "ALTER SEQUENCE media_import_registry_id_seq "
    "OWNED BY media_import_registry.id",
]


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in DDL:
                cur.execute(statement)

    print("media_import_registry: таблица и последовательность готовы")


if __name__ == "__main__":
    main()
