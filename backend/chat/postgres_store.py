from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from engine.query.query import SearchQuery
from engine.search.postgresql_chat_engine import PendingSearchQuery

from backend.chat.store import ChatSession


logger = logging.getLogger(__name__)

# pg_advisory_lock принимает bigint; у UUID берём младшие 63 бита.
_ADVISORY_MASK = (1 << 63) - 1


class PostgresChatStore:
    """PostgreSQL-backed session store for multi-worker deployments.

    The process-local ``ChatStore`` cannot share ``pending`` between uvicorn
    workers: a follow-up request may hit another process and the clarification
    disappears. This store keeps sessions in ``chat_sessions`` so every worker
    sees the same state.
    """

    def __init__(self, connection_factory, ttl_minutes: int = 45):
        self.connection_factory = connection_factory
        self.ttl = timedelta(minutes=ttl_minutes)
        self._last_prune = 0.0
        self._prune_interval = float(
            os.getenv("ALBION_CHAT_PRUNE_INTERVAL", "300")
        )

    def healthcheck(self) -> None:
        """Fail fast when the migration has not been applied."""
        with self.connection_factory() as conn:
            conn.execute("SELECT 1 FROM chat_sessions LIMIT 1")
            conn.commit()

    def prune(self, force: bool = False) -> None:
        now = time.monotonic()

        if not force and (now - self._last_prune) < self._prune_interval:
            return

        self._last_prune = now
        retention_days = int(os.getenv("ALBION_CHAT_REQUEST_RETENTION_DAYS", "7"))

        try:
            with self.connection_factory() as conn:
                conn.execute(
                    "DELETE FROM chat_sessions WHERE expires_at < NOW()"
                )
                conn.execute(
                    """
                    DELETE FROM chat_requests
                    WHERE created_at < NOW() - (%s || ' days')::interval
                    """,
                    (retention_days,),
                )
                conn.commit()
        except Exception:  # noqa: BLE001 — очистка не должна ломать чат
            logger.exception("Не удалось очистить истёкшие сессии чата")

    def _row_to_session(self, row) -> ChatSession:
        pending = _pending_from_json(row[1])
        return ChatSession(
            id=row[0],
            expires_at=row[5],
            pending=pending,
            last_result_ids=list(row[2] or []),
            updated_at=row[4],
        )

    def create(self) -> ChatSession:
        now = datetime.now(timezone.utc)
        session = ChatSession(id=uuid4(), expires_at=now + self.ttl)

        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (id, expires_at)
                VALUES (%s, %s)
                """,
                (session.id, session.expires_at),
            )
            conn.commit()

        self.prune()
        return session

    def get(self, session_id: UUID) -> ChatSession | None:
        now = datetime.now(timezone.utc)

        with self.connection_factory() as conn:
            row = conn.execute(
                """
                SELECT id, pending_query, last_result_ids,
                       created_at, updated_at, expires_at
                FROM chat_sessions
                WHERE id = %s AND expires_at > %s
                """,
                (session_id, now),
            ).fetchone()

            if row is None:
                conn.rollback()
                return None

            expires_at = now + self.ttl
            conn.execute(
                """
                UPDATE chat_sessions
                SET updated_at = %s, expires_at = %s
                WHERE id = %s
                """,
                (now, expires_at, session_id),
            )
            conn.commit()

        session = self._row_to_session(row)
        session.expires_at = expires_at
        return session

    def reset(self, session_id: UUID) -> bool:
        with self.connection_factory() as conn:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE id = %s",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    @contextmanager
    def session_lock(self, session_id: UUID):
        """Cross-worker advisory lock for one chat session."""
        key = session_id.int & _ADVISORY_MASK

        with self.connection_factory() as conn:
            conn.execute("SELECT pg_advisory_lock(%s)", (key,))

            try:
                yield
            finally:
                try:
                    conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
                    conn.commit()
                except Exception:  # noqa: BLE001
                    logger.exception("Не удалось снять advisory lock чата")

    def save_state(self, session: ChatSession) -> None:
        """Persist pending/last result ids after EVERY turn.

        Previously this happened only inside ``remember_response``, i.e. only
        when the client sent ``request_id``. A follow-up without it lost the
        clarification state.
        """
        with self.connection_factory() as conn:
            conn.execute(
                """
                UPDATE chat_sessions
                SET pending_query = %s,
                    last_result_ids = %s,
                    updated_at = %s,
                    expires_at = %s
                WHERE id = %s
                """,
                (
                    Jsonb(_pending_to_json(session.pending)),
                    Jsonb(session.last_result_ids),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc) + self.ttl,
                    session.id,
                ),
            )
            conn.commit()

    def response_for(self, session: ChatSession, request_id: UUID | None):
        if request_id is None:
            return None

        with self.connection_factory() as conn:
            row = conn.execute(
                """
                SELECT response
                FROM chat_requests
                WHERE session_id = %s AND request_id = %s
                """,
                (session.id, request_id),
            ).fetchone()
            return row[0] if row else None

    def remember_response(self, session, request_id, response):
        with self.connection_factory() as conn:
            conn.execute(
                """
                INSERT INTO chat_requests (session_id, request_id, response)
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id, request_id)
                DO UPDATE SET response = EXCLUDED.response
                """,
                (session.id, request_id, Jsonb(response)),
            )
            conn.commit()


def _pending_to_json(pending: Any) -> dict[str, Any] | None:
    if pending is None:
        return None

    query = pending.query
    return {
        "clarification_type": pending.clarification_type,
        "clarification_text": pending.clarification_text,
        "query": {
            key: getattr(query, key)
            for key in (
                "city", "district", "address", "media_type", "size", "year",
                "month", "months", "period_mode", "availability",
                "load_threshold", "max_load", "min_price", "max_price",
                "sort_by", "limit",
            )
        },
    }


def _pending_from_json(data: dict[str, Any] | None):
    if not data:
        return None

    query = SearchQuery(**data["query"])
    return PendingSearchQuery(
        query=query,
        clarification_type=data.get("clarification_type", "media_type"),
        clarification_text=data.get("clarification_text", ""),
    )


def persist_enabled() -> bool:
    return os.getenv("ALBION_CHAT_PERSIST", "false").lower() in {
        "1", "true", "yes", "on"
    }
