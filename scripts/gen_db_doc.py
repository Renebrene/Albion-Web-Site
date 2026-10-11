#!/usr/bin/env python3
"""Генерирует doc/database.md из живой схемы PostgreSQL.

Запуск из корня проекта (нужны .env с доступами и подключение к БД):

    .venv/bin/python scripts/gen_db_doc.py

Скрипт детерминированный (сортировка по имени). Правьте шаблон здесь,
а не сгенерированный doc/database.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

OUT_PATH = PROJECT_DIR / "doc" / "database.md"

HEADER = (
    "<!-- СГЕНЕРИРОВАНО: scripts/gen_db_doc.py. "
    "Не редактировать вручную — правьте генератор. -->"
)

INTRO = """\
## Назначение и особенности

- СУБД: **PostgreSQL 16 + PostGIS** (расширения `postgis`, `pgcrypto`).
- Доступ из кода: `backend/services/data_service.py` → `get_connection()`.
  Контекстный менеджер psycopg3 **коммитит при выходе без исключения** —
  отдельный `commit()` обычно не нужен.
- Схема меняется **идемпотентными миграциями** в `backend/migrations/`
  (запускаются отдельно, не в каждом worker'е).
- Медиа/архивы хранятся на диске (`storage/`, `archive/`), в БД — метаданные.
"""


def _query(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def main() -> None:
    from backend.services.data_service import get_connection

    sections: dict[str, list[str]] = {
        "extensions": [],
        "tables": [],
        "fks": [],
        "views": [],
    }

    with get_connection() as conn:
        with conn.cursor() as cur:
            # --- расширения
            rows = _query(
                cur,
                "SELECT extname, extversion FROM pg_extension ORDER BY extname",
            )
            sections["extensions"] = [f"- `{n}` {v}" for n, v in rows]

            # --- таблицы
            tables = [
                r[0]
                for r in _query(
                    cur,
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "ORDER BY table_name",
                )
            ]

            # --- первичные ключи: table -> set(column)
            pk_rows = _query(
                cur,
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                WHERE tc.table_schema='public'
                  AND tc.constraint_type='PRIMARY KEY'
                """,
            )
            pk = {}
            for table, column in pk_rows:
                pk.setdefault(table, set()).add(column)

            for table in tables:
                columns = _query(
                    cur,
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    ORDER BY ordinal_position
                    """,
                    (table,),
                )

                sections["tables"].append(f"### {table}")
                sections["tables"].append("")
                sections["tables"].append(
                    "| Колонка | Тип | NULL | По умолчанию |"
                )
                sections["tables"].append("|---|---|---|---|")

                for name, dtype, nullable, default in columns:
                    marker = "🔑 " if name in pk.get(table, set()) else ""
                    default_text = (
                        f"`{default}`" if default is not None else ""
                    )
                    sections["tables"].append(
                        f"| {marker}{name} | {dtype} | "
                        f"{'да' if nullable == 'YES' else 'нет'} | "
                        f"{default_text} |"
                    )

                sections["tables"].append("")

            # --- внешние ключи
            fk_rows = _query(
                cur,
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS ref_table,
                    ccu.column_name AS ref_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema='public'
                  AND tc.constraint_type='FOREIGN KEY'
                ORDER BY tc.table_name, kcu.column_name
                """,
            )
            sections["fks"] = [
                f"- `{t}.{c}` → `{rt}.{rc}`" for t, c, rt, rc in fk_rows
            ]

            # --- представления
            views = [
                r[0]
                for r in _query(
                    cur,
                    "SELECT table_name FROM information_schema.views "
                    "WHERE table_schema='public' ORDER BY table_name",
                )
            ]
            sections["views"] = [f"- `{v}`" for v in views]

    lines: list[str] = [HEADER, "", "# База данных — схема", ""]
    lines.append(INTRO)
    lines.append("Регенерация: `.venv/bin/python scripts/gen_db_doc.py`.")
    lines.append("")
    lines.append(f"> Всего таблиц: {len(tables)}, представлений: {len(views)}. ")
    lines.append("> 🔑 — колонка первичного ключа.")
    lines.append("")

    lines.append("## Расширения")
    lines.append("")
    lines.extend(sections["extensions"])
    lines.append("")

    lines.append("## Таблицы")
    lines.append("")
    lines.extend(sections["tables"])

    lines.append("## Внешние ключи")
    lines.append("")
    lines.extend(sections["fks"] or ["- (нет)"])
    lines.append("")

    lines.append("## Представления")
    lines.append("")
    lines.extend(sections["views"] or ["- (нет)"])
    lines.append("")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"OK: {OUT_PATH} ({len(tables)} tables, {len(views)} views)")


if __name__ == "__main__":
    main()
