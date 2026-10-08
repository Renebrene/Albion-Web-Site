"""Миграция БД для раздела «Настройки» админки.

Создаёт таблицу settings_presets — именованные наборы настроек
внешнего вида. Текущие настройки хранятся в site_settings
(ключ appearance, значение — JSON).

Запуск:  .venv/bin/python -m backend.migrations.migrate_settings_presets
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def main() -> None:
    print("ALBION · Миграция настроек")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_presets (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON settings_presets TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE settings_presets_id_seq TO albion_app"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_presets_name ON settings_presets (name)"
            )

            # «Быстрое переключение» — всё через ту же таблицу настроек.
            conn.execute(
                """
                INSERT INTO site_settings (key, value, value_type, description)
                VALUES (
                    'appearance',
                    '{}',
                    'json',
                    'Текущие настройки внешнего вида (JSON)'
                )
                ON CONFLICT (key) DO NOTHING
                """
            )

    print("COMMIT: миграция настроек завершена.")


if __name__ == "__main__":
    main()