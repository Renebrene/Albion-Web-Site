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
from backend.services.data_service import get_connection


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


@router.get("/traffic-light")
def admin_get_traffic_light(auth=Depends(require_admin)):
    """Получить данные закладки traffic-light в разобранном виде.

    Возвращает:
      {
        "image_url": str | null,
        "text": str,
        "photos": [{"url": str, "label": str}, ...]
      }
    """
    with get_connection() as conn:
        tabs = svc._load_tabs(conn)

    tl_tab = None
    for tab in tabs:
        if tab["kind"] == "traffic-light":
            tl_tab = tab
            break

    if tl_tab is None:
        return {
            "image_url": None,
            "text": "",
            "photos": [],
        }

    return svc._parse_traffic_light_content(tl_tab["content"])


class TrafficLightUpdatePayload(BaseModel):
    image_url: str | None = None
    custom_html: str = ""
    text: str = ""
    photos: list[dict] = Field(default_factory=list)


@router.put("/traffic-light")
def admin_save_traffic_light(
    payload: TrafficLightUpdatePayload,
    auth=Depends(require_admin),
):
    """Обновить данные закладки traffic-light."""
    with get_connection() as conn:
        tabs = svc._load_tabs(conn)

    tl_tab = None
    for tab in tabs:
        if tab["kind"] == "traffic-light":
            tl_tab = tab
            break

    photos = [
        {"url": p.get("url", ""), "label": p.get("label", "")}
        for p in payload.photos
        if p.get("url")
    ]

    if tl_tab is None:
        # Создаём закладку traffic-light если её нет.
        content = svc._build_traffic_light_content({
            "image_url": payload.image_url or "",
            "custom_html": payload.custom_html,
            "text": payload.text,
            "photos": photos,
        })
        conn.execute(
            """
            INSERT INTO info_tabs (title, kind, content, sort_order, is_active)
            VALUES ('СВЕТОФОРНЫЕ ОБЪЕКТЫ', 'traffic-light', %s, 40, TRUE)
            """,
            (content,),
        )
        return {"success": True}

    # Обновляем существующую закладку.
    parsed = svc._parse_traffic_light_content(tl_tab["content"])
    if payload.image_url is not None:
        parsed["image_url"] = payload.image_url
    parsed["custom_html"] = payload.custom_html
    parsed["text"] = payload.text
    parsed["photos"] = photos

    content = svc._build_traffic_light_content(parsed)
    conn.execute(
        """
        UPDATE info_tabs
        SET content = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (content, tl_tab["id"]),
    )

    return {"success": True}
