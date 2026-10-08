from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services import contacts_admin_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/contacts",
    tags=["admin-contacts"],
)


# ---------------------------------------------------------------- models


class SettingsUpdate(BaseModel):
    seo_title: str | None = Field(default=None)
    seo_description: str | None = Field(default=None)
    phone: str | None = Field(default=None)
    email: str | None = Field(default=None)
    additionalEmails: list[str] | None = Field(default=None)


class OfficePayload(BaseModel):
    name: str
    address: str = ""
    phone: str | None = None
    emails: list[str] | None = None
    schedule: str | None = None
    lat: float | None = None
    lng: float | None = None
    media_id: int | None = None
    sort_order: int | None = None
    is_active: bool = True


class DepartmentPayload(BaseModel):
    name: str
    sort_order: int | None = None
    is_active: bool = True


class EmployeePayload(BaseModel):
    department_id: int
    name: str = ""
    position: str = ""
    subdivision: str | None = None
    phone: str | None = None
    personal_phone: str | None = None
    extension: str | None = None
    email: str | None = None
    media_id: int | None = None
    sort_order: int | None = None
    is_active: bool = True


class ReorderOffice(BaseModel):
    id: int
    sort_order: int | None = None


class ReorderEmployee(BaseModel):
    id: int
    sort_order: int | None = None
    department_id: int | None = None


class ReorderDepartment(BaseModel):
    id: int
    sort_order: int | None = None
    employees: list[ReorderEmployee] | None = None


class ReorderPayload(BaseModel):
    offices: list[ReorderOffice] | None = None
    departments: list[ReorderDepartment] | None = None


# ---------------------------------------------------------------- routes


@router.get("")
def admin_get_contacts(auth=Depends(require_admin)):
    try:
        return {"success": True, **svc.get_admin_contacts()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/settings")
def admin_update_settings(
    payload: SettingsUpdate,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_settings(
                seo_title=payload.seo_title,
                seo_description=payload.seo_description,
                phone=payload.phone,
                email=payload.email,
                additional_emails=payload.additionalEmails,
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- offices ---


@router.post("/offices")
def admin_create_office(
    payload: OfficePayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.create_office(**payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/offices/{office_id}")
def admin_update_office(
    office_id: int,
    payload: OfficePayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_office(office_id, **payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/offices/{office_id}")
def admin_delete_office(
    office_id: int,
    auth=Depends(require_admin),
):
    svc.delete_office(office_id)
    return {"success": True}


# --- departments ---


@router.post("/departments")
def admin_create_department(
    payload: DepartmentPayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.create_department(**payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/departments/{department_id}")
def admin_update_department(
    department_id: int,
    payload: DepartmentPayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_department(
                department_id,
                name=payload.name,
                sort_order=payload.sort_order,
                is_active=payload.is_active,
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/departments/{department_id}")
def admin_delete_department(
    department_id: int,
    auth=Depends(require_admin),
):
    svc.delete_department(department_id)
    return {"success": True}


# --- employees ---


@router.post("/employees")
def admin_create_employee(
    payload: EmployeePayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.create_employee(**payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/employees/{employee_id}")
def admin_update_employee(
    employee_id: int,
    payload: EmployeePayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_employee(employee_id, **payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/employees/{employee_id}")
def admin_delete_employee(
    employee_id: int,
    auth=Depends(require_admin),
):
    svc.delete_employee(employee_id)
    return {"success": True}


# --- reorder ---


@router.put("/reorder")
def admin_reorder(
    payload: ReorderPayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.reorder(
                offices=[
                    o.model_dump(exclude_none=True)
                    for o in (payload.offices or [])
                ],
                departments=[
                    d.model_dump(exclude_none=True)
                    for d in (payload.departments or [])
                ],
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))