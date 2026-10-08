from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services import news_admin_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(
    prefix="/api/admin/news",
    tags=["admin-news"],
)


# ---------------------------------------------------------------- models


class NewsPayload(BaseModel):
    title: str = ""
    excerpt: str | None = Field(default=None)
    content: str = ""
    category_id: int | None = Field(default=None)
    published_at: str | None = Field(default=None)
    is_published: bool = False
    is_featured: bool = False
    seo_title: str | None = Field(default=None)
    seo_description: str | None = Field(default=None)
    slug: str | None = Field(default=None)
    media_ids: list[int] | None = Field(default=None)
    cover_media_id: int | None = Field(default=None)


class NewsUpdate(BaseModel):
    title: str | None = Field(default=None)
    excerpt: str | None = Field(default=None)
    content: str | None = Field(default=None)
    category_id: int | None = Field(default=None)
    published_at: str | None = Field(default=None)
    is_published: bool | None = Field(default=None)
    is_featured: bool | None = Field(default=None)
    seo_title: str | None = Field(default=None)
    seo_description: str | None = Field(default=None)
    slug: str | None = Field(default=None)
    media_ids: list[int] | None = Field(default=None)
    cover_media_id: int | None = Field(default=None)


class CategoryPayload(BaseModel):
    name: str = ""
    slug: str | None = Field(default=None)


# ---------------------------------------------------------------- routes


@router.get("")
def admin_get_news(auth=Depends(require_admin)):
    try:
        return {"success": True, **svc.get_admin_news()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("")
def admin_create_news(
    payload: NewsPayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.create_news(**payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{news_id}")
def admin_update_news(
    news_id: int,
    payload: NewsUpdate,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.update_news(
                news_id,
                **payload.model_dump(exclude_unset=True),
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{news_id}")
def admin_delete_news(
    news_id: int,
    auth=Depends(require_admin),
):
    svc.delete_news(news_id)
    return {"success": True}


@router.post("/categories")
def admin_create_category(
    payload: CategoryPayload,
    auth=Depends(require_admin),
):
    try:
        return {
            "success": True,
            **svc.create_category(
                name=payload.name,
                slug=payload.slug,
            ),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
