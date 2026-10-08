"""Миграция БД для личных кабинетов (ЛК) клиентов и менеджеров.

Создаёт таблицы:
  • user_accounts    — аккаунты (логин + хеш пароля + хеш секретной фразы);
  • account_sessions — активные сессии (хранится только SHA-256 хеш token);
  • client_requests  — заявки клиентов.

Персональные данные не хранятся: только логин, хеши и технические поля.

Запуск:  .venv/bin/python -m backend.migrations.migrate_accounts
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def main() -> None:
    print("ALBION · Миграция личных кабинетов (ЛК)")

    with get_connection() as conn:
        with conn.transaction():
            # ------------------------------------------------------------------
            # Аккаунты
            # ------------------------------------------------------------------
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_accounts (
                    id BIGSERIAL PRIMARY KEY,
                    login TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'client',
                    secret_phrase_hash TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON user_accounts TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE user_accounts_id_seq TO albion_app"
            )
            # Логин регистронезависимый.
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_user_accounts_login_lower
                ON user_accounts (lower(login))
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_accounts_login ON user_accounts (login)"
            )

            # ------------------------------------------------------------------
            # Сессии аккаунтов
            # ------------------------------------------------------------------
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    account_id BIGINT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON account_sessions TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE account_sessions_id_seq TO albion_app"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_account_sessions_account
                ON account_sessions (account_id)
                """
            )

            # ------------------------------------------------------------------
            # Заявки клиентов
            # ------------------------------------------------------------------
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_requests (
                    id BIGSERIAL PRIMARY KEY,
                    account_id BIGINT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT '',
                    surface_id BIGINT NULL,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON client_requests TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE client_requests_id_seq TO albion_app"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_requests_account
                ON client_requests (account_id, created_at DESC)
                """
            )

    print("COMMIT: миграция личных кабинетов завершена.")
    print("  • таблицы: user_accounts, account_sessions, client_requests")


if __name__ == "__main__":
    main()
