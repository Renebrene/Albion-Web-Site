"""Роутер личных кабинетов (ЛК) клиентов и менеджеров.

Префикс: /api/account. Авторизация — Bearer token (см. account_service).

Подключение в backend/main.py:

    from backend.api.accounts import router as account_router

    app.include_router(account_router)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.services import account_service as svc


router = APIRouter(
    prefix="/api/account",
    tags=["account"],
)


# ---------------------------------------------------------------- models


class RegisterPayload(BaseModel):
    login: str
    password: str
    secret_phrase: str


class LoginPayload(BaseModel):
    login: str
    password: str


class RecoverPayload(BaseModel):
    login: str
    secret_phrase: str
    new_password: str


class CreateRequestPayload(BaseModel):
    title: str = ""
    # surface_id/payload проверяет сервис — так ошибки приходят как HTTP 400
    # с русским текстом, а не как 422 от pydantic.
    surface_id: Any = None
    payload: Any = None


class PortfolioPayload(BaseModel):
    # Портфель — список позиций (поверхности + выбранные месяцы).
    # Структуру описывает фронтенд (usePortfolio), бэкенд хранит её как есть.
    items: list[Any] = []


# ---------------------------------------------------------------- helpers


def _extract_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def require_account(
    authorization: str | None = Header(default=None),
) -> dict:
    """Dependency: возвращает dict пользователя ЛК либо 401."""
    token = _extract_token(authorization)
    user = svc.get_current_user(token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ---------------------------------------------------------------- endpoints


@router.post("/register")
def account_register(payload: RegisterPayload):
    try:
        result = svc.register(
            payload.login,
            payload.password,
            payload.secret_phrase,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "token": result["token"],
        "user": result["user"],
    }


@router.post("/login")
def account_login(payload: LoginPayload):
    user = svc.authenticate(payload.login, payload.password)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = svc.create_session(user["id"])

    return {
        "success": True,
        "token": token,
        "user": user,
    }


@router.post("/logout")
def account_logout(
    authorization: str | None = Header(default=None),
    user: dict = Depends(require_account),
):
    token = _extract_token(authorization)
    svc.revoke_session(token)

    return {"success": True}


@router.get("/me")
def account_me(user: dict = Depends(require_account)):
    return {
        "success": True,
        "user": user,
        "requests": svc.list_requests(user["id"]),
    }


@router.post("/recover")
def account_recover(payload: RecoverPayload):
    try:
        svc.recover_password(
            payload.login,
            payload.secret_phrase,
            payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"success": True}


@router.get("/requests")
def account_requests(user: dict = Depends(require_account)):
    return {
        "success": True,
        "requests": svc.list_requests(user["id"]),
    }


@router.post("/requests")
def account_create_request(
    payload: CreateRequestPayload,
    user: dict = Depends(require_account),
):
    try:
        request = svc.create_request(
            user["id"],
            payload.title,
            payload.surface_id,
            payload.payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "request": request,
    }


@router.get("/portfolio")
def account_get_portfolio(user: dict = Depends(require_account)):
    """Портфель текущего аккаунта: { "items": [...] }."""
    payload = svc.get_portfolio(user["id"])

    return {"items": payload.get("items", [])}


@router.put("/portfolio")
def account_save_portfolio(
    payload: PortfolioPayload,
    user: dict = Depends(require_account),
):
    """Сохраняет портфель аккаунта и возвращает сохранённое."""
    saved = svc.save_portfolio(user["id"], {"items": payload.items})

    return {"items": saved.get("items", [])}
