"""Миграция сохранённых чатов аккаунта.

Одна строка на аккаунт: payload — JSONB со списком чатов (номер и текстовая
история «вопрос–ответ»). Позволяет восстановить чаты при следующем заходе.

Идемпотентна.

Запуск:  .venv/bin/python -m backend.migrations.migrate_account_chats
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция сохранённых чатов аккаунта")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_chats (
                    id BIGSERIAL PRIMARY KEY,
                    account_id BIGINT NOT NULL UNIQUE
                        REFERENCES user_accounts(id) ON DELETE CASCADE,
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON account_chats TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE account_chats_id_seq "
                "TO albion_app"
            )

    print("COMMIT: миграция сохранённых чатов завершена.")
    print("  • таблица: account_chats")


if __name__ == "__main__":
    run()
