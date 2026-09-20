from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash

from backend.services.data_service import get_connection


PASSWORD_HASH = PasswordHash.recommended()

SESSION_LIFETIME = timedelta(days=7)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate(login: str, password: str):
    """
    Проверяет логин и пароль активного администратора.

    Возвращает данные пользователя либо None.
    """
    login = login.strip()

    if not login or not password:
        return None

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                id,
                login,
                password_hash,
                name,
                role,
                is_active
            FROM admin_users
            WHERE login = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (login,),
        ).fetchone()

    if user is None:
        return None

    user_id, user_login, stored_hash, name, role, is_active = user

    try:
        valid = PASSWORD_HASH.verify(password, stored_hash)
    except Exception:
        valid = False

    if not valid:
        return None

    return {
        "id": user_id,
        "login": user_login,
        "name": name,
        "role": role,
        "is_active": is_active,
    }


def create_session(
    user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> str:
    """
    Создаёт сессию.

    Сам token возвращается вызывающему коду.
    В PostgreSQL сохраняется только SHA-256 хэш token.
    """
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO admin_sessions
                (
                    user_id,
                    token_hash,
                    expires_at,
                    ip_address,
                    user_agent
                )
            VALUES
                (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                token_hash,
                expires_at,
                ip_address,
                user_agent,
            ),
        )

        conn.execute(
            """
            UPDATE admin_users
            SET last_login_at = NOW()
            WHERE id = %s
            """,
            (user_id,),
        )

    return token


def get_current_user(token: str):
    """
    Проверяет session token и возвращает активного пользователя.
    """
    if not token:
        return None

    token_hash = hash_token(token)

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT
                u.id,
                u.login,
                u.name,
                u.role,
                u.is_active
            FROM admin_sessions s
            JOIN admin_users u
              ON u.id = s.user_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
              AND u.is_active = TRUE
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

    if user is None:
        return None

    user_id, login, name, role, is_active = user

    return {
        "id": user_id,
        "login": login,
        "name": name,
        "role": role,
        "is_active": is_active,
    }


def revoke_session(token: str) -> bool:
    """
    Отзывает текущую сессию.
    """
    if not token:
        return False

    token_hash = hash_token(token)

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE admin_sessions
            SET revoked_at = NOW()
            WHERE token_hash = %s
              AND revoked_at IS NULL
            RETURNING id
            """,
            (token_hash,),
        ).fetchone()

    return result is not None
