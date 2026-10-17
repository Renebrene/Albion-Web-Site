"""Переопределение фото конструкций (медиатека конструкций).

Превью конструкций лежат в папке активного импорта:
    storage/constructions/imports/<import_key>/<photo|map>/<large|card|thumb>/...

Переопределение хранит собственную версию превью в отдельном каталоге
``storage/constructions/overrides/`` и привязано к активному импорту
(``import_id``): пока импорт активен — сайт отдаёт переопределённое фото
(карта, список, чат, портфель); после следующего импорта активный импорт
меняется и переопределение перестаёт применяться. То есть изменение временное —
«до следующего обновления базы».
"""
from __future__ import annotations

import os

from psycopg.types.json import Json

from backend.services.data_service import (
    PROJECT_DIR,
    _read_cache_stamp,
    get_connection,
)


OVERRIDE_DIR = PROJECT_DIR / "storage" / "constructions" / "overrides"

# Релятивный префикс путей (совпадает с construction_media.*_path).
_OVERRIDE_REL = "storage/constructions/overrides"

# Небольшой кэш карты переопределений активного импорта.
_CACHE: dict = {"key": None, "stamp": None, "map": {}}


def invalidate() -> None:
    _CACHE["key"] = None
    _CACHE["stamp"] = None
    _CACHE["map"] = {}


def _invalidate_data_cache() -> None:
    from backend.services.data_service import invalidate_data_cache

    invalidate_data_cache()


