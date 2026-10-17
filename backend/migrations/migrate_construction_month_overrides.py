"""Миграция временных переопределений месячных цены и статуса конструкций.

Overrides привязаны к активному import_id и не изменяют импортированные
surface_availability. Идемпотентна.

Запуск: uv run python -m backend.migrations.migrate_construction_month_overrides
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция месячных overrides конструкций")
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS construction_month_overrides (
                    id BIGSERIAL PRIMARY KEY,
                    import_id BIGINT NOT NULL,
                    surface_hash TEXT NOT NULL,
                    year INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
                    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
                    price TEXT,
                    status TEXT CHECK (
                        status IS NULL OR status IN ('free', 'reserved', 'pending', 'busy')
                    ),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (import_id, surface_hash, year, month)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_construction_month_overrides_lookup "
                "ON construction_month_overrides (import_id, surface_hash, year, month)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON construction_month_overrides TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE "
                "ON SEQUENCE construction_month_overrides_id_seq TO albion_app"
            )
    print("COMMIT: таблица construction_month_overrides готова.")


if __name__ == "__main__":
    run()
