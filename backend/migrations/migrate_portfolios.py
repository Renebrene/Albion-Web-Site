"""Миграция БД для «Портфеля» — корзины избранных поверхностей аккаунта.

Создаёт таблицу:
  • account_portfolios — портфель аккаунта (один на пользователя);
    payload — JSONB со списком позиций и служебной версией схемы.

Идемпотентна: повторный запуск ничего не ломает (CREATE TABLE IF NOT EXISTS).

Запуск:  .venv/bin/python -m backend.migrations.migrate_portfolios
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция портфелей (избранные поверхности)")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_portfolios (
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
                "GRANT SELECT, INSERT, UPDATE, DELETE ON account_portfolios TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE account_portfolios_id_seq TO albion_app"
            )

    print("COMMIT: миграция портфелей завершена.")
    print("  • таблица: account_portfolios")


if __name__ == "__main__":
    run()