def _active_import(conn) -> tuple[int | None, str | None]:
    row = conn.execute(
        """
        SELECT id, import_key
        FROM construction_imports
        WHERE status = 'active'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    return (row[0], row[1]) if row else (None, None)


def _url(rel_path: str | None) -> str:
    if not rel_path:
        return ""

    return "/" + str(rel_path).lstrip("/")


def get_overrides_map(force: bool = False) -> dict:
    """{(surface_hash, media_type): {large, card, thumb}} активного импорта."""
    stamp = _read_cache_stamp()

    # Быстрый путь: пока метка версии данных не менялась, в БД не ходим.
    # Импорт и правки медиа вызывают invalidate_data_cache(), который
    # перезаписывает метку.
    if (
        not force
        and _CACHE["key"] is not None
        and _CACHE["stamp"] == stamp
    ):
        return _CACHE["map"]

    with get_connection() as conn:
        import_id, _key = _active_import(conn)

        if import_id is None:
            _CACHE["key"] = None
            _CACHE["stamp"] = stamp
            _CACHE["map"] = {}
            return {}

        if not force and _CACHE["key"] == import_id:
            _CACHE["stamp"] = stamp
            return _CACHE["map"]

        rows = conn.execute(
            """
            SELECT surface_hash, media_type, large_path, card_path, thumb_path
            FROM construction_media_overrides
            WHERE import_id = %s
            """,
            (import_id,),
        ).fetchall()

    result: dict = {}

    for surface_hash, media_type, large_path, card_path, thumb_path in rows:
        result[(surface_hash, media_type)] = {
            "large": _url(large_path),
            "card": _url(card_path),
            "thumb": _url(thumb_path),
        }

    _CACHE["key"] = import_id
    _CACHE["stamp"] = stamp
    _CACHE["map"] = result

    return result


def get_override(surface_hash: str | None, media_type: str) -> dict | None:
    if not surface_hash:
        return None

    return get_overrides_map().get((surface_hash, media_type))


def _write_variants(surface_hash: str, media_type: str, data: bytes, original_name):
    """Строит варианты превью и складывает их в каталог переопределений."""
    from backend.services.media_service import (
        _build_static_variants,
        _open_image,
    )

    image = _open_image(data)
    preserve_png = str(original_name or "").lower().endswith(".png")
    variants = _build_static_variants(image, preserve_png)

    OVERRIDE_DIR.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}

    for variant, (payload, _mime, extension) in variants.items():
        name = f"{surface_hash}_{media_type}_{variant}{extension}"
        target = OVERRIDE_DIR / name
        tmp = target.with_suffix(target.suffix + ".tmp")

        tmp.write_bytes(payload)
        os.replace(tmp, target)

        paths[variant] = f"{_OVERRIDE_REL}/{name}"

    return paths


def save_override(
    surface_hash: str,
    media_type: str,
    data: bytes,
    original_name: str | None = None,
) -> dict:
    """Сохраняет переопределение фото конструкции для активного импорта."""
    media_type = media_type or "photo"

    paths = _write_variants(surface_hash, media_type, data, original_name)

    with get_connection() as conn:
        import_id, _key = _active_import(conn)

        conn.execute(
            """
            INSERT INTO construction_media_overrides
                (import_id, surface_hash, media_type,
                 large_path, card_path, thumb_path, original_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (surface_hash, media_type) DO UPDATE
            SET import_id = EXCLUDED.import_id,
                large_path = EXCLUDED.large_path,
                card_path = EXCLUDED.card_path,
                thumb_path = EXCLUDED.thumb_path,
                original_name = EXCLUDED.original_name,
                updated_at = NOW()
            """,
            (
                import_id,
                surface_hash,
                media_type,
                paths.get("large"),
                paths.get("card"),
                paths.get("thumb"),
                original_name,
            ),
        )

    invalidate()
    _invalidate_data_cache()

    return {
        "surface_hash": surface_hash,
        "media_type": media_type,
        "photo": _url(paths.get("card") or paths.get("large")),
        "photo_card": _url(paths.get("card")),
        "photo_thumb": _url(paths.get("thumb")),
        "photo_large": _url(paths.get("large")),
    }


def _read_storage_file(url: str) -> tuple[bytes, str]:
    """Читает файл из хранилища по сохранённому пути (/storage/... или storage/...)."""
    value = str(url or "").strip()

    if value.startswith("/storage/"):
        rel = value[len("/storage/") :]
    elif value.startswith("storage/"):
        rel = value[len("storage/") :]
    else:
        rel = value.lstrip("/")

    target = PROJECT_DIR / "storage" / rel

    if not target.is_file():
        raise FileNotFoundError(f"Файл не найден: {url}")

    return target.read_bytes(), target.name


def save_override_from_url(
    surface_hash: str,
    media_type: str,
    source_url: str,
    original_name: str | None = None,
) -> dict:
    """Переопределяет фото, копируя уже существующий файл (выбор из каталога превью)."""
    data, name = _read_storage_file(source_url)

    return save_override(surface_hash, media_type, data, original_name or name)


def clear_override(surface_hash: str, media_type: str = "photo") -> bool:
    """Снимает переопределение и удаляет его файлы из каталога."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT large_path, card_path, thumb_path
            FROM construction_media_overrides
            WHERE surface_hash = %s AND media_type = %s
            """,
            (surface_hash, media_type),
        ).fetchone()

        conn.execute(
            """
            DELETE FROM construction_media_overrides
            WHERE surface_hash = %s AND media_type = %s
            """,
            (surface_hash, media_type),
        )

    if row:
        for rel in row:
            if not rel:
                continue

            try:
                (PROJECT_DIR / str(rel)).unlink(missing_ok=True)
            except OSError:
                pass

    invalidate()
    _invalidate_data_cache()

    return True


def list_overrides() -> list[dict]:
    """Список переопределений активного импорта (для админки)."""
    with get_connection() as conn:
        _import_id, _key = _active_import(conn)

        rows = conn.execute(
            """
            SELECT surface_hash, media_type, card_path, thumb_path, large_path,
                   original_name, updated_at
            FROM construction_media_overrides
            ORDER BY updated_at DESC
            """
        ).fetchall()

    return [
        {
            "surface_hash": row[0],
            "media_type": row[1],
            "url": _url(row[2] or row[4]),
            "thumb": _url(row[3]),
            "original_name": row[5],
            "updated_at": row[6].isoformat() if row[6] else None,
        }
        for row in rows
    ]


# --------------------------------------------------- поля (не фото)

# Разрешённые к переопределению основные поля конструкции.
FIELD_KEYS = (
    "city",
    "address",
    "district",
    "side",
    "type",
    "size",
    "material",
    "light",
    "number",
)

_FIELD_CACHE: dict = {"key": None, "stamp": None, "map": {}}


def _invalidate_fields() -> None:
    _FIELD_CACHE["key"] = None
    _FIELD_CACHE["stamp"] = None
    _FIELD_CACHE["map"] = {}


def get_fields_map(force: bool = False) -> dict:
    """{surface_hash: {поле: значение}} переопределений активного импорта."""
    stamp = _read_cache_stamp()

    if (
        not force
        and _FIELD_CACHE["key"] is not None
        and _FIELD_CACHE["stamp"] == stamp
    ):
        return _FIELD_CACHE["map"]

    with get_connection() as conn:
        import_id, _key = _active_import(conn)

        if import_id is None:
            _FIELD_CACHE["key"] = None
            _FIELD_CACHE["stamp"] = stamp
            _FIELD_CACHE["map"] = {}
            return {}

        if not force and _FIELD_CACHE["key"] == import_id:
            _FIELD_CACHE["stamp"] = stamp
            return _FIELD_CACHE["map"]

        rows = conn.execute(
            """
            SELECT surface_hash, fields
            FROM construction_field_overrides
            WHERE import_id = %s
            """,
            (import_id,),
        ).fetchall()

    result: dict = {}

    for surface_hash, fields in rows:
        if isinstance(fields, dict) and fields:
            result[surface_hash] = fields

    _FIELD_CACHE["key"] = import_id
    _FIELD_CACHE["stamp"] = stamp
    _FIELD_CACHE["map"] = result

    return result


def get_fields(surface_hash: str | None) -> dict | None:
    if not surface_hash:
        return None

    return get_fields_map().get(surface_hash)


def save_fields(surface_hash: str, fields: dict) -> dict:
    """Сохраняет основные поля, сохраняя уже записанные month overrides."""
    clean: dict = {}

    for key in FIELD_KEYS:
        if key in (fields or {}):
            value = fields[key]
            clean[key] = "" if value is None else str(value).strip()

    with get_connection() as conn:
        import_id, _key = _active_import(conn)
        row = conn.execute(
            "SELECT fields FROM construction_field_overrides WHERE surface_hash = %s",
            (surface_hash,),
        ).fetchone()
        existing = row[0] if row and isinstance(row[0], dict) else {}
        merged = {"__months": existing["__months"]} if isinstance(existing.get("__months"), dict) else {}
        merged.update(clean)

        if merged:
            conn.execute(
                """
                INSERT INTO construction_field_overrides
                    (surface_hash, import_id, fields)
                VALUES (%s, %s, %s)
                ON CONFLICT (surface_hash) DO UPDATE
                SET import_id = EXCLUDED.import_id,
                    fields = EXCLUDED.fields,
                    updated_at = NOW()
                """,
                (surface_hash, import_id, Json(merged)),
            )
        else:
            conn.execute(
                "DELETE FROM construction_field_overrides WHERE surface_hash = %s",
                (surface_hash,),
            )

    _invalidate_fields()
    _invalidate_data_cache()

    return {"surface_hash": surface_hash, "fields": clean}


def clear_fields(surface_hash: str) -> bool:
    """Снимает только основные поля; monthly overrides очищаются отдельно."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT fields FROM construction_field_overrides WHERE surface_hash = %s",
            (surface_hash,),
        ).fetchone()
        existing = row[0] if row and isinstance(row[0], dict) else {}
        months = existing.get("__months")
        if isinstance(months, dict) and months:
            conn.execute(
                "UPDATE construction_field_overrides SET fields = %s, updated_at = NOW() WHERE surface_hash = %s",
                (Json({"__months": months}), surface_hash),
            )
        else:
            conn.execute(
                "DELETE FROM construction_field_overrides WHERE surface_hash = %s",
                (surface_hash,),
            )

    _invalidate_fields()
    _invalidate_data_cache()

    return True


# -------------------------------------------- цены/статусы по месяцам

_MONTH_STATUSES = {"free", "reserved", "pending", "busy"}


def _clean_month_overrides(months: dict) -> list[tuple[int, int, dict]]:
    """Validate UI month override entries and convert month names to numbers."""
    from backend.services.data_service import MONTHS

    names_to_numbers = {name: number for number, name in MONTHS.items()}
    clean = []
    for month_name, values in (months or {}).items():
        if not isinstance(values, dict):
            continue
        month_number = names_to_numbers.get(month_name)
        if month_number is None:
            raise ValueError(f"Неизвестный месяц: {month_name}")
        try:
            year = int(values.get("year"))
        except (TypeError, ValueError):
            raise ValueError(f"Некорректный год за {month_name}")
        if not 2000 <= year <= 2100:
            raise ValueError(f"Год за {month_name} вне допустимого диапазона")

        item: dict[str, object] = {}
        if "price" in values:
            price = values["price"]
            if price in (None, ""):
                item["price"] = ""
            else:
                try:
                    number = float(str(price).replace(" ", "").replace(",", "."))
                except (TypeError, ValueError):
                    raise ValueError(f"Некорректная цена за {month_name}")
                if not 0 <= number <= 10_000_000:
                    raise ValueError(f"Цена за {month_name} вне допустимого диапазона")
                item["price"] = str(int(number)) if number.is_integer() else str(number)

        if "status" in values:
            status = str(values["status"] or "").strip().lower()
            if status not in _MONTH_STATUSES:
                raise ValueError(f"Некорректный статус за {month_name}")
            item["status"] = status

        if item:
            clean.append((year, month_number, item))
    return clean


def get_month_fields_map(force: bool = False) -> dict:
    """{(surface_hash, year, month): {price, status}} active-import overrides."""
    stamp = _read_cache_stamp()
    cache = _MONTH_FIELDS_CACHE
    if not force and cache["stamp"] == stamp and cache["map"] is not None:
        return cache["map"]

    with get_connection() as conn:
        import_id, _key = _active_import(conn)
        if import_id is None:
            result = {}
        else:
            rows = conn.execute(
                """
                SELECT surface_hash, year, month, price, status
                FROM construction_month_overrides
                WHERE import_id = %s
                """,
                (import_id,),
            ).fetchall()
            result = {
                (row[0], int(row[1]), int(row[2])): {
                    **({"price": row[3]} if row[3] is not None else {}),
                    **({"status": row[4]} if row[4] is not None else {}),
                }
                for row in rows
            }

    cache.update(stamp=stamp, map=result)
    return result


_MONTH_FIELDS_CACHE = {"stamp": None, "map": None}


def save_month_fields(surface_hash: str, months: dict) -> dict:
    clean = _clean_month_overrides(months)
    if not clean:
        return {"surface_hash": surface_hash, "months": {}}

    with get_connection() as conn:
        import_id, _key = _active_import(conn)
        if import_id is None:
            raise ValueError("Нет активного импорта конструкций")
        for year, month, values in clean:
            conn.execute(
                """
                INSERT INTO construction_month_overrides
                    (import_id, surface_hash, year, month, price, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (import_id, surface_hash, year, month) DO UPDATE
                SET price = COALESCE(EXCLUDED.price, construction_month_overrides.price),
                    status = COALESCE(EXCLUDED.status, construction_month_overrides.status),
                    updated_at = NOW()
                """,
                (import_id, surface_hash, year, month,
                 values.get("price"), values.get("status")),
            )

    _MONTH_FIELDS_CACHE.update(stamp=None, map=None)
    _invalidate_data_cache()
    return {"surface_hash": surface_hash, "months": months}


def clear_month_fields(surface_hash: str) -> bool:
    with get_connection() as conn:
        import_id, _key = _active_import(conn)
        if import_id is not None:
            conn.execute(
                "DELETE FROM construction_month_overrides "
                "WHERE import_id = %s AND surface_hash = %s",
                (import_id, surface_hash),
            )
    _MONTH_FIELDS_CACHE.update(stamp=None, map=None)
    _invalidate_data_cache()
    return True
