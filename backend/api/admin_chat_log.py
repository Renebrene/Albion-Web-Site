"""Админ-раздел «Журнал умного чата».

Отдаёт текстовые пары «вопрос → ответ» с датой-временем для изучения
запросов пользователей. Позволяет отмечать записи и выгружать их в JSONL —
формат, удобный для анализа и дообучения нейросетей.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.services.auth_api import require_admin
from backend.services.chat_log_service import (
    export_turns,
    list_turns,
    set_selection,
)


router = APIRouter(
    prefix="/api/admin/chat-log",
    tags=["admin-chat-log"],
)


class SelectionPayload(BaseModel):
    """Отметка «выбрано» для набора записей журнала."""

    ids: list[int] = Field(default_factory=list, max_length=1000)
    selected: bool = True


@router.get("")
def chat_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    selected_only: bool = Query(default=False),
    auth=Depends(require_admin),
):
    result = list_turns(
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        query=q,
        selected_only=selected_only,
    )

    return {"success": True, **result}


@router.post("/selection")
def chat_log_selection(
    payload: SelectionPayload,
    auth=Depends(require_admin),
):
    """Ставит или снимает отметку «выбрано» у переданных записей."""
    updated = set_selection(ids=payload.ids, selected=payload.selected)

    return {"success": True, "updated": updated}


@router.get("/export")
def chat_log_export(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    selected_only: bool = Query(default=False),
    auth=Depends(require_admin),
):
    """Выгрузка журнала в JSONL (по строке JSON на запись).

    Формат JSONL с полем ``messages`` ({role, content}) — стандартный для
    анализа и дообучения нейросетей; метаданные (id, дата, ключ чата)
    сохранены рядом.
    """
    rows = export_turns(
        date_from=date_from,
        date_to=date_to,
        query=q,
        selected_only=selected_only,
    )

    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    body = "\n".join(lines)
    if body:
        body += "\n"

    return Response(
        content=body,
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="chat-log.jsonl"',
        },
    )
