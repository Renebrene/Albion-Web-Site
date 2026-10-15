"""Заявки без личного кабинета.

Личный кабинет скрыт (см. doc/account-cabinet.md), но заявки должны
работать: клиент отправляет форму с сайта без входа. Для этого
``client_requests.account_id`` становится NULLABLE — у анонимной заявки
он пустой, а контакты (имя, телефон, комментарий) лежат в ``payload``.

Миграция идемпотентна: повторный запуск ничего не меняет.

Запуск:  .venv/bin/python -m backend.migrations.migrate_requests_anonymous
"""

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def main() -> None:
    print("ALBION · Миграция: заявки без личного кабинета")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                ALTER TABLE client_requests
                    ALTER COLUMN account_id DROP NOT NULL
                """
            )

            # Индекс под выборку анонимных/свежих заявок в админке.
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_requests_account
                    ON client_requests (account_id)
                """
            )

    print("  client_requests.account_id → NULLABLE (готово)")


if __name__ == "__main__":
    main()
