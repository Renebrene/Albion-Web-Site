"""Миграция БД для отслеживания визитов: таблица page_visits.

Хранит обезличенную статистику заходов на страницы:
время, путь, страна (по IP в момент визита), устройство/браузер и
необратимый visitor_hash. IP-адрес НЕ хранится ни в этой таблице, ни
в логах.

Дополнительно создаёт соль visit_salt в site_settings (нужна для
visitor_hash) — без неё посетители считались бы одинаково.

Запуск:  .venv/bin/python -m backend.migrations.migrate_page_visits
"""
import secrets

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

SALT_KEY = "visit_salt"


def main() -> None:
    print("ALBION · Миграция: отслеживание визитов (page_visits)")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS page_visits (
                    id            BIGSERIAL PRIMARY KEY,
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    path          TEXT NOT NULL,
                    referrer      TEXT,
                    country_code  TEXT,
                    country_name  TEXT,
                    is_bot        BOOLEAN NOT NULL DEFAULT FALSE,
                    device        TEXT,
                    browser       TEXT,
                    visitor_hash  TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON page_visits TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE page_visits_id_seq TO albion_app"
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_visits_created "
                "ON page_visits (created_at DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_visits_country "
                "ON page_visits (country_code)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_visits_path "
                "ON page_visits (path)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_page_visits_visitor "
                "ON page_visits (visitor_hash)"
            )

            # Соль для хеширования посетителей (стабильная, создаётся один раз).
            conn.execute(
                """
                INSERT INTO site_settings (key, value, value_type, description)
                VALUES (%s, %s, 'text', 'Соль хеширования посетителей')
                ON CONFLICT (key) DO NOTHING
                """,
                (SALT_KEY, secrets.token_hex(32)),
            )

    print("COMMIT: миграция визитов завершена.")
    print("  • таблица: page_visits")
    print("  • site_settings: соль visit_salt")


if __name__ == "__main__":
    main()
