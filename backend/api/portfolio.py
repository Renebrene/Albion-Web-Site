"""Публичный экспорт портфеля.

Префикс: /api/portfolio. Авторизация НЕ требуется — портфель можно
собрать и анонимно (он приходит целиком в теле запроса).

    POST /api/portfolio/export?format=xlsx|docx|pdf

Тело::

    {
      "title": "Портфель Albion",
      "items": [
        {
          "surfaceId": 123,
          "city": "Ростов-на-Дону",
          "address": "ул. …",
          "side": "A",
          "type": "ЩИТ",
          "size": "6 × 3 м",
          "months": { "Октябрь": { "price": 15400, "stale": false } }
        }
      ]
    }

Ответ — файл с Content-Disposition: attachment.

Подключение в backend/main.py:

    from backend.api.portfolio import router as portfolio_router

    app.include_router(portfolio_router)
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from backend.services import portfolio_export as svc


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/portfolio",
    tags=["portfolio"],
)


class PortfolioExportPayload(BaseModel):
    """Портфель как есть: структуру описывает фронтенд (usePortfolio)."""

    # Доп. поля сохраняем — они не мешают экспорту.
    model_config = {"extra": "allow"}

    title: str = svc.DEFAULT_TITLE

    # Список позиций. Валидацию (список/непустой/лимит) делает сервис,
    # чтобы ошибки приходили как HTTP 400 с русским текстом, а не 422.
    items: Any = []

    # Необязательно: добавлять ли колонку «Фото». None — не задано в теле,
    # тогда можно взять значение из query-параметра (приоритет у тела).
    with_photos: bool | None = None


def _query_bool(value: Any) -> bool:
    """«1»/«true»/«yes»/«on»/«да» -> True (иначе False)."""
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"1", "true", "yes", "on", "да"}


@router.post("/export")
def export_portfolio(
    payload: PortfolioExportPayload,
    format: str = Query(
        default="xlsx",
        description="Формат файла: xlsx, docx или pdf",
    ),
    with_photos: str | None = Query(
        default=None,
        description="Добавить колонку «Фото» (1/true). Тело запроса приоритетнее.",
    ),
):
    fmt = (format or "").strip().lower()

    if fmt not in svc.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Неподдерживаемый формат: {format!r}. "
                "Допустимо: xlsx, docx, pdf."
            ),
        )

    # Приоритет у тела запроса; query — только если поле не задано.
    if payload.with_photos is None:
        include_photos = _query_bool(with_photos)
    else:
        include_photos = bool(payload.with_photos)

    try:
        content = svc.render(
            payload.items,
            fmt,
            title=payload.title,
            with_photos=include_photos,
        )
    except svc.PortfolioExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except svc.FontUnavailableError as exc:
        logger.error("Экспорт портфеля в PDF невозможен: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — не роняем сервер на кривых данных
        logger.exception("Не удалось сформировать экспорт портфеля (%s)", fmt)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось сформировать файл экспорта: {exc}",
        ) from exc

    filename = svc.build_filename(fmt)

    return Response(
        content=content,
        media_type=svc.CONTENT_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
