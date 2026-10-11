"""Админ-эндпоинты медиатеки конструкций.

Медиатека конструкций — каталог превью. Здесь можно переопределить фото
конструкции: новая картинка сохраняется во временный каталог превью
(``storage/constructions/overrides``) и подхватывается на всём сайте, но
действует только до следующего обновления базы (следующего импорта).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from backend.services import construction_overrides as svc
from backend.services.auth_api import require_admin
from backend.services.media_service import MAX_INPUT_FILE_SIZE, MediaValidationError
from backend.services.upload_limits import UploadTooLargeError, read_upload_limited


router = APIRouter(
    prefix="/api/admin/constructions",
    tags=["admin-construction-media"],
)


class FieldsPayload(BaseModel):
    surface_hash: str
    fields: dict = {}


@router.post("/media/override")
async def set_media_override(
    surface_hash: str = Form(...),
    media_type: str = Form(default="photo"),
    file: UploadFile | None = File(default=None),
    source_url: str | None = Form(default=None),
    auth=Depends(require_admin),
):
    """Переопределяет фото конструкции (файлом или копией из каталога превью)."""
    surface_hash = surface_hash.strip()

    if not surface_hash:
        raise HTTPException(status_code=400, detail="surface_hash обязателен")

    if media_type not in ("photo", "map"):
        raise HTTPException(status_code=400, detail="media_type: photo или map")

    try:
        if file is not None:
            data = read_upload_limited(file, MAX_INPUT_FILE_SIZE)
            result = svc.save_override(
                surface_hash,
                media_type,
                data,
                file.filename,
            )
        elif source_url:
            result = svc.save_override_from_url(
                surface_hash,
                media_type,
                source_url,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Нужен файл или source_url",
            )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except MediaValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"success": True, "override": result}


@router.delete("/media/override")
def clear_media_override(
    surface_hash: str = Query(...),
    media_type: str = Query(default="photo"),
    auth=Depends(require_admin),
):
    """Снимает переопределение фото конструкции."""
    svc.clear_override(surface_hash, media_type)

    return {"success": True}


@router.get("/media/overrides")
def list_media_overrides(auth=Depends(require_admin)):
    """Активные переопределения фото (для админки)."""
    return {"success": True, "overrides": svc.list_overrides()}


@router.post("/media/fields")
def set_fields_override(
    payload: FieldsPayload,
    auth=Depends(require_admin),
):
    """Временное переопределение основных полей конструкции."""
    surface_hash = payload.surface_hash.strip()

    if not surface_hash:
        raise HTTPException(status_code=400, detail="surface_hash обязателен")

    return {
        "success": True,
        "override": svc.save_fields(surface_hash, payload.fields),
    }


@router.delete("/media/fields")
def clear_fields_override(
    surface_hash: str = Query(...),
    auth=Depends(require_admin),
):
    """Снимает переопределение полей конструкции."""
    svc.clear_fields(surface_hash)

    return {"success": True}
