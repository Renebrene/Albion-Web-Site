"""Create the optional PostgreSQL storage for smart-chat sessions.

The current service uses a bounded process-local store so the demo works
without a migration. This additive migration is ready for multi-worker
persistence and keeps only normalized state/idempotency responses.
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file

load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY,
                    pending_query JSONB,
                    last_result_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_requests (
                    session_id UUID NOT NULL
                        REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    request_id UUID NOT NULL,
                    response JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (session_id, request_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires_at "
                "ON chat_sessions (expires_at)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON chat_sessions TO albion_app"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON chat_requests TO albion_app"
            )


if __name__ == "__main__":
    run()
    print("COMMIT: миграция chat_sessions/chat_requests завершена.")
