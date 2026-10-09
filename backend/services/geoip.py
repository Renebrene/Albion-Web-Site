"""Определение страны по IP через локальную базу MaxMind-формата (.mmdb).

Базу можно взять любую в формате .mmdb:
  • DB-IP Lite  (CC BY 4.0, без аккаунта) — скрипт scripts/fetch_geoip.py;
  • GeoLite2 Country (MaxMind)             — положить файл рядом вручную.

Файл ищется в backend/data/*.mmdb (или по пути из ALBION_GEOIP_DB).
Если файла нет — модуль молча возвращает «страна неизвестна», а не падает:
трекинг визитов должен работать и без гео-базы.

Внимание: в БД IP не сохраняется — страна вычисляется в момент визита
и хранится отдельно (см. backend/services/visit_service.py).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from backend.services.data_service import PROJECT_DIR


logger = logging.getLogger(__name__)

# Каталог с базами по умолчанию.
DATA_DIR = PROJECT_DIR / "backend" / "data"

# Один читатель на процесс: открытие .mmdb не бесплатное.
_reader = None
_reader_path: Path | None = None
_load_failed = False


def _db_path() -> Path | None:
    """Путь к .mmdb: из env ALBION_GEOIP_DB либо первый *.mmdb в backend/data."""
    explicit = os.getenv("ALBION_GEOIP_DB")

    if explicit:
        path = Path(explicit)

        return path if path.is_file() else None

    if not DATA_DIR.is_dir():
        return None

    candidates = sorted(DATA_DIR.glob("*.mmdb"))

    return candidates[0] if candidates else None


def _get_reader():
    """Ленивая загрузка базы. None, если базы нет или она не читается."""
    global _reader, _reader_path, _load_failed

    path = _db_path()

    if path is None:
        if not _load_failed:
            logger.info(
                "GeoIP: база .mmdb не найдена (страна будет пустой). "
                "Загрузите: python -m scripts.fetch_geoip"
            )
            _load_failed = True

        return None

    if _reader is not None and _reader_path == path:
        return _reader

    try:
        import maxminddb

        _reader = maxminddb.open_database(str(path))
        _reader_path = path

        logger.info("GeoIP: загружена база %s", path.name)
    except Exception:
        logger.warning("GeoIP: не удалось открыть базу %s", path, exc_info=True)
        _reader = None
        _load_failed = True

    return _reader


# Поля, встречающиеся в разных сборках (GeoLite2 / DB-IP).
_NAME_KEYS = ("en", "ru")


def _country_names(record: dict) -> tuple[str | None, str | None]:
    code = record.get("country", {}).get("iso_code")

    country = record.get("country") or {}
    names = country.get("names") or {}

    name = None

    if isinstance(names, dict):
        for key in _NAME_KEYS:
            if names.get(key):
                name = names[key]
                break

    # DB-IP: {"country": {"iso_code": "RU", "names": {"en": "Russia"}}}
    # Некоторые сборки кладут имя в "country_name"/"continent".
    if not name:
        name = country.get("name") or record.get("country_name")

    if not code:
        return None, None

    return str(code).upper(), (str(name) if name else None)


def lookup_country(ip: str | None) -> tuple[str | None, str | None]:
    """Возвращает (ISO-код, название) для IP либо (None, None).

    Никогда не бросает исключение — вызывается в горячем пути трекинга.
    """
    if not ip:
        return None, None

    reader = _get_reader()

    if reader is None:
        return None, None

    try:
        record = reader.get(ip)
    except Exception:
        return None, None

    if not isinstance(record, dict):
        return None, None

    return _country_names(record)
