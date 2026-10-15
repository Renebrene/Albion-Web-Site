"""Заявки с сайта — без личного кабинета.

Личный кабинет скрыт (doc/account-cabinet.md), но заявки нужны: клиент
заполняет форму на сайте (в панели портфеля или на странице «Контакты») и
она попадает в ``client_requests`` с ``account_id = NULL``.

Префиксы:
    POST /api/requests        — принять заявку (без авторизации)
    GET  /api/admin/requests  — список заявок для админки
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services import account_service as svc
from backend.services.auth_api import require_admin


router = APIRouter(prefix="/api", tags=["requests"])

admin_router = APIRouter(
    prefix="/api/admin/requests",
    tags=["admin-requests"],
)

NAME_MAX = 120
PHONE_MAX = 40
COMMENT_MAX = 2000
ITEMS_MAX = 60

# Телефон: цифры, пробелы, скобки, дефис, плюс. Буквы не пропускаем.
_PHONE_RE = re.compile(r"^[+\d][\d\s()\-]{5,%d}$" % (PHONE_MAX - 1))


class RequestItem(BaseModel):
    id: int | None = None
    title: str = ""


class PublicRequestPayload(BaseModel):
    name: str = ""
    phone: str = ""
    comment: str = ""
    items: list[RequestItem] = Field(default_factory=list)


class PublicRequestResult(BaseModel):
    success: bool = True
    request: dict


def _clean(value: str, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


@router.post("/requests", response_model=PublicRequestResult)
def create_public_request(payload: PublicRequestPayload):
    """Принимает заявку с сайта (авторизация не требуется)."""
    name = _clean(payload.name, NAME_MAX)
    phone = _clean(payload.phone, PHONE_MAX)
    comment = _clean(payload.comment, COMMENT_MAX)

    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Укажите имя")

    if not _PHONE_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail="Укажите телефон в формате +7 900 000-00-00",
        )

    items = [
        {
            "id": item.id,
            "title": _clean(item.title, 200),
        }
        for item in payload.items[:ITEMS_MAX]
    ]

    # Заголовок заявки: одна конструкция — её название, несколько — сводка.
    if len(items) == 1 and items[0]["title"]:
        title = items[0]["title"]
    elif items:
        title = f"Подборка из {len(items)} конструкций"
    else:
        title = "Заявка с сайта"

    try:
        created = svc.create_request(
            None,
            title,
            items[0]["id"] if len(items) == 1 else None,
            {
                "source": "site",
                "name": name,
                "phone": phone,
                "comment": comment,
                "items": items,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, "request": created}


@admin_router.get("")
def admin_list_requests(
    limit: int = Query(200, ge=1, le=1000),
    auth=Depends(require_admin),
):
    """Список заявок: и анонимные с сайта, и из личного кабинета."""
    return {
        "success": True,
        "requests": svc.list_all_requests(limit),
    }
