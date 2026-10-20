"""Режим хранения медиа: локальный или дублирование в Albion.

Модуль не бросает исключений из ``upload_saved_objects``: локальная копия
уже записана, поэтому ошибка Albion превращается в предупреждение.
"""
from __future__ import annotations

import logging
from pathlib import Path

from backend.services import albion_storage


logger = logging.getLogger(__name__)


def mode() -> str:
    try:
        return albion_storage.resolve_config().get("mode", "local")
    except Exception:  # noqa: BLE001 — при сбое настроек работаем локально
        logger.warning("Albion storage: не удалось определить режим хранения")
        return "local"


def should_store_remote() -> bool:
    return mode() == "albion"


def public_url(record) -> str:
    """Публичный URL записи: external_url, иначе локальный /storage/..."""
    if isinstance(record, dict):
        external_url = record.get("external_url")
        storage_path = record.get("storage_path")
    else:
        external_url = getattr(record, "external_url", None)
        storage_path = getattr(record, "storage_path", None)

    if external_url:
        raw = str(external_url).strip()

        if raw.startswith(("http://", "https://")):
            return raw

    return f"/storage/{storage_path}" if storage_path else ""


def upload_saved_objects(objects) -> list[dict]:
    """Загружает созданные файлы в Albion.

    ``objects`` — последовательность ``(local_path, relative_path, kind)``.
    Возвращает по элементу на каждый файл:

        {
            "kind": ...,
            "storage_path": "<относительный путь>",
            "storage_backend": "albion" | "local",
            "external_url": str | None,
            "external_key": str | None,
            "error": str | None,
        }

    Ошибки не пробрасываются.
    """
    results: list[dict] = []

    for item in objects or ():
        try:
            local_path, relative_path, kind = item
        except (TypeError, ValueError):
            logger.warning("Albion storage: некорректный объект для загрузки")
            continue

        local_path = Path(local_path)
        relative_path = Path(relative_path)

        result = {
            "kind": kind,
            "storage_path": str(relative_path),
            "storage_backend": "local",
            "external_url": None,
            "external_key": None,
            "error": None,
        }

        try:
            uploaded = albion_storage.upload_file(
                local_path,
                relative_path.name,
                subfolder="site-media",
            )
            external_url = str(uploaded.get("url") or "").strip()

            if not external_url:
                raise albion_storage.AlbionError(
                    "Albion не вернул публичную ссылку"
                )

            result.update(
                storage_backend="albion",
                external_url=external_url,
                external_key=(
                    uploaded.get("file_id")
                    or uploaded.get("object_key")
                    or None
                ),
            )
        except Exception as exc:  # noqa: BLE001 — локальная копия важнее
            message = str(exc).strip()[:300] or exc.__class__.__name__
            logger.warning(
                "Albion storage: не удалось загрузить %s: %s",
                relative_path,
                message,
            )
            result["error"] = message

        results.append(result)

    return results
