from __future__ import annotations

import os
import secrets

from fastapi import Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.services.audit_service import log_admin_action
from backend.services.auth_service import (
    AUTH_MODE_COOKIE,
    COOKIE_SESSION_LIFETIME,
    auth_mode,
    authenticate,
    create_session,
    get_current_user,
    get_session_csrf,
    revoke_session,
    touch_session,
)

# --- Cookie-сессии админки (TZ 2.1) -----------------------------------------

# HttpOnly: JavaScript не видит токен сессии.
ADMIN_COOKIE = "albion_admin_session"

# Читаемый CSRF-токен: SPA повторяет его в заголовке X-CSRF-Token.
ADMIN_CSRF_COOKIE = "albion_admin_csrf"

# Маркер «сессия есть» — только подсказка для гварда роутера,
# настоящую проверку делает сервер.
ADMIN_AUTH_COOKIE = "albion_admin_auth"

# Методы, для которых cookie-авторизация требует CSRF-заголовок.
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def cookie_secure() -> bool:
    """
    Secure-флаг cookie. По умолчанию включён; для локальной отладки по
    http его можно снять: ALBION_COOKIE_SECURE=false.
    """
    value = (os.getenv("ALBION_COOKIE_SECURE") or "true").strip().lower()

    return value not in ("0", "false", "no")


def set_admin_cookies(response: Response, token: str, csrf: str) -> None:
    max_age = int(COOKIE_SESSION_LIFETIME.total_seconds())
    secure = cookie_secure()

    common = {
        "max_age": max_age,
        "secure": secure,
        "samesite": "lax",
        "path": "/",
    }

    response.set_cookie(ADMIN_COOKIE, token, httponly=True, **common)
    response.set_cookie(ADMIN_CSRF_COOKIE, csrf, httponly=False, **common)
    response.set_cookie(ADMIN_AUTH_COOKIE, "1", httponly=False, **common)


def clear_admin_cookies(response: Response) -> None:
    for name in (ADMIN_COOKIE, ADMIN_CSRF_COOKIE, ADMIN_AUTH_COOKIE):
        response.delete_cookie(name, path="/")


class LoginRequest(BaseModel):
    login: str
    password: str


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
):
    token = None
    via_cookie = False

    if auth_mode() == AUTH_MODE_COOKIE:
        token = request.cookies.get(ADMIN_COOKIE)
        via_cookie = bool(token)

    # Bearer оставлен запасным путём: открытые до переключения вкладки
    # продолжают работать, пока их не перезагрузят.
    if not token:
        token = _extract_token(authorization)

    user = get_current_user(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав",
        )

    # CSRF: cookie браузер отправляет сам, поэтому для изменяющих методов
    # требуем заголовок, который может поставить только наш SPA.
    if via_cookie and request.method.upper() in UNSAFE_METHODS:
        provided = request.headers.get("x-csrf-token") or ""
        expected = get_session_csrf(token) or ""

        if not expected or not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недействительный CSRF-токен",
            )

    touch_session(token)

    return {
        "token": token,
        "user": user,
        "via_cookie": via_cookie,
    }


def login_admin(
    data: LoginRequest,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    user = authenticate(data.login, data.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cookie_mode = auth_mode() == AUTH_MODE_COOKIE

    token = create_session(
        user["id"],
        ip_address=ip_address,
        user_agent=user_agent,
        lifetime=COOKIE_SESSION_LIFETIME if cookie_mode else None,
    )

    log_admin_action(
        user["id"],
        "login",
        "admin_user",
        user["id"],
        ip_address=ip_address,
    )

    return {
        "token": token,
        # CSRF нужен только cookie-режиму: эндпоинт кладёт его в cookie.
        "csrf": get_session_csrf(token) or "",
        "user": user,
    }


def logout_admin(auth):
    revoked = revoke_session(auth["token"])

    return {
        "success": revoked,
    }
