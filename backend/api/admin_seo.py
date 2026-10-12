from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend.services import seo_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/seo",
    tags=["admin-seo"],
)

public_router = APIRouter(
    prefix="/api",
    tags=["seo"],
)

# robots.txt и sitemap.xml — без префикса, отдаются с корня сайта.
crawler_router = APIRouter(tags=["seo"])


class SeoPayload(BaseModel):
    site_name: str | None = None
    site_url: str | None = None
    default_title: str | None = None
    default_description: str | None = None
    default_keywords: str | None = None
    og_image: str | None = None
    pages: dict = Field(default_factory=dict)


@router.get("")
def admin_get_seo(auth=Depends(require_admin)):
    return {"success": True, **svc.get_seo()}


@router.put("")
def admin_save_seo(payload: SeoPayload, auth=Depends(require_admin)):
    try:
        result = svc.save_seo(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, **result}


@router.post("/reset")
def admin_reset_seo(auth=Depends(require_admin)):
    return {"success": True, **svc.reset_seo()}


@public_router.get("/seo")
def public_get_seo():
    return svc.get_public_seo()


@crawler_router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return svc.robots_txt()


@crawler_router.get("/sitemap.xml")
def sitemap():
    return PlainTextResponse(
        svc.sitemap_xml(),
        media_type="application/xml",
    )
