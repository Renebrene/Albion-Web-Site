from __future__ import annotations

import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.chat import llm
from backend.chat.models import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatResetRequest,
    ChatSessionResponse,
)
from backend.chat.postgres_store import PostgresChatStore, persist_enabled
from backend.chat.service import ChatService
from backend.chat.store import chat_store
from backend.services import chat_llm_settings as llm_settings
from backend.services.auth_api import require_admin
from backend.services.data_service import get_connection


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])
admin_router = APIRouter(prefix="/api/admin/chat", tags=["admin-chat"])


def _build_store():
    """Pick a session store: postgres (multi-worker), auto or memory.

    ``auto`` tries PostgreSQL (required with several uvicorn workers) and
    falls back to the process-local store only if the DB/schema is
    unavailable, so development without migrations still works.
    """
    mode = os.getenv("ALBION_CHAT_STORE", "").strip().lower()

    if not mode:
        mode = "postgres" if persist_enabled() else "auto"

    if mode == "memory":
        logger.warning(
            "Чат использует in-memory сессии: уточнения не переживут "
            "смену uvicorn-воркера"
        )
        return chat_store

    candidate = PostgresChatStore(get_connection)

    try:
        candidate.healthcheck()
    except Exception:  # noqa: BLE001
        if mode == "postgres":
            raise

        logger.exception(
            "PostgreSQL-хранилище чата недоступно; включён in-memory режим"
        )
        return chat_store

    logger.info("Чат использует PostgreSQL-хранилище сессий")
    return candidate


class _V2WithFallback:
    """Use search v2, but never break chat if the catalog/DB fails."""

    def __init__(self) -> None:
        from backend.search.bridge import AlbionSearchBridge
        from backend.search.v2.service import SearchV2Service

        self.primary = SearchV2Service()
        self.fallback = AlbionSearchBridge()

    def default_year(self) -> int:
        try:
            return self.primary.default_year()
        except Exception:  # noqa: BLE001
            return self.fallback.repository.default_year()

    def search_with_meta(self, query):
        try:
            return self.primary.search_with_meta(query)
        except Exception:  # noqa: BLE001
            logger.exception("Поиск v2 недоступен; откат на v1")
            return self.fallback.search_rich(query), {
                "warnings": ["Поиск v2 недоступен; использован поиск v1"]
            }

    def search_rich(self, query):
        items, _meta = self.search_with_meta(query)
        return items


def _build_bridge():
    """Optional v2 backend; v1 remains the default."""
    version = os.getenv("ALBION_CHAT_SEARCH_VERSION", "1").strip().lower()

    if version in {"2", "v2"}:
        logger.info("Умный чат использует поиск v2 (с откатом на v1)")
        return _V2WithFallback()

    return None


_store = _build_store()
_service = ChatService(bridge=_build_bridge(), store=_store)


@router.post("", response_model=ChatSessionResponse)
def create_chat() -> ChatSessionResponse:
    return ChatSessionResponse(session_id=_service.store.create().id)


@router.post("/message", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    try:
        return _service.message(payload)
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


class ChatLLMStagePayload(BaseModel):
    profile: str
    model: str | None = None


class ChatLLMSelectionPayload(BaseModel):
    extract: ChatLLMStagePayload
    answer: ChatLLMStagePayload


@admin_router.get("/llm")
def chat_llm_info(auth=Depends(require_admin)):
    """Active providers/models and available profiles (no secrets)."""
    return {
        "success": True,
        **llm.describe(),
        **llm_settings.describe(),
    }


@admin_router.put("/llm")
def chat_llm_save(
    payload: ChatLLMSelectionPayload,
    auth=Depends(require_admin),
):
    """Select extraction/answer profiles without editing code."""
    try:
        selection = llm_settings.save_selection(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "success": True,
        "selection": selection,
        **llm_settings.describe(),
    }
