from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services import settings_service as svc
from backend.services import synonyms_service as synonyms
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/settings",
    tags=["admin-settings"],
)

public_router = APIRouter(
    prefix="/api",
    tags=["settings"],
)


# ---------------------------------------------------------------- models


class SettingsSavePayload(BaseModel):
    settings: dict = Field(default_factory=dict)


class PresetPayload(BaseModel):
    name: str = ""


class SynonymsPayload(BaseModel):
    dictionary: dict = Field(default_factory=dict)


# ---------------------------------------------------------------- admin


@router.get("")
def admin_get_settings(auth=Depends(require_admin)):
    try:
        return {"success": True, **svc.get_settings()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("")
def admin_save_settings(
    payload: SettingsSavePayload,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **svc.save_settings(payload.settings)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/presets")
def admin_create_preset(
    payload: PresetPayload,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **svc.create_preset(payload.name)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/presets/{preset_id}/apply")
def admin_apply_preset(
    preset_id: int,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **svc.apply_preset(preset_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/presets/{preset_id}")
def admin_delete_preset(
    preset_id: int,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **svc.delete_preset(preset_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reset")
def admin_reset_settings(auth=Depends(require_admin)):
    try:
        return {"success": True, **svc.reset_to_defaults()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/synonyms")
def admin_get_synonyms(auth=Depends(require_admin)):
    try:
        return {"success": True, **synonyms.get_synonyms()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/synonyms")
def admin_save_synonyms(
    payload: SynonymsPayload,
    auth=Depends(require_admin),
):
    try:
        return {"success": True, **synonyms.save_synonyms(payload.dictionary)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/synonyms/reset")
def admin_reset_synonyms(auth=Depends(require_admin)):
    try:
        return {"success": True, **synonyms.reset_synonyms()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------- public


@public_router.get("/settings")
def public_get_settings():
    return svc.get_public_settings()
