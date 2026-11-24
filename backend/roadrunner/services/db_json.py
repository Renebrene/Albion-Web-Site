"""Приведение JSON/JSONB из PostgreSQL к Python-словарю.

Колонки `roadrunner_settings.settings` и `roadrunner_scenarios.scenario_data`
имеют тип JSONB. psycopg возвращает их уже распарсенными (dict), а старый код
вызывал `json.loads(row[0])` и падал с TypeError. Функция ниже сохраняет
совместимость и со строковым представлением (например, при чтении из SQLite
или из текстового дампа).
"""
from __future__ import annotations

import json
from typing import Any


def as_dict(value: Any) -> dict:
    """Вернуть dict из dict/str/bytes/None; невалидное значение → {}."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}
