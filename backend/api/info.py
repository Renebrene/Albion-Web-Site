"""Закладки страницы «Информация»: публичное чтение и админ-редактор.

    from backend.api.info import (
        router as admin_info_router,
        public_router as public_info_router,
    )
    app.include_router(admin_info_router)
    app.include_router(public_info_router)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.services import info_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/info",
    tags=["admin-info"],
)

public_router = APIRouter(
    prefix="/api",
    tags=["info"],
)


# ---------------------------------------------------------------- models


class TabsSavePayload(BaseModel):
    tabs: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------- public


@public_router.get("/info")
def public_info():
    """Активные закладки страницы «Информация».

    no-store: содержимое меняется из админки, и браузер не должен отдавать
    закэшированный ответ со старым набором городов/описаний.
    """
    return JSONResponse(
        content=svc.get_public_info(),
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------- admin


@router.get("/tabs")
def admin_get_tabs(auth=Depends(require_admin)):
    return {"success": True, **svc.get_admin_info()}


@router.put("/tabs")
def admin_save_tabs(
    payload: TabsSavePayload,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **svc.save_tabs(payload.tabs)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
