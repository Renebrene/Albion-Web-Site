"""Общие фикстуры и хелперы для интеграционных тестов.

Тесты, которым нужна PostgreSQL, помечаются skip, если база недоступна:
это позволяет гонять набор и на машине без БД.
"""

from __future__ import annotations

import pytest


def db_available() -> bool:
    try:
        from backend.services.data_service import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not db_available(), reason="нет подключения к PostgreSQL"
)
