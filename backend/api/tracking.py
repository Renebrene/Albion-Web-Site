"""Публичный эндпоинт трекинга визитов.

Префикс: /api. Специально ВНЕ /api/admin/ — иначе на него навесился бы
no-store middleware, а require_admin здесь не нужен: трекинг публичный.

Запрос шлёт браузер (sendBeacon) при клиентской навигации SPA.
IP посетителя определяется здесь (request), но в БД не сохраняется —
см. backend/services/visit_service.record_visit.

Подключение в backend/main.py:

    from backend.api.tracking import router as tracking_router

    app.include_router(tracking_router)
"""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.services.visitor import client_ip
from backend.services.visit_service import record_visit


router = APIRouter(
    prefix="/api",
    tags=["tracking"],
)

MAX_PATH_LENGTH = 512


class TrackPayload(BaseModel):
    path: str = Field(default="", max_length=MAX_PATH_LENGTH)
    referrer: str | None = Field(default=None, max_length=MAX_PATH_LENGTH)


def _clean_path(path: str) -> str:
    """Путь страницы: только внутренний маршрут, без API и мусора."""
    value = (path or "").strip()

    if not value.startswith("/"):
        return ""

    # Служебные маршруты трекать не нужно.
    if value.startswith("/api") or value.startswith("/storage"):
        return ""

    return value[:MAX_PATH_LENGTH]


def _referrer_host(referrer: str | None) -> str | None:
    """Оставляем только схему+хост внешнего источника (без пути и query)."""
    value = (referrer or "").strip()

    if not value:
        return None

    try:
        parts = urlsplit(value)
    except ValueError:
        return None

    if not parts.scheme or not parts.netloc:
        return None

    return f"{parts.scheme}://{parts.netloc}"


@router.post("/track")
def track_visit(payload: TrackPayload, request: Request):
    """Фиксирует визит. Всегда отвечает success, даже если запись упала."""
    path = _clean_path(payload.path)

    if path:
        record_visit(
            path=path,
            referrer=_referrer_host(payload.referrer),
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

    return {"success": True}
