"""Ремонт схемы таблиц конструкций после неполного восстановления из архива.

Возвращает таблицам конструкций DEFAULT, PRIMARY KEY, UNIQUE/FK/CHECK и
индексы (их терял старый `pg_restore -t <таблица>` — отдельные записи дампа
с другими именами не выбирались). Логика вынесена в
backend/services/constructions_schema.py и переиспользуется восстановлением
из архива.

Идемпотентно. Запуск:
    .venv/bin/python -m backend.migrations.migrate_repair_constructions_schema
"""
from __future__ import annotations

from backend.services.constructions_schema import repair_schema
from backend.services.data_service import get_connection


def main() -> None:
    with get_connection() as conn:
        result = repair_schema(conn)

    print(f"Идентичность (DEFAULT+owned): {result['defaults']}")
    print(f"PRIMARY KEY добавлено:        {result['primary_keys']}")
    print(f"UNIQUE/FK/CHECK добавлено:    {result['constraints']}")
    print(f"Индексов применено:           {result['indexes']}")


if __name__ == "__main__":
    main()
