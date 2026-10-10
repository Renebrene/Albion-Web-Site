"""API дашборда админки: чтение и сохранение порядка/названий плиток."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services import dashboard_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/dashboard",
    tags=["admin-dashboard"],
)


class DashboardLayout(BaseModel):
    # Порядок плиток (пути разделов) и переименования по пути.
    order: list[str] = Field(default_factory=list)
    items: dict[str, dict] = Field(default_factory=dict)


@router.get("")
def admin_get_dashboard_layout(auth=Depends(require_admin)):
    try:
        return {"success": True, **svc.get_dashboard_layout()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("")
def admin_save_dashboard_layout(
    payload: DashboardLayout,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.save_dashboard_layout(payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
