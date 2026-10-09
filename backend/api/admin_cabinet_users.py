"""Роутер админ-раздела «Пользователи личного кабинета».

Префикс: /api/admin/cabinet-users. Все эндпоинты требуют роль admin
(см. backend.services.auth_api.require_admin).

Это учётки ЛИЧНОГО КАБИНЕТА (таблица user_accounts) — отдельная
система от admin_users (учётки панели управления). Нужны в админке,
чтобы видеть, кто зарегистрировался в кабинете.

Подключение в backend/main.py:

    from backend.api.admin_cabinet_users import router as cabinet_users_router

    app.include_router(cabinet_users_router)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.services.auth_api import require_admin
from backend.services.data_service import get_connection


router = APIRouter(
    prefix="/api/admin/cabinet-users",
    tags=["admin-cabinet-users"],
)

# Роли личного кабинета (см. account_service.ALLOWED_ROLES + admin).
ROLE_LABELS = {
    "client": "Клиент",
    "manager": "Менеджер",
    "admin": "Администратор",
}


def _iso(value):
    return value.isoformat() if value is not None else None


@router.get("")
def admin_list_cabinet_users(auth=Depends(require_admin)):
    """Список учётных записей личного кабинета.

    Дополнительно отдаём число заявок и время последнего входа
    (максимум created_at по сессиям) — для обзора в админке.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.login,
                u.role,
                u.is_active,
                u.created_at,
                (
                    SELECT MAX(s.created_at)
                    FROM account_sessions s
                    WHERE s.account_id = u.id
                ) AS last_login_at,
                (
                    SELECT COUNT(*)
                    FROM client_requests r
                    WHERE r.account_id = u.id
                ) AS requests_count
            FROM user_accounts u
            ORDER BY u.id
            """
        ).fetchall()

    users = [
        {
            "id": row[0],
            "login": row[1],
            "role": row[2],
            "role_label": ROLE_LABELS.get(row[2], row[2]),
            "is_active": row[3],
            "created_at": _iso(row[4]),
            "last_login_at": _iso(row[5]),
            "requests_count": row[6],
        }
        for row in rows
    ]

    return {
        "success": True,
        "users": users,
    }
