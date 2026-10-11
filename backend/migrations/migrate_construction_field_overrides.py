"""Миграция временных переопределений основных полей конструкций.

Одна строка на поверхность: ``fields`` — JSONB с изменёнными значениями
(адрес, город, район, тип, размер, сторона, свет, материал, номер). Привязано
к активному импорту: пока он активен — сайт отдаёт изменённые значения; после
следующего импорта переопределение перестаёт применяться.

Идемпотентна.

Запуск:  .venv/bin/python -m backend.migrations.migrate_construction_field_overrides
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция переопределений полей конструкций")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS construction_field_overrides (
                    surface_hash TEXT PRIMARY KEY,
                    import_id BIGINT,
                    fields JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cm_field_overrides_import "
                "ON construction_field_overrides (import_id)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON construction_field_overrides TO albion_app"
            )

    print("COMMIT: миграция переопределений полей завершена.")
    print("  • таблица: construction_field_overrides")


if __name__ == "__main__":
    run()
