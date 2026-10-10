from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import UUID, uuid4


@dataclass
class ChatSession:
    id: UUID
    expires_at: datetime
    pending: Any = None
    last_result_ids: list[int] = field(default_factory=list)
    responses: dict[UUID, dict[str, Any]] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ChatStore:
    """Small TTL store for the public demo.

    The store deliberately keeps only normalized pending state and bounded
    idempotency responses. It can later be replaced by a PostgreSQL store
    without changing the chat service contract.
    """

    def __init__(self, ttl_minutes: int = 45) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[UUID, ChatSession] = {}
        self._lock = RLock()

    def _purge(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            key
            for key, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for key in expired:
            self._sessions.pop(key, None)

    def create(self) -> ChatSession:
        with self._lock:
            self._purge()
            now = datetime.now(timezone.utc)
            session = ChatSession(id=uuid4(), expires_at=now + self.ttl)
            self._sessions[session.id] = session
            return session

    def get(self, session_id: UUID) -> ChatSession | None:
        with self._lock:
            self._purge()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.updated_at = datetime.now(timezone.utc)
            session.expires_at = session.updated_at + self.ttl
            return session

    def reset(self, session_id: UUID) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def remember_response(
        self,
        session: ChatSession,
        request_id: UUID,
        response: dict[str, Any],
    ) -> None:
        with self._lock:
            session.responses[request_id] = response
            # Keep at most a small bounded idempotency cache.
            while len(session.responses) > 20:
                session.responses.pop(next(iter(session.responses)))

    def response_for(
        self,
        session: ChatSession,
        request_id: UUID | None,
    ) -> dict[str, Any] | None:
        if request_id is None:
            return None
        with self._lock:
            return session.responses.get(request_id)


chat_store = ChatStore()
