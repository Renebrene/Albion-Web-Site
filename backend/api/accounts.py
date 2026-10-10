"""Роутер личных кабинетов (ЛК) клиентов и менеджеров.

Префикс: /api/account. Авторизация — Bearer token (см. account_service).

Подключение в backend/main.py:

    from backend.api.accounts import router as account_router

    app.include_router(account_router)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

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


class RequisitesPayload(BaseModel):
    """Реквизиты пользователя ЛК для выгрузки/печати портфеля.

    Все поля — строки, по умолчанию пустые. Длины ограничены, лишние
    ключи отбрасывает сервис (normalize_requisites).
    """

    organization: str = Field(default="", max_length=300)
    inn: str = Field(default="", max_length=300)
    kpp: str = Field(default="", max_length=300)
    address: str = Field(default="", max_length=300)
    phone: str = Field(default="", max_length=300)
    email: str = Field(default="", max_length=300)
    contact: str = Field(default="", max_length=300)


class ChatsPayload(BaseModel):
    # Чаты умного чата: список {number, key, messages}. Структуру описывает
    # фронтенд, бэкенд хранит её как есть (только текстовая история).
    chats: list[Any] = []


class PortfolioPayload(BaseModel):
    # Портфель — список позиций (поверхности + выбранные месяцы).
    # Структуру описывает фронтенд (usePortfolio), бэкенд хранит её как есть.
    items: list[Any] = []
    # Необязательное название портфеля. Если поле не пришло в запросе
    # (exclude_unset), уже сохранённое название не затирается.
    title: str = ""


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


@router.put("/requisites")
def account_save_requisites(
    payload: RequisitesPayload,
    user: dict = Depends(require_account),
):
    """Сохраняет реквизиты аккаунта и возвращает сохранённый объект."""
    saved = svc.save_requisites(user["id"], payload)

    return {
        "success": True,
        "requisites": saved,
    }


@router.get("/chats")
def account_get_chats(user: dict = Depends(require_account)):
    """Сохранённые чаты аккаунта: { "chats": [...], "updated_at": ... }."""
    payload = svc.get_chats(user["id"])

    return {
        "success": True,
        "chats": payload.get("chats", []),
        "updated_at": svc.get_chats_updated_at(user["id"]),
    }


@router.put("/chats")
def account_save_chats(
    payload: ChatsPayload,
    user: dict = Depends(require_account),
):
    """Сохраняет чаты аккаунта (только текстовая история)."""
    saved = svc.save_chats(user["id"], {"chats": payload.chats})

    return {
        "success": True,
        "chats": saved.get("chats", []),
        "updated_at": svc.get_chats_updated_at(user["id"]),
    }


@router.delete("/chats")
def account_clear_chats(user: dict = Depends(require_account)):
    """Очищает сохранённые чаты ЛК (журнал чата не затрагивается)."""
    svc.clear_chats(user["id"])

    return {"success": True, "chats": []}


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
    """Портфель текущего аккаунта: { "title": ..., "items": [...] }."""
    payload = svc.get_portfolio(user["id"])

    return {
        "title": payload.get("title") or "",
        "items": payload.get("items", []),
        "updated_at": svc.get_portfolio_updated_at(user["id"]),
    }


@router.put("/portfolio")
def account_save_portfolio(
    payload: PortfolioPayload,
    user: dict = Depends(require_account),
):
    """Сохраняет портфель аккаунта и возвращает сохранённое.

    Обратная совместимость: если тело содержит только items (без title),
    уже сохранённое название не затирается пустой строкой.
    """
    sent = payload.model_dump(exclude_unset=True)

    if "title" in sent:
        title = (payload.title or "").strip()
    else:
        current = svc.get_portfolio(user["id"])
        title = current.get("title") or ""

    saved = svc.save_portfolio(user["id"], {"title": title, "items": payload.items})

    return {
        "title": saved.get("title") or "",
        "items": saved.get("items", []),
        "updated_at": svc.get_portfolio_updated_at(user["id"]),
    }


@router.delete("/portfolio")
def account_clear_portfolio(user: dict = Depends(require_account)):
    """Очищает сохранённый портфель ЛК (данные конструкций не удаляются)."""
    svc.clear_portfolio(user["id"])

    return {"success": True, "items": []}
