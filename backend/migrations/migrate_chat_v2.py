"""Additive migration for portable smart-chat sessions (v2).

- ``state_version`` lets future changes evolve the stored session payload.
- ``idx_chat_requests_created_at`` supports retention cleanup.

Safe to re-run.
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file

load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                ALTER TABLE chat_sessions
                    ADD COLUMN IF NOT EXISTS state_version BIGINT
                    NOT NULL DEFAULT 1
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_requests_created_at "
                "ON chat_requests (created_at)"
            )


if __name__ == "__main__":
    run()
    print("COMMIT: миграция chat v2 завершена.")
