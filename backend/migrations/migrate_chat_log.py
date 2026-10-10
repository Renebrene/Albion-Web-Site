"""Миграция журнала умного чата.

Хранит ТОЛЬКО текст: вопрос, ответ и дату-время. Нужно для дальнейшего
изучения запросов пользователей. Личные данные/фото здесь не сохраняются.

Идемпотентна: повторный запуск ничего не ломает.

Запуск:  .venv/bin/python -m backend.migrations.migrate_chat_log
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция журнала умного чата")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_turns (
                    id BIGSERIAL PRIMARY KEY,

                    session_id UUID,
                    chat_key TEXT,

                    question TEXT NOT NULL,
                    answer TEXT,

                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_turns_created_at "
                "ON chat_turns (created_at DESC)"
            )
            # Отметка «выбрано» для выгрузки на анализ нейросетями.
            # Идемпотентно: повторный запуск не ломает существующую таблицу.
            conn.execute(
                "ALTER TABLE chat_turns "
                "ADD COLUMN IF NOT EXISTS selected BOOLEAN NOT NULL DEFAULT FALSE"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_turns_selected "
                "ON chat_turns (selected) WHERE selected"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON chat_turns TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE chat_turns_id_seq "
                "TO albion_app"
            )

    print("COMMIT: миграция журнала чата завершена.")
    print("  • таблица: chat_turns (колонка selected)")


if __name__ == "__main__":
    run()
