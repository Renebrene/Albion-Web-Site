"""Создаёт provisioned admin-аккаунт в таблице ``user_accounts``.

Это отдельная система авторизации личного кабинета. Она не создаёт и не
изменяет учётные записи панели ``admin_users``.

Первый запуск требует секреты окружения:

* ``ALBION_ACCOUNT_ADMIN_PASSWORD`` — пароль аккаунта;
* ``ALBION_ACCOUNT_ADMIN_SECRET`` — секретная фраза восстановления.

Повторный запуск безопасен: если логин уже существует, его пароль, секретная
фраза, роль и активность не изменяются. Для намеренной смены credentials нужно
использовать штатную процедуру управления аккаунтами. Для явной ротации
существующего активного admin есть отдельный флаг ``--reset-existing``.

Запуск без изменения существующих credentials:
``.venv/bin/python -m backend.migrations.migrate_accounts_admin``

Явная ротация после backup и проверки секретов:
``.venv/bin/python -m backend.migrations.migrate_accounts_admin --reset-existing``
"""
from __future__ import annotations

import argparse
import os

from backend.services.account_service import PASSWORD_HASH
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

LOGIN = "админ"
ROLE = "admin"
PASSWORD_ENV = "ALBION_ACCOUNT_ADMIN_PASSWORD"
SECRET_ENV = "ALBION_ACCOUNT_ADMIN_SECRET"
MIN_BOOTSTRAP_SECRET_LENGTH = 12


def _required_secret(name: str) -> str:
    value = os.getenv(name, "")
    if not value or not value.strip():
        raise RuntimeError(
            f"Не задан {name}. Укажите секрет в окружении или .env "
            "перед первым запуском миграции."
        )
    if len(value) < MIN_BOOTSTRAP_SECRET_LENGTH:
        raise RuntimeError(
            f"{name} должен содержать минимум "
            f"{MIN_BOOTSTRAP_SECRET_LENGTH} символов."
        )
    return value


def _existing_account(conn):
    return conn.execute(
        """
        SELECT id, login, role, is_active
        FROM user_accounts
        WHERE lower(login) = lower(%s)
        LIMIT 1
        """,
        (LOGIN,),
    ).fetchone()


def _credential_hashes() -> tuple[str, str]:
    password = _required_secret(PASSWORD_ENV)
    secret_phrase = _required_secret(SECRET_ENV)
    return PASSWORD_HASH.hash(password), PASSWORD_HASH.hash(secret_phrase)


def ensure_admin_account(conn, *, reset_existing: bool = False) -> tuple[str, int, str]:
    """Create once, or explicitly rotate an existing active admin account."""
    existing = _existing_account(conn)
    if existing is not None:
        account_id, login, role, is_active = existing
        if role != ROLE or not is_active:
            raise RuntimeError(
                f"Аккаунт {login!r} уже существует, но не является активным "
                "admin. Исправьте его вручную; миграция не повышает права "
                "и не активирует существующие аккаунты автоматически."
            )
        if not reset_existing:
            return "preserved", int(account_id), str(login)
        password_hash, secret_hash = _credential_hashes()
        conn.execute(
            """
            UPDATE user_accounts
            SET password_hash = %s,
                secret_phrase_hash = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (password_hash, secret_hash, account_id),
        )
        return "reset", int(account_id), str(login)

    password_hash, secret_hash = _credential_hashes()
    row = conn.execute(
        """
        INSERT INTO user_accounts
            (login, password_hash, role, secret_phrase_hash, is_active)
        VALUES
            (%s, %s, %s, %s, TRUE)
        RETURNING id, login, role
        """,
        (LOGIN, password_hash, ROLE, secret_hash),
    ).fetchone()
    return "created", int(row[0]), str(row[1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset-existing",
        action="store_true",
        help="Явно заменить credentials существующего активного user_accounts admin",
    )
    args = parser.parse_args()

    print("ALBION · Provisioning admin-аккаунта личного кабинета")

    with get_connection() as conn:
        with conn.transaction():
            action, account_id, login = ensure_admin_account(
                conn,
                reset_existing=args.reset_existing,
            )

    if action == "created":
        print(
            f"COMMIT: аккаунт user_accounts создан — id={account_id}, "
            f"логин={login!r}, роль={ROLE!r}"
        )
        print("  • секреты взяты из окружения и не выводятся")
    elif action == "reset":
        print(
            f"COMMIT: credentials аккаунта user_accounts обновлены — "
            f"id={account_id}, логин={login!r}"
        )
    else:
        print(
            f"OK: аккаунт user_accounts уже существует и сохранён без изменений "
            f"— id={account_id}, логин={login!r}"
        )


if __name__ == "__main__":
    main()
