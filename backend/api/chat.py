from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel, ConfigDict, Field

from backend.chat.models import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResetRequest,
    ChatSessionResponse,
)
from backend.chat.postgres_store import PostgresChatStore, persist_enabled
from backend.chat.service import ChatService
from backend.services.data_service import get_connection


router = APIRouter(prefix="/api/chat", tags=["chat"])
_store = PostgresChatStore(get_connection) if persist_enabled() else None
_service = ChatService(store=_store)


@router.post("", response_model=ChatSessionResponse)
def create_chat() -> ChatSessionResponse:
    return ChatSessionResponse(session_id=_service.store.create().id)


@router.post("/message", response_model=ChatMessageResponse)

def send_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    try:
        return _service.message(payload)
    except LookupError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{session_id}/message", response_model=ChatMessageResponse)
def send_session_message(
    session_id: UUID,
    payload: ChatMessageRequest,
) -> ChatMessageResponse:
    payload.session_id = session_id
    return send_message(payload)


@router.post("/reset")
def reset_chat(payload: ChatResetRequest) -> dict[str, bool]:
    if not _service.reset(payload.session_id):
        raise HTTPException(status_code=404, detail="Сессия чата не найдена")
    return {"success": True}
