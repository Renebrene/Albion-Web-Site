from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash

from backend.services.data_service import get_connection


PASSWORD_HASH = PasswordHash.recommended()

SESSION_LIFETIME = timedelta(days=7)

# Cookie-сессии (TZ 2.1) живут меньше: 8 часов.
COOKIE_SESSION_LIFETIME = timedelta(hours=8)

# Режим авторизации админки. bearer — как было (токен в sessionStorage),
# cookie — HttpOnly-сессия. Переключение: ALBION_AUTH_MODE=cookie.
AUTH_MODE_BEARER = "bearer"
AUTH_MODE_COOKIE = "cookie"


def auth_mode() -> str:
    value = (os.getenv("ALBION_AUTH_MODE") or "").strip().lower()

    return AUTH_MODE_COOKIE if value == AUTH_MODE_COOKIE else AUTH_MODE_BEARER


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
    csrf_token: str | None = None,
    lifetime: timedelta | None = None,
) -> str:
    """
    Создаёт сессию.

    Сам token возвращается вызывающему коду.
    В PostgreSQL сохраняется только SHA-256 хэш token.

    csrf_token — токен для double-submit (заголовок X-CSRF-Token);
    для cookie-режима. lifetime — срок жизни сессии (по умолчанию 7 дней,
    для cookie-режима передаётся 8 часов).
    """
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    csrf = csrf_token or secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + (lifetime or SESSION_LIFETIME)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO admin_sessions
                (
                    user_id,
                    token_hash,
                    expires_at,
                    ip_address,
                    user_agent,
                    csrf_token
                )
            VALUES
                (%s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                token_hash,
                expires_at,
                ip_address,
                user_agent,
                csrf,
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


def get_session_csrf(token: str) -> str | None:
    """CSRF-токен активной сессии (для проверки заголовка X-CSRF-Token)."""
    if not token:
        return None

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT csrf_token
            FROM admin_sessions
            WHERE token_hash = %s
              AND revoked_at IS NULL
              AND expires_at > NOW()
            LIMIT 1
            """,
            (hash_token(token),),
        ).fetchone()

    return row[0] if row and row[0] else None


def touch_session(token: str) -> None:
    """
    Отмечает активность сессии. Обновляем не чаще раза в минуту —
    иначе каждый запрос админки писал бы в таблицу.
    """
    if not token:
        return

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE admin_sessions
            SET last_seen = NOW()
            WHERE token_hash = %s
              AND (
                  last_seen IS NULL
                  OR last_seen < NOW() - INTERVAL '60 seconds'
              )
            """,
            (hash_token(token),),
        )


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


def revoke_user_sessions(user_id: int, keep_token: str | None = None) -> int:
    """Отзывает ВСЕ активные сессии пользователя.

    Нужно после смены пароля, смены роли или отключения аккаунта: иначе уже
    выданные токены (живут до 7 дней) продолжают давать доступ.

    keep_token — токен, который НЕ отзывать (например, текущая сессия
    администратора, меняющего свой же пароль).
    """
    params: list = [int(user_id)]
    keep_clause = ""

    if keep_token:
        keep_clause = " AND token_hash <> %s"
        params.append(hash_token(keep_token))

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            UPDATE admin_sessions
            SET revoked_at = NOW()
            WHERE user_id = %s
              AND revoked_at IS NULL
              {keep_clause}
            RETURNING id
            """,
            tuple(params),
        ).fetchall()

    return len(rows)
