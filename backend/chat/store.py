from __future__ import annotations

import os
from contextlib import contextmanager
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
    """Bounded TTL store for development / single-worker deployments.

    For several uvicorn workers use ``PostgresChatStore``: this store is
    process-local, so a follow-up request may land in another worker and lose
    ``pending``. The interface is shared by both stores.
    """

    def __init__(
        self,
        ttl_minutes: int = 45,
        *,
        max_sessions: int | None = None,
        max_responses: int = 20,
    ) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_sessions = max_sessions or int(
            os.getenv("ALBION_CHAT_MAX_SESSIONS", "1000")
        )
        self.max_responses = max_responses
        self._sessions: dict[UUID, ChatSession] = {}
        self._locks: dict[UUID, RLock] = {}
        self._lock = RLock()

    def prune(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [
                key
                for key, session in self._sessions.items()
                if session.expires_at <= now
            ]
            for key in expired:
                self._sessions.pop(key, None)
                self._locks.pop(key, None)

    # Backward-compatible private alias used by older call sites.
    _purge = prune

    def _evict_if_needed(self) -> None:
        while len(self._sessions) > self.max_sessions:
            oldest = min(
                self._sessions.values(),
                key=lambda session: session.updated_at,
            )
            self._sessions.pop(oldest.id, None)
            self._locks.pop(oldest.id, None)

    def create(self) -> ChatSession:
        with self._lock:
            self.prune()
            now = datetime.now(timezone.utc)
            session = ChatSession(id=uuid4(), expires_at=now + self.ttl)
            self._sessions[session.id] = session
            self._locks.setdefault(session.id, RLock())
            self._evict_if_needed()
            return session

    def get(self, session_id: UUID) -> ChatSession | None:
        with self._lock:
            self.prune()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.updated_at = datetime.now(timezone.utc)
            session.expires_at = session.updated_at + self.ttl
            return session

    def reset(self, session_id: UUID) -> bool:
        with self._lock:
            self._locks.pop(session_id, None)
            return self._sessions.pop(session_id, None) is not None

    @contextmanager
    def session_lock(self, session_id: UUID):
        """Serialize turns of one session inside this process."""
        with self._lock:
            lock = self._locks.setdefault(session_id, RLock())

        with lock:
            yield

    def save_state(self, session: ChatSession) -> None:
        """In-memory session object is already the state."""
        return None

    def remember_response(
        self,
        session: ChatSession,
        request_id: UUID,
        response: dict[str, Any],
    ) -> None:
        with self._lock:
            session.responses[request_id] = response
            # Keep at most a small bounded idempotency cache.
            while len(session.responses) > self.max_responses:
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
