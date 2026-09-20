from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.services.auth_service import (
    authenticate,
    create_session,
    get_current_user,
    revoke_session,
)


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
    authorization: str | None = Header(default=None),
):
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

    return {
        "token": token,
        "user": user,
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

    token = create_session(
        user["id"],
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {
        "token": token,
        "user": user,
    }


def logout_admin(auth):
    revoked = revoke_session(auth["token"])

    return {
        "success": revoked,
    }
