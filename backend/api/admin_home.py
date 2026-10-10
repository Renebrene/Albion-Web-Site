"""Администрирование главной страницы: слайды и их карточки.

    from backend.api.admin_home import router as admin_home_router
    app.include_router(admin_home_router)
"""
from fastapi import APIRouter, Depends, HTTPException

from backend.services.auth_api import require_admin
from backend.services.home_service import (
    create_item,
    create_slide,
    delete_feedback,
    delete_item,
    delete_slide,
    list_feedback,
    list_slides,
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


@router.post("/slides")
def slide_create(payload: dict, auth=Depends(require_admin)):
    slide = create_slide(payload or {})

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
    slide = update_slide(slide_id, payload or {})

    if slide is None:
        raise HTTPException(status_code=404, detail="Слайд не найден")

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
    item = create_item(slide_id, payload or {})

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
    item = update_item(item_id, payload or {})

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
