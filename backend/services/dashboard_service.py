"""Настройка дашборда админки: порядок плиток и их названия/описания.

Каталог плиток (какие разделы существуют и их значения по умолчанию) живёт
во фронтенде — он же рендерит страницу. В БД храним только переопределения:
порядок и новые заголовки/описания. Так новые плитки, добавленные в код,
появляются автоматически, а сохранённые правки к ним не мешают.

Значение лежит в site_settings (общая key/value-таблица) как JSON-строка.
"""
from __future__ import annotations

import json

from backend.services.data_service import get_connection


SETTINGS_KEY = "admin_dashboard_layout"
SETTINGS_DESCRIPTION = "Дашборд админки: порядок плиток и переименования"

EMPTY_LAYOUT = {"order": [], "items": {}}


def _parse(value) -> dict:
    """Аккуратно приводим сохранённое значение к структуре раскладки."""
    if not value:
        return {"order": [], "items": {}}

    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {"order": [], "items": {}}

    if not isinstance(data, dict):
        return {"order": [], "items": {}}

    order = [
        path for path in (data.get("order") or [])
        if isinstance(path, str)
    ]

    items = {}
    raw_items = data.get("items")

    if isinstance(raw_items, dict):
        for path, patch in raw_items.items():
            if not isinstance(path, str) or not isinstance(patch, dict):
                continue

            entry = {}

            if isinstance(patch.get("title"), str):
                entry["title"] = patch["title"]

            if isinstance(patch.get("text"), str):
                entry["text"] = patch["text"]

            # Значок: либо ключ из набора предустановленных, либо URL файла
            # из медиатеки. Пустая строка — это явное «без значка» (перебивает
            # значок по умолчанию), поэтому сохраняем значение, если ключ
            # вообще присутствует в патче.
            if "icon" in patch and isinstance(patch.get("icon"), str):
                entry["icon"] = patch["icon"].strip()[:500]

            if entry:
                items[path] = entry

    return {"order": order, "items": items}


def get_dashboard_layout() -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM site_settings WHERE key = %s",
                (SETTINGS_KEY,),
            )
            row = cur.fetchone()

    return _parse(row[0] if row else None)


def save_dashboard_layout(payload: dict) -> dict:
    layout = _parse(json.dumps(payload or {}))
    value = json.dumps(layout, ensure_ascii=False)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO site_settings (key, value, value_type, description)
                VALUES (%s, %s, 'json', %s)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    value_type = EXCLUDED.value_type,
                    updated_at = NOW()
                """,
                (SETTINGS_KEY, value, SETTINGS_DESCRIPTION),
            )

    return layout
