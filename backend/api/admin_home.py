"""Администрирование главной страницы: слайды и их карточки.

    from backend.api.admin_home import router as admin_home_router
    app.include_router(admin_home_router)
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from backend.services.auth_api import require_admin
from backend.services.home_service import (
    BANNER_CODE_CSP,
    create_button,
    create_item,
    create_slide,
    delete_button,
    delete_feedback,
    delete_item,
    clear_preview_code,
    delete_slide,
    get_default_banner_code,
    get_item,
    get_preview_code,
    get_slide_code,
    list_feedback,
    list_slides,
    update_button,
    update_item,
    update_slide,
)
from backend.services.home_geo_service import (
    create_attraction,
    create_location,
    create_photo,
    delete_attraction,
    delete_location,
    delete_photo,
    get_admin_geo,
    update_attraction,
    update_location,
    update_settings,
)


router = APIRouter(
    prefix="/api/admin/home",
    tags=["admin-home"],
)


@router.get("/slides")
def slides(auth=Depends(require_admin)):
    return {
        "success": True,
        "slides": list_slides(),
    }


@router.get("/banner-default")
def banner_default(auth=Depends(require_admin)):
    """Эталонный HTML-код баннера — для кнопки «Сбросить к стандартному»."""
    return {
        "success": True,
        "code": get_default_banner_code(),
    }


@router.get("/slides/{slide_id}/code", include_in_schema=False)
def slide_code_preview(
    slide_id: int,
    auth=Depends(require_admin),
):
    """Предпросмотр сохранённого кода баннера (в том числе у скрытого слайда)."""
    # Живой предпросмотр: если редактор записал временный код — берём его,
    # иначе показываем последний сохранённый в БД.
    code = get_preview_code(slide_id)
    if code is None:
        code = get_slide_code(slide_id, require_active=False)

    if code is None:
        raise HTTPException(status_code=404, detail="Код баннера не найден")

    return HTMLResponse(
        content=code,
        headers={
            "Content-Security-Policy": BANNER_CODE_CSP,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.put("/slides/{slide_id}/preview", include_in_schema=False)
def slide_preview_save(
    slide_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    """Временный код для живого предпросмотра (не сохраняется в слайд).

    Редактор админки обновляет предпросмотр по мере ввода, не дожидаясь
    нажатия «Сохранить». Значение лежит в памяти processesа и живёт до
    перезапуска/следующей записи; в БД попадает только по «Сохранить».
    """
    from backend.services.home_service import set_preview_code

    set_preview_code(slide_id, str(payload.get("code") or ""))
    return {"success": True}


@router.post("/slides")
def slide_create(payload: dict, auth=Depends(require_admin)):
    try:
        slide = create_slide(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "slide": slide,
        "slides": list_slides(),
    }


@router.patch("/slides/{slide_id}")
def slide_update(
    slide_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    try:
        slide = update_slide(slide_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if slide is None:
        raise HTTPException(status_code=404, detail="Слайд не найден")

    # После сохранения предпросмотр должен показывать код из БД.
    clear_preview_code(slide_id)

    return {
        "success": True,
        "slide": slide,
        "slides": list_slides(),
    }


@router.delete("/slides/{slide_id}")
def slide_delete(slide_id: int, auth=Depends(require_admin)):
    if not delete_slide(slide_id):
        raise HTTPException(status_code=404, detail="Слайд не найден")

    return {
        "success": True,
        "slides": list_slides(),
    }


@router.post("/slides/{slide_id}/items")
def item_create(
    slide_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    try:
        item = create_item(slide_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=404, detail="Слайд не найден")

    return {
        "success": True,
        "item": item,
        "slides": list_slides(),
    }


@router.patch("/items/{item_id}")
def item_update(
    item_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    try:
        item = update_item(item_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    return {
        "success": True,
        "item": item,
        "slides": list_slides(),
    }


@router.delete("/items/{item_id}")
def item_delete(item_id: int, auth=Depends(require_admin)):
    if not delete_item(item_id):
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    return {
        "success": True,
        "slides": list_slides(),
    }


# ---------------------------------------------------------------- кнопки


@router.post("/slides/{slide_id}/buttons")
def slide_button_create(
    slide_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    try:
        button = create_button(slide_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "button": button,
        "slides": list_slides(),
    }


@router.post("/items/{item_id}/buttons")
def item_button_create(
    item_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    item = get_item(item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Карточка не найдена")

    try:
        button = create_button(item["slide_id"], payload or {}, item_id=item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "button": button,
        "slides": list_slides(),
    }


@router.patch("/buttons/{button_id}")
def button_update(
    button_id: int,
    payload: dict,
    auth=Depends(require_admin),
):
    try:
        button = update_button(button_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if button is None:
        raise HTTPException(status_code=404, detail="Кнопка не найдена")

    return {
        "success": True,
        "button": button,
        "slides": list_slides(),
    }


@router.delete("/buttons/{button_id}")
def button_delete(button_id: int, auth=Depends(require_admin)):
    if not delete_button(button_id):
        raise HTTPException(status_code=404, detail="Кнопка не найдена")

    return {
        "success": True,
        "slides": list_slides(),
    }


@router.get("/feedback")
def feedback_list(auth=Depends(require_admin)):
    return {
        "success": True,
        "feedback": list_feedback(),
    }


@router.delete("/feedback/{feedback_id}")
def feedback_delete(feedback_id: int, auth=Depends(require_admin)):
    if not delete_feedback(feedback_id):
        raise HTTPException(status_code=404, detail="Сообщение не найдено")

    return {
        "success": True,
        "feedback": list_feedback(),
    }


# ---------------------------------------------------------------- geo-контент


@router.get("/geo")
def geo_content(auth=Depends(require_admin)):
    return {"success": True, **get_admin_geo()}


@router.patch("/geo/settings")
def geo_settings(payload: dict, auth=Depends(require_admin)):
    return {"success": True, "settings": update_settings(payload or {})}


@router.post("/geo/locations")
def geo_location_create(payload: dict, auth=Depends(require_admin)):
    try:
        result = create_location(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "location": result, **get_admin_geo()}


@router.patch("/geo/locations/{location_id}")
def geo_location_update(location_id: int, payload: dict, auth=Depends(require_admin)):
    try:
        update_location(location_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **get_admin_geo()}


@router.delete("/geo/locations/{location_id}")
def geo_location_delete(location_id: int, auth=Depends(require_admin)):
    try:
        delete_location(location_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **get_admin_geo()}


@router.post("/geo/attractions")
def geo_attraction_create(payload: dict, auth=Depends(require_admin)):
    try:
        result = create_attraction(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "attraction": result, **get_admin_geo()}


@router.patch("/geo/attractions/{attraction_id}")
def geo_attraction_update(attraction_id: int, payload: dict, auth=Depends(require_admin)):
    try:
        update_attraction(attraction_id, payload or {})
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **get_admin_geo()}


@router.delete("/geo/attractions/{attraction_id}")
def geo_attraction_delete(attraction_id: int, auth=Depends(require_admin)):
    try:
        delete_attraction(attraction_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **get_admin_geo()}


@router.post("/geo/attractions/{attraction_id}/photos")
def geo_photo_create(attraction_id: int, payload: dict, auth=Depends(require_admin)):
    try:
        result = create_photo(attraction_id, payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "photo": result, **get_admin_geo()}


@router.delete("/geo/photos/{photo_id}")
def geo_photo_delete(photo_id: int, auth=Depends(require_admin)):
    try:
        delete_photo(photo_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, **get_admin_geo()}
