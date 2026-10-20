"""Настройки интеграции с файлохранилищем Albion.

Секреты не попадают в публичную схему настроек: они хранятся в
``site_settings['storage.albion']`` и возвращаются только в маскированном виде.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import albion_storage
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/integration",
    tags=["admin-integration"],
)


class AlbionConfigPayload(BaseModel):
    mode: str | None = None
    url: str | None = None
    folder_id: str | None = None
    ttl_days: int | None = None
    token: str | None = None


@router.get("/albion")
def get_albion_config(auth=Depends(require_admin)):
    return {
        "success": True,
        **albion_storage.public_config(),
    }


@router.put("/albion")
def save_albion_config(
    payload: AlbionConfigPayload,
    auth=Depends(require_admin),
):
    try:
        config = albion_storage.update_config(
            mode=payload.mode,
            url=payload.url,
            folder_id=payload.folder_id,
            ttl_days=payload.ttl_days,
            token=payload.token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        **config,
    }


@router.post("/albion/verify")
def verify_albion(auth=Depends(require_admin)):
    try:
        result = albion_storage.verify()
    except albion_storage.AlbionError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        **result,
    }
