"""Словари синонимов для парсера запросов и умного чата.

Словарь хранится в ``site_settings`` (ключ ``synonyms``), а при его
отсутствии используется упакованный ``engine/dictionary/synonyms.json``.
Так правки из админки не меняют файлы в репозитории и переживают
перезапуск/передеплой, а разные uvicorn-воркеры читают одно и то же
значение из БД.
"""
from __future__ import annotations

import importlib.resources
import json
import logging
from pathlib import Path
from typing import Any

from engine.dictionary.synonym_dictionary import SynonymDictionary

from backend.services.data_service import get_connection


logger = logging.getLogger(__name__)

SETTINGS_KEY = "synonyms"
SETTINGS_DESCRIPTION = "Словари синонимов для парсера и чата (JSON)"
PACKAGED_VERSION = "packaged"


def _packaged_path() -> Path:
    import engine

    return Path(engine.__file__).parent / "dictionary" / "synonyms.json"


def load_packaged_dictionary() -> dict:
    """Упакованный словарь — значения по умолчанию и основа сброса."""
    path = _packaged_path()

    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    # На случай установки пакетом, где файл доступен только как ресурс.
    resource = importlib.resources.files("engine.dictionary").joinpath(
        "synonyms.json"
    )
    return json.loads(resource.read_text(encoding="utf-8"))


def _normalize(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Словарь должен быть JSON-объектом")

    normalized = {
        category: data.get(category, {})
        for category in ("types", "cities", "keywords")
    }

    # Конструктор проверит структуру и конфликты алиасов.
    SynonymDictionary.from_dict(normalized)

    return normalized


def _read_stored(conn) -> tuple[dict | None, str]:
    row = conn.execute(
        """
        SELECT value, updated_at
        FROM site_settings
        WHERE key = %s
        """,
        (SETTINGS_KEY,),
    ).fetchone()

    if not row or row[0] is None:
        return None, PACKAGED_VERSION

    raw = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    updated_at = row[1]
    version = (
        updated_at.isoformat(timespec="microseconds")
        if updated_at is not None
        else PACKAGED_VERSION
    )

    return _normalize(raw), version


def load_active_dictionary() -> tuple[SynonymDictionary, str]:
    """Активный словарь и его версия.

    Версия — ``updated_at`` строки настроек; по ней ``ChatService``
    понимает, что словарь изменили в админке, и пересобирает парсер.
    При недоступной БД/битом значении используется упакованный словарь.
    """
    try:
        with get_connection() as conn:
            stored, version = _read_stored(conn)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Не удалось прочитать словарь синонимов из БД; "
            "используется упакованный"
        )
        return SynonymDictionary(_packaged_path()), PACKAGED_VERSION

    if stored is None:
        return SynonymDictionary(_packaged_path()), version

    try:
        return SynonymDictionary.from_dict(stored), version
    except (ValueError, TypeError, AttributeError):
        logger.exception(
            "Сохранённый словарь синонимов повреждён; "
            "используется упакованный"
        )
        return SynonymDictionary(_packaged_path()), f"{version}:broken"


def get_synonyms() -> dict:
    """Словарь для админки: активное значение и признак правки."""
    with get_connection() as conn:
        stored, version = _read_stored(conn)

    dictionary = stored if stored is not None else load_packaged_dictionary()

    return {
        "dictionary": dictionary,
        "is_custom": stored is not None,
        "updated_at": None if stored is None else version,
        "defaults": load_packaged_dictionary(),
    }


def save_synonyms(data: dict) -> dict:
    """Проверяет и сохраняет словарь; возвращает новое состояние."""
    normalized = _normalize(data)
    payload = json.dumps(normalized, ensure_ascii=False)

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO site_settings (key, value, value_type, description)
                VALUES (%s, %s, 'json', %s)
                ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (SETTINGS_KEY, payload, SETTINGS_DESCRIPTION),
            )

    return get_synonyms()


def reset_synonyms() -> dict:
    """Удаляет пользовательскую версию — снова используется файл."""
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "DELETE FROM site_settings WHERE key = %s",
                (SETTINGS_KEY,),
            )

    return get_synonyms()
