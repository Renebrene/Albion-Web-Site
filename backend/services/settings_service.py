"""Сервис настроек внешнего вида.

Схема SETTINGS_SCHEMA описывает редактируемые параметры; список легко
расширять по мере определения элементов, которые нужно настраивать.
Текущие значения хранятся в site_settings (ключ 'appearance', JSON),
наборы — в settings_presets (JSONB).
"""
from __future__ import annotations

import json
from typing import Any

from backend.services.data_service import get_connection


SETTINGS_KEY = "appearance"

FONT_OPTIONS = [
    {"label": "Inter", "value": "Inter"},
    {"label": "Roboto", "value": "Roboto"},
    {"label": "PT Sans", "value": "PT Sans"},
    {"label": "Montserrat", "value": "Montserrat"},
    {"label": "Manrope", "value": "Manrope"},
    {"label": "Системный", "value": "system"},
]

WEIGHT_OPTIONS = [
    {"label": "Обычный (400)", "value": "400"},
    {"label": "Средний (500)", "value": "500"},
    {"label": "Полужирный (600)", "value": "600"},
    {"label": "Жирный (700)", "value": "700"},
    {"label": "Очень жирный (800)", "value": "800"},
]

# Описание редактируемых параметров.
# type: text | number | color | select | toggle
# Для select обязательно options: [{label, value}]
# group: блок формы в админке ('appearance' по умолчанию, 'map' — карта)
SETTINGS_SCHEMA: list[dict[str, Any]] = [
    {
        "key": "font_family",
        "label": "Основной шрифт сайта",
        "type": "select",
        "options": FONT_OPTIONS,
        "default": "system",
    },
    {
        "key": "font_heading",
        "label": "Шрифт заголовков",
        "type": "select",
        "options": FONT_OPTIONS,
        "default": "system",
    },
    {
        "key": "font_size_base",
        "label": "Базовый размер шрифта, px",
        "type": "number",
        "default": "16",
    },
    {
        "key": "heading_weight",
        "label": "Насыщенность заголовков",
        "type": "select",
        "options": WEIGHT_OPTIONS,
        "default": "800",
    },
    {
        "key": "color_accent",
        "label": "Акцентный цвет",
        "type": "color",
        "default": "#e12a1f",
    },
    {
        "key": "color_background",
        "label": "Цвет фона страниц",
        "type": "color",
        "default": "#f3f5f6",
    },
    {
        "key": "color_text",
        "label": "Цвет основного текста",
        "type": "color",
        "default": "#17212b",
    },
    {
        "key": "radius_cards",
        "label": "Скругление карточек, px",
        "type": "number",
        "default": "18",
    },
    {
        "key": "radius_buttons",
        "label": "Скругление кнопок, px",
        "type": "number",
        "default": "10",
    },
    {
        "key": "map_engine",
        "label": "Оператор карты",
        "type": "select",
        "group": "map",
        "options": [
            {"label": "OpenStreetMap (Leaflet)", "value": "osm"},
            {"label": "Яндекс.Карты", "value": "yandex"},
        ],
        "default": "osm",
    },
    # Логика цвета точек на карте:
    #   three — три цвета (свободно / частично занято / занято);
    #   two   — два цвета (зелёный, если есть хоть одна свободная
    #           поверхность; иначе красный — всё занято/резерв/утверждение).
    {
        "key": "map_color_mode",
        "label": "Цвета точек на карте",
        "type": "select",
        "group": "map",
        "options": [
            {
                "label": "Три цвета: свободно / частично / занято",
                "value": "three",
            },
            {
                "label": "Два цвета: есть свободная / всё занято",
                "value": "two",
            },
        ],
        "default": "three",
    },
    # Цвета точек на карте: состояние конструкции по выбранным месяцам.
    # Используются и в маркерах (Leaflet/Яндекс), и в подписях статусов.
    {
        "key": "map_color_free",
        "label": "Цвет точки: свободно",
        "type": "color",
        "group": "map",
        "default": "#2ea66d",
    },
    {
        "key": "map_color_busy",
        "label": "Цвет точки: занято",
        "type": "color",
        "group": "map",
        "default": "#e24b42",
    },
    {
        "key": "map_color_mixed",
        "label": "Цвет точки: частично занято",
        "type": "color",
        "group": "map",
        "default": "#e6a51c",
    },
]

