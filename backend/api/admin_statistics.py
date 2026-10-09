"""Админ-раздел «Статистика»: посещаемость страниц и география.

Префикс: /api/admin/statistics. Все эндпоинты требуют роль admin
(см. backend.services.auth_api.require_admin).

Данные обезличены (см. page_visits): IP не хранится, страна вычисляется
в момент визита, уникальность — по необратимому visitor_hash.

Подключение в backend/main.py:

    from backend.api.admin_statistics import router as admin_statistics_router

    app.include_router(admin_statistics_router)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.services.auth_api import require_admin
from backend.services import visit_service as svc


router = APIRouter(
    prefix="/api/admin/statistics",
    tags=["admin-statistics"],
)


@router.get("/summary")
def admin_statistics_summary(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    auth=Depends(require_admin),
):
    return {"success": True, **svc.summary(date_from, date_to)}


@router.get("/daily")
def admin_statistics_daily(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    auth=Depends(require_admin),
):
    return {"success": True, "items": svc.daily(date_from, date_to)}


@router.get("/countries")
def admin_statistics_countries(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    auth=Depends(require_admin),
):
    return {
        "success": True,
        "items": svc.countries(date_from, date_to, limit=limit),
    }


@router.get("/pages")
def admin_statistics_pages(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    auth=Depends(require_admin),
):
    return {
        "success": True,
        "items": svc.pages(date_from, date_to, limit=limit),
    }


@router.get("/visits")
def admin_statistics_visits(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth=Depends(require_admin),
):
    items, total = svc.list_visits(
        date_from, date_to, limit=limit, offset=offset
    )

    return {"success": True, "items": items, "total": total}
