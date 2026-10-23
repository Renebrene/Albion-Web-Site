"""Миграция БД для cookie-сессий админки (TZ 2.1).

Добавляет в admin_sessions:
    csrf_token — токен для заголовка X-CSRF-Token (double-submit);
    last_seen  — когда сессию видели в последний раз.

Колонки revoked_at и expires_at уже есть. Схема идемпотентна: повторный
запуск ничего не меняет.

Запуск:  .venv/bin/python -m backend.migrations.migrate_admin_session_cookies
"""

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def main() -> None:
    print("ALBION · Миграция cookie-сессий админки")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE admin_sessions ADD COLUMN IF NOT EXISTS csrf_token TEXT"
            )
            conn.execute(
                "ALTER TABLE admin_sessions "
                "ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ"
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_token_hash "
                "ON admin_sessions (token_hash)"
            )

    print("COMMIT: cookie-сессии админки готовы к работе.")


if __name__ == "__main__":
    main()
