"""Advisory-lock обновления базы: межпроцессная защита от двойного запуска.

Проверяет, что пока один «воркер» держит блокировку обновления, другой
(отдельное соединение) её не получает.
"""

from __future__ import annotations

from backend.services import update_service as us
from backend.services.data_service import get_raw_connection
from backend.tests.conftest import requires_db


def _try_lock_on_new_connection() -> bool:
    """Пытается взять тот же advisory-lock на отдельном соединении."""
    conn = get_raw_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_try_advisory_lock(%s)", (us._UPDATE_LOCK_ID,)
            )
            return bool(cur.fetchone()[0])
    finally:
        conn.close()


@requires_db
def test_update_lock_is_exclusive_across_connections():
    assert us._acquire_update_lock() is True

    try:
        # Другое соединение = другой воркер: блокировку не получит.
        assert _try_lock_on_new_connection() is False
    finally:
        us._release_update_lock()

    # После освобождения блокировку можно взять снова.
    assert _try_lock_on_new_connection() is True


@requires_db
def test_update_lock_is_idempotent_within_process():
    """Повторный вызов в том же процессе не считает себя «занятым»."""
    assert us._acquire_update_lock() is True

    try:
        assert us._acquire_update_lock() is True
    finally:
        us._release_update_lock()
