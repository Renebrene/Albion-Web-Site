"""Планировщик авто-бекапа сайта.

Подтверждает, что advisory-блокировка PostgreSQL не даёт нескольким
worker'ам uvicorn создать авто-бекап дважды: параллельный вызов
ensure_weekly_backup() приводит ровно к одному созданию бекапа.
"""

from __future__ import annotations

import threading

import pytest

from backend.services import site_backup_service as svc


def _db_available() -> bool:
    try:
        from backend.services.data_service import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _db_available(), reason="нет подключения к PostgreSQL")
def test_ensure_weekly_backup_creates_once_under_concurrency(monkeypatch):
    calls: list[str] = []
    started = threading.Barrier(2, timeout=10)

    def fake_create_backup(kind: str = "manual") -> dict:
        calls.append(kind)
        # Держим advisory-lock достаточно долго, чтобы второй поток успел
        # попытаться его взять, пока первый ещё работает.
        threading.Event().wait(0.5)
        return {"kind": kind}

    # Нет прошлых бекапов — проверка «моложе 7 дней» не срабатывает,
    # и поток доходит до создания бекапа.
    monkeypatch.setattr(svc, "_backup_dirs", lambda: [])
    monkeypatch.setattr(svc, "create_backup", fake_create_backup)

    results: list[bool] = []

    def worker() -> None:
        started.wait()
        results.append(svc.ensure_weekly_backup())

    threads = [threading.Thread(target=worker) for _ in range(2)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=15)

    assert results.count(True) == 1, f"бекап должен создаться один раз: {results}"
    assert calls == ["auto"]
