"""Заводит аккаунт администратора в системе личных кабинетов (user_accounts).

Зачем: вход в админку требуется делать «через личный кабинет». Для этого
аккаунт администратора должен существовать и в user_accounts (роль admin),
иначе вход на /api/account/login с логином «админ» не найдёт пользователя.

Таблица admin_users (панель управления) не затрагивается — это отдельная
система авторизации; здесь только ЛК.

Логин/пароль: админ / альбион. Скрипт идемпотентен: при повторном запуске
приводит роль и пароль к ожидаемым значениям.

Запуск:  .venv/bin/python -m backend.migrations.migrate_accounts_admin
"""
from backend.services.account_service import PASSWORD_HASH
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

LOGIN = "админ"
PASSWORD = "альбион"
ROLE = "admin"


def main() -> None:
    print("ALBION · Аккаунт администратора в личном кабинете")

    password_hash = PASSWORD_HASH.hash(PASSWORD)
    # Секретную фразу для админа не задаём отдельно — используем тот же
    # пароль, чтобы восстановление не ломалось на пустом хеше.
    secret_hash = PASSWORD_HASH.hash(PASSWORD)

    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                """
                INSERT INTO user_accounts
                    (login, password_hash, role, secret_phrase_hash, is_active)
                VALUES
                    (%s, %s, %s, %s, TRUE)
                ON CONFLICT (lower(login)) DO UPDATE
                SET password_hash     = EXCLUDED.password_hash,
                    role              = EXCLUDED.role,
                    secret_phrase_hash = EXCLUDED.secret_phrase_hash,
                    is_active         = TRUE,
                    updated_at        = NOW()
                RETURNING id, login, role
                """,
                (LOGIN, password_hash, ROLE, secret_hash),
            ).fetchone()

    print(f"COMMIT: аккаунт ЛК готов — id={row[0]}, логин={row[1]!r}, роль={row[2]!r}")
    print("  • вход в ЛК: /account (логин «админ», пароль «альбион»)")
    print("  • вход в админку: /administration (та же пара)")


if __name__ == "__main__":
    main()
