"""Роутер админ-раздела «Пользователи».

Префикс: /api/admin/users. Все эндпоинты требуют роль admin
(см. backend.services.auth_api.require_admin).

Подключение в backend/main.py:

    from backend.api.admin_users import router as admin_users_router

    app.include_router(admin_users_router)
"""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services.auth_api import require_admin
from backend.services.auth_service import PASSWORD_HASH, revoke_user_sessions
from backend.services.data_service import get_connection


router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-users"],
)

ALLOWED_ROLES = ("admin", "editor")

ROLE_LABELS = {
    "admin": "Администратор",
    "editor": "Редактор",
}


# ---------------------------------------------------------------- models


class UserCreate(BaseModel):
    login: str
    password: str
    name: str
    role: str = "admin"


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    password: str


# ---------------------------------------------------------------- helpers


def _iso(value):
    return value.isoformat() if value is not None else None


def _serialize(row) -> dict:
    (
        user_id,
        login,
        name,
        role,
        is_active,
        created_at,
        last_login_at,
    ) = row

    return {
        "id": user_id,
        "login": login,
        "name": name,
        "role": role,
        "is_active": is_active,
        "created_at": _iso(created_at),
        "last_login_at": _iso(last_login_at),
    }


def _validate_role(role: str) -> str:
    role = (role or "").strip()

    if role not in ALLOWED_ROLES:
        raise ValueError(
            "Недопустимая роль. Допустимо: admin, editor."
        )

    return role


def _validate_password(password: str) -> str:
    if password is None or len(password) < 4:
        raise ValueError(
            "Пароль должен содержать минимум 4 символа."
        )

    return password


# ---------------------------------------------------------------- routes


@router.get("")
def admin_list_users(auth=Depends(require_admin)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                login,
                name,
                role,
                is_active,
                created_at,
                last_login_at
            FROM admin_users
            ORDER BY id
            """
        ).fetchall()

    return {
        "success": True,
        "users": [_serialize(row) for row in rows],
    }


@router.post("")
def admin_create_user(
    payload: UserCreate,
    auth=Depends(require_admin),
):
    login = (payload.login or "").strip()
    name = (payload.name or "").strip()

    if not login:
        raise HTTPException(
            status_code=400,
            detail="Укажите логин.",
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Укажите имя.",
        )

    try:
        role = _validate_role(payload.role)
        password = _validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    password_hash = PASSWORD_HASH.hash(password)

    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM admin_users WHERE login = %s",
                (login,),
            ).fetchone()

            if existing is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Пользователь с таким логином уже существует.",
                )

            row = conn.execute(
                """
                INSERT INTO admin_users
                    (login, password_hash, name, role, is_active)
                VALUES
                    (%s, %s, %s, %s, TRUE)
                RETURNING
                    id,
                    login,
                    name,
                    role,
                    is_active,
                    created_at,
                    last_login_at
                """,
                (login, password_hash, name, role),
            ).fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким логином уже существует.",
        )

    return {
        "success": True,
        "user": _serialize(row),
    }


@router.patch("/{user_id}")
def admin_update_user(
    user_id: int,
    payload: UserUpdate,
    auth=Depends(require_admin),
):
    fields = []
    values = []

    if payload.name is not None:
        name = payload.name.strip()

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Имя не может быть пустым.",
            )

        fields.append("name = %s")
        values.append(name)

    if payload.role is not None:
        try:
            role = _validate_role(payload.role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        fields.append("role = %s")
        values.append(role)

    if payload.is_active is not None:
        fields.append("is_active = %s")
        values.append(bool(payload.is_active))

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM admin_users WHERE id = %s",
            (user_id,),
        ).fetchone()

        if exists is None:
            raise HTTPException(
                status_code=404,
                detail="Пользователь не найден.",
            )

        if not fields:
            row = conn.execute(
                """
                SELECT
                    id,
                    login,
                    name,
                    role,
                    is_active,
                    created_at,
                    last_login_at
                FROM admin_users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()
        else:
            values.append(user_id)
            row = conn.execute(
                f"""
                UPDATE admin_users
                SET {', '.join(fields)}
                WHERE id = %s
                RETURNING
                    id,
                    login,
                    name,
                    role,
                    is_active,
                    created_at,
                    last_login_at
                """,
                tuple(values),
            ).fetchone()

    # При смене роли или отключении аккаунта отзываем выданные сессии.
    if payload.role is not None or payload.is_active is not None:
        revoke_user_sessions(user_id)

    return {
        "success": True,
        "user": _serialize(row),
    }


@router.post("/{user_id}/password")
def admin_change_password(
    user_id: int,
    payload: PasswordChange,
    auth=Depends(require_admin),
):
    try:
        password = _validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    password_hash = PASSWORD_HASH.hash(password)

    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE admin_users
            SET password_hash = %s
            WHERE id = %s
            RETURNING id
            """,
            (password_hash, user_id),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Пользователь не найден.",
        )

    # Отзываем все сессии пользователя; свою текущую оставляем,
    # чтобы администратор не вылетел сразу после смены своего пароля.
    revoke_user_sessions(user_id, keep_token=(auth or {}).get("token"))

    return {"success": True}
