"""Миграция БД: реквизиты пользователя ЛК.

Добавляет в таблицу user_accounts колонку:
  • requisites JSONB NOT NULL DEFAULT '{}'::jsonb
    — реквизиты организации для выгрузки/печати портфеля
      (организация, ИНН, КПП, адрес, телефон, e-mail, контактное лицо).

Идемпотентна: повторный запуск ничего не ломает
(ALTER TABLE … ADD COLUMN IF NOT EXISTS).

Запуск:  .venv/bin/python -m backend.migrations.migrate_accounts_requisites
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция реквизитов пользователя ЛК")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                ALTER TABLE user_accounts
                ADD COLUMN IF NOT EXISTS requisites JSONB NOT NULL
                    DEFAULT '{}'::jsonb
                """
            )

    print("COMMIT: миграция реквизитов завершена.")
    print("  • колонка: user_accounts.requisites (JSONB)")


if __name__ == "__main__":
    run()
