from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services import site_menu_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/site",
    tags=["admin-site"],
)


class MenuItem(BaseModel):
    key: str | None = None
    label: str
    url: str = "#"
    sort_order: int | None = None
    is_active: bool = True


class MenuUpdatePayload(BaseModel):
    main: list[MenuItem] | None = Field(default=None)
    footer: list[MenuItem] | None = Field(default=None)


@router.get("/menu")
def admin_get_menu(auth=Depends(require_admin)):
    return {"success": True, **svc.get_admin_menu()}


@router.put("/menu")
def admin_update_menu(
    payload: MenuUpdatePayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_menu_items(
                main=[i.model_dump() for i in (payload.main or [])],
                footer=[i.model_dump() for i in (payload.footer or [])],
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))