# Список ключей в порядке формы (для фронта)
SCHEMA_KEYS = [item["key"] for item in SETTINGS_SCHEMA]


def _default_appearance() -> dict[str, str]:
    return {item["key"]: str(item["default"]) for item in SETTINGS_SCHEMA}


def _read_current(conn) -> dict[str, str]:
    row = conn.execute(
        "SELECT value FROM site_settings WHERE key = %s",
        (SETTINGS_KEY,),
    ).fetchone()

    stored: dict = {}

    if row and row[0]:
        try:
            parsed = json.loads(row[0])
            if isinstance(parsed, dict):
                stored = parsed
        except (json.JSONDecodeError, TypeError):
            stored = {}

    defaults = _default_appearance()
    defaults.update(stored)

    return defaults


def _write_current(conn, values: dict[str, str]) -> None:
    conn.execute(
        """
        INSERT INTO site_settings (key, value, value_type, description)
        VALUES (%s, %s, 'json', 'Текущие настройки внешнего вида (JSON)')
        ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW()
        """,
        (SETTINGS_KEY, json.dumps(values, ensure_ascii=False)),
    )


def _schema_payload(include_defaults: bool = True) -> dict:
    return {
        "schema": SETTINGS_SCHEMA,
        "defaults": _default_appearance() if include_defaults else {},
    }


def get_settings() -> dict:
    """Текущие настройки + схема + наборы (для админки и публично)."""
    with get_connection() as conn:
        current = _read_current(conn)

        presets = conn.execute(
            """
            SELECT id, name, created_at
            FROM settings_presets
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()

    return {
        "current": current,
        "presets": [
            {
                "id": row[0],
                "name": row[1],
                "created_at": (
                    row[2].isoformat(timespec="seconds") if row[2] else None
                ),
            }
            for row in presets
        ],
        **_schema_payload(),
    }


def get_public_settings() -> dict:
    """Публичные настройки для применения к элементам сайта.

    Возвращает только текущие значения по ключам схемы — фронт может
    мапить их на CSS-переменные. Пустой объект, если схема не определена.
    """
    with get_connection() as conn:
        current = _read_current(conn)

    if not SETTINGS_SCHEMA:
        return {}

    return {key: current.get(key, "") for key in SCHEMA_KEYS}


def save_settings(settings: dict) -> dict:
    """Сохраняет текущие настройки (принимает любые ключи схемы)."""
    with get_connection() as conn:
        with conn.transaction():
            current = _read_current(conn)

            if not isinstance(settings, dict):
                raise ValueError("Настройки должны быть объектом")

            for key, value in settings.items():
                if key in SCHEMA_KEYS:
                    current[key] = str(value)

            _write_current(conn, current)

    return get_settings()


def create_preset(name: str) -> dict:
    name = (name or "").strip()

    if not name:
        raise ValueError("Укажите название набора")

    with get_connection() as conn:
        with conn.transaction():
            exists = conn.execute(
                "SELECT 1 FROM settings_presets WHERE name = %s",
                (name,),
            ).fetchone()

            if exists:
                raise ValueError("Набор с таким названием уже существует")

            current = _read_current(conn)

            conn.execute(
                """
                INSERT INTO settings_presets (name, payload)
                VALUES (%s, %s)
                """,
                (
                    name,
                    json.dumps(current, ensure_ascii=False),
                ),
            )

    return get_settings()


def delete_preset(preset_id: int) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM settings_presets WHERE id = %s",
                (preset_id,),
            )

    return get_settings()


def apply_preset(preset_id: int) -> dict:
    with get_connection() as conn:
        with conn.transaction():
            row = conn.execute(
                "SELECT payload FROM settings_presets WHERE id = %s",
                (preset_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Набор не найден")

            payload = row[0] if isinstance(row[0], dict) else json.loads(
                row[0] if row[0] else "{}"
            )

            current = _read_current(conn)

            for key in SCHEMA_KEYS:
                if key in payload:
                    current[key] = str(payload[key])

            _write_current(conn, current)

    return get_settings()


def reset_to_defaults() -> dict:
    with get_connection() as conn:
        with conn.transaction():
            _write_current(conn, _default_appearance())

    return get_settings()