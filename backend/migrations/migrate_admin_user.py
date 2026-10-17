"""Создаёт отдельного администратора панели в таблице ``admin_users``.

Секреты читаются из окружения/.env:

* ALBION_PANEL_ADMIN_LOGIN
* ALBION_PANEL_ADMIN_PASSWORD
* ALBION_PANEL_ADMIN_NAME

Миграция create-only: существующие записи и credentials не изменяются.
``user_accounts`` и legacy migrate_accounts_admin.py намеренно не затрагиваются.

Запуск: .venv/bin/python -m backend.migrations.migrate_admin_user
"""
from __future__ import annotations

import os

from backend.services.auth_service import PASSWORD_HASH
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

LOGIN_ENV = "ALBION_PANEL_ADMIN_LOGIN"
PASSWORD_ENV = "ALBION_PANEL_ADMIN_PASSWORD"
NAME_ENV = "ALBION_PANEL_ADMIN_NAME"
MIN_PASSWORD_LENGTH = 12


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Не задан {name} в окружении или .env")
    return value


def _credentials() -> tuple[str, str, str]:
    login = _required(LOGIN_ENV)
    password = _required(PASSWORD_ENV)
    name = _required(NAME_ENV)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise RuntimeError(
            f"{PASSWORD_ENV} должен содержать минимум "
            f"{MIN_PASSWORD_LENGTH} символов"
        )
    if len(login) < 8:
        raise RuntimeError("Логин панели должен содержать минимум 8 символов")
    return login, password, name


def ensure_admin_user(conn) -> tuple[str, int, str]:
    """Create one panel admin; preserve any existing row unchanged."""
    login, password, name = _credentials()
    existing = conn.execute(
        "SELECT id, login FROM admin_users WHERE login = %s LIMIT 1",
        (login,),
    ).fetchone()
    if existing is not None:
        raise RuntimeError(
            f"Администратор панели с логином {existing[1]!r} уже существует; "
            "изменения credentials запрещены этой create-only миграцией."
        )

    row = conn.execute(
        """
        INSERT INTO admin_users (login, password_hash, name, role, is_active)
        VALUES (%s, %s, %s, 'admin', TRUE)
        RETURNING id, login, role
        """,
        (login, PASSWORD_HASH.hash(password), name),
    ).fetchone()
    return "created", int(row[0]), str(row[1])


def main() -> None:
    print("ALBION · Создание администратора панели admin_users")
    with get_connection() as conn:
        with conn.transaction():
            action, user_id, login = ensure_admin_user(conn)
    print(f"COMMIT: admin_users создан — id={user_id}, логин={login!r}")
    print("  • пароль взят из окружения и не выводится")


if __name__ == "__main__":
    main()
