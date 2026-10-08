"""Роутер админ-раздела «Журнал действий».

Префикс: /api/admin/audit. Авторизация — require_admin.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.services import audit_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/audit",
    tags=["admin-audit"],
)


@router.get("")
def admin_list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    auth=Depends(require_admin),
):
    items, total = svc.list_audit(
        limit=limit,
        offset=offset,
        action=action,
    )

    return {
        "success": True,
        "items": items,
        "total": total,
    }
