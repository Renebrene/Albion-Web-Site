"""Активный сценарий Roadrunner.

Сценарий, применённый из чата/админки, живёт в таблице настроек под отдельным
ключом. Баннер опрашивает его и после завершения возвращается к коду БД.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from backend.services.data_service import get_connection

KEY = "active_scenario"


def apply_scenario(scenario: dict[str, Any]) -> dict[str, Any]:
    """Записать активный сценарий с момента старта."""
    payload = {
        "scenario": scenario,
        "started_at": time.time(),
        "duration": int(scenario.get("duration") or 60),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO roadrunner_settings (key, settings)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET settings = EXCLUDED.settings
            """,
            (KEY, json.dumps(payload, ensure_ascii=False)),
        )

    return payload


def get_active_scenario() -> Optional[dict[str, Any]]:
    """Вернуть сценарий, если он ещё не закончился."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT settings FROM roadrunner_settings WHERE key = %s",
                (KEY,),
            ).fetchone()
    except Exception:
        return None

    if not row:
        return None

    try:
        raw = row[0]
        payload = raw if isinstance(raw, dict) else json.loads(raw)
    except Exception:
        return None

    started = float(payload.get("started_at") or 0)
    duration = int(payload.get("duration") or 60)

    if started and time.time() - started > duration + 5:
        clear_active_scenario()
        return None

    return payload


def clear_active_scenario() -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM roadrunner_settings WHERE key = %s", (KEY,)
        )
