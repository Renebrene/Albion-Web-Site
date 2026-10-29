import hashlib
import json
import os
import threading
import time
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool


PROJECT_DIR = Path(__file__).resolve().parents[2]

def load_env_file(path):
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        os.environ.setdefault(key, value)


load_env_file(PROJECT_DIR / ".env")


MONTHS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}

STATUS_MAP = {
    "FREE": "Свободно",
    "SOLD": "Занято",
    "RESERVED": "В резерве",
    "PENDING": "На утверждении",
    "LOAD": "Доступность",
}

# Основные поля, которые можно временно переопределить (раздел «Конструкции»).
_OVERRIDABLE_FIELDS = frozenset(
    {
        "city",
        "address",
        "district",
        "side",
        "type",
        "size",
        "material",
        "light",
        "number",
    }
)


def _connection_kwargs() -> dict:
    kwargs = {
        "host": os.getenv("ALBION_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("ALBION_DB_PORT", "5432")),
        "dbname": os.getenv("ALBION_DB_NAME", "albion"),
        "user": os.getenv("ALBION_DB_USER", "albion_app"),
        "password": os.getenv("ALBION_DB_PASSWORD"),
    }

    if not kwargs["password"]:
        kwargs.pop("password")

    return kwargs


# Один bounded-пул на процесс. Иначе каждый get_connection() открывал новый
# backend PostgreSQL, а один HTTP-запрос мог открыть 3–4 соединения. При
# 6 workers и threadpool это упиралось в max_connections.
_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                try:
                    max_size = int(os.getenv("ALBION_DB_POOL_MAX", "4"))
                except ValueError:
                    max_size = 4

                try:
                    timeout = float(
                        os.getenv("ALBION_DB_POOL_TIMEOUT", "10")
                    )
                except ValueError:
                    timeout = 10.0

                _pool = ConnectionPool(
                    conninfo=make_conninfo(**_connection_kwargs()),
                    min_size=1,
                    max_size=max(1, max_size),
                    timeout=max(0.1, timeout),
                    open=True,
                    name="albion",
                )

    return _pool


def get_connection():
    """Соединение из пула; используйте через `with get_connection() as conn`."""
    return _get_pool().connection()


def get_raw_connection():
    """Отдельное соединение для advisory-lock/диагностики, вне пула."""
    return psycopg.connect(**_connection_kwargs())


def _text(value):
    return "" if value is None else str(value)


def _status(value):
    return STATUS_MAP.get(value, "Доступность")


def get_base_stats():
    """Сводка по базе для админ-карточек (состояние базы)."""
    with get_connection() as conn:
        last = conn.execute(
            """
            SELECT created_at
            FROM construction_imports
            WHERE status = 'active'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        surfaces_count = conn.execute(
            "SELECT COUNT(*) FROM surfaces WHERE is_active = TRUE"
        ).fetchone()[0]

        media_count = conn.execute(
            "SELECT COUNT(*) FROM media"
        ).fetchone()[0]

        photos_count = conn.execute(
            "SELECT COUNT(*) FROM media WHERE mime_type LIKE 'image/%'"
        ).fetchone()[0]

        # Скачанные превью фотографий адресов (активный импорт).
        previews_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM construction_media
            WHERE media_type = 'photo'
              AND card_path IS NOT NULL
              AND import_id = (
                  SELECT id FROM construction_imports
                  WHERE status = 'active'
                  ORDER BY id DESC
                  LIMIT 1
              )
            """
        ).fetchone()[0]

        return {
            "last_update": (
                last[0].isoformat() if last and last[0] else None
            ),
            "constructions": int(surfaces_count),
            "media": int(media_count),
            "photos": int(photos_count),
            "previews": int(previews_count),
        }


def get_data():
    """
    Возвращает конструкции в точности в формате,
    который ранее формировался из data.js.
    Источник данных: PostgreSQL.
    """

    sql = """
        SELECT
            s.id,
            s.surface_hash,
            c.address,
            c.district,
            ci.name AS city,

            s.latitude,
            s.longitude,
            s.map,
            s.name,
            s.external_number,
            cm.card_path,
            cm.thumb_path,
            cm.large_path,
            cmm.card_path,
            cmm.thumb_path,
            cmm.large_path,
            s.price,
            s.side,
            s.size,
            s.type,
            s.light,
            s.material,

            a.year,
            a.month,
            a.raw_value,
            a.status,
            a.price

        FROM surfaces s
        JOIN constructions c
            ON c.id = s.construction_id
        JOIN cities ci
            ON ci.id = c.city_id
        LEFT JOIN construction_media cm
            ON cm.import_id = (
                SELECT id
                FROM construction_imports
                WHERE status = 'active'
                LIMIT 1
            )
           AND cm.surface_hash = s.surface_hash
           AND cm.media_type = 'photo'
        LEFT JOIN construction_media cmm
            ON cmm.import_id = (
                SELECT id
                FROM construction_imports
                WHERE status = 'active'
                LIMIT 1
            )
           AND cmm.surface_hash = s.surface_hash
           AND cmm.media_type = 'map'
        LEFT JOIN surface_availability a
            ON a.surface_id = s.id

        WHERE s.is_active = TRUE

        ORDER BY s.id, a.year, a.month
    """

    records = {}

    # Переопределения фото конструкций (медиатека конструкций), активного импорта.
    from backend.services.construction_overrides import (
        get_fields_map,
        get_month_fields_map,
        get_overrides_map,
    )

    overrides = get_overrides_map()
    field_overrides = get_fields_map()
    month_field_overrides = get_month_fields_map()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

            for row in cur.fetchall():
                (
                    surface_id,
                    surface_hash,
                    address,
                    district,
                    city,
                    latitude,
                    longitude,
                    map_url,
                    name,
                    external_number,
                    photo_path,
                    photo_thumb_path,
                    photo_large_path,
                    map_card_path,
                    map_thumb_path,
                    map_large_path,
                    price,
                    side,
                    size,
                    media_type,
                    light,
                    material,
                    availability_year,
                    month,
                    raw_value,
                    db_status,
                    month_price,
                ) = row

                if surface_id not in records:
                    records[surface_id] = {
                        "id": surface_id,
                        "surface_hash": _text(surface_hash),
                        "address": _text(address),
                        "city": _text(city),
                        "district": _text(district),
                        "lat": latitude,
                        "lng": longitude,
                        "map": _text(map_url),
                        "months": {},
                        "month_prices": {},
                        "month_years": {},

                        "name": _text(name),
                        "number": _text(external_number),
                        # Абсолютный путь от корня сайта: /storage/... —
        # иначе относительный src ломается на вложенных роутах
        # (/vozmozhnosti, /novosti/:slug и т.п.).
        "photo": (
            "/" + _text(photo_path)
            if photo_path
            else ""
        ),
                        # Миниатюра (thumb) и полноразмерная версия (large)
                        # того же фото. Пусто -> null, чтобы фронтенд мог
                        # отличить «нет картинки» от валидного пути и
                        # использовать photo как fallback.
                        "photo_thumb": (
                            "/" + _text(photo_thumb_path)
                            if photo_thumb_path
                            else None
                        ),
                        "photo_large": (
                            "/" + _text(photo_large_path)
                            if photo_large_path
                            else None
                        ),
                        # Карта-схема — локально сохранённый файл (импорт),
                        # отдельным LEFT JOIN cmm (media_type='map').
                        # Поле "map" выше — прежняя ссылка Яндекс.Диска,
                        # её не перезаписываем.
                        #
                        # Отдаём только крупный вариант: map_card и map_thumb
                        # всегда присутствуют вместе с map_large, а фронтенд
                        # берёт их лишь как фолбэк. Экономия ~0.4 МБ.
                        "map_large": (
                            "/" + _text(map_large_path)
                            if map_large_path
                            else None
                        ),
                        "price": _text(price),
                        "light": _text(light),
                        "material": _text(material),
                        "side": _text(side),
                        "size": _text(size),
                        "statuses": {},
                        "type": _text(media_type),
                    }

                    # Переопределение фото/карты из медиатеки конструкций
                    # (действует, пока активен тот же импорт).
                    photo_override = overrides.get((surface_hash, "photo"))

                    if photo_override:
                        item = records[surface_id]
                        item["photo"] = (
                            photo_override.get("card")
                            or photo_override.get("large")
                            or item["photo"]
                        )
                        item["photo_thumb"] = (
                            photo_override.get("thumb") or item["photo_thumb"]
                        )
                        item["photo_large"] = (
                            photo_override.get("large") or item["photo_large"]
                        )
                        item.setdefault("overridden", []).append("photo")

                    map_override = overrides.get((surface_hash, "map"))

                    if map_override:
                        item = records[surface_id]
                        item["map_large"] = (
                            map_override.get("large") or item["map_large"]
                        )
                        item.setdefault("overridden", []).append("map")

                    # Временное переопределение основных полей (адрес, город,
                    # район, тип, размер, сторона, свет, материал, номер).
                    field_override = field_overrides.get(surface_hash)

                    if field_override:
                        item = records[surface_id]

                        for key, value in field_override.items():
                            if key in _OVERRIDABLE_FIELDS:
                                item[key] = _text(value)

                        item["overridden"] = sorted(
                            set(item.get("overridden") or [])
                            | {
                                key
                                for key in field_override
                                if key != "__months"
                            }
                        )

                if month is not None and month in MONTHS:
                    month_name = MONTHS[month]
                    records[surface_id]["months"][month_name] = _text(
                        raw_value
                    )
                    records[surface_id]["month_years"][month_name] = int(
                        availability_year
                    )
                    records[surface_id]["statuses"][month_name] = _status(
                        db_status
                    )
                    records[surface_id].setdefault("month_prices", {})[
                        month_name
                    ] = _text(month_price)

                    month_override = month_field_overrides.get(
                        (
                            surface_hash,
                            int(availability_year),
                            int(month),
                        ),
                        {},
                    )
                    if "price" in month_override:
                        records[surface_id]["month_prices"][month_name] = str(
                            month_override["price"]
                        )
                    if "status" in month_override:
                        records[surface_id]["statuses"][month_name] = (
                            {
                                "free": "Свободно",
                                "reserved": "В резерве",
                                "pending": "На утверждении",
                                "busy": "Занято",
                            }.get(str(month_override["status"]), "Свободно")
                        )
                    if month_override:
                        records[surface_id].setdefault("overridden", []).append(
                            f"month:{month_name}"
                        )

    result = []

    # Месяцы НЕ достраиваем до фиксированного списка: в ответе только те,
    # что реально есть в новой базе (выгрузка может содержать 3, а не 5).
    for item in records.values():
        result.append(item)

    return result


# --------------------------------------------------------------- кэш ответа

# Публичный /api/constructions отдаётся целиком и стоит ~100 мс CPU
# (SQL + сборка + сериализация). Данные меняются только при импорте,
# поэтому кэшируем сериализованное тело и повторно отдаём его с ETag.
# TTL — страховка на случай правок мимо импорта; основной сброс —
# invalidate_data_cache() после успешного импорта.
DATA_CACHE_TTL = float(os.environ.get("ALBION_DATA_CACHE_TTL", "30"))

# Кэш живёт в памяти КАЖДОГО процесса uvicorn, поэтому сброса в одном
# воркере мало: остальные до DATA_CACHE_TTL отдавали бы старое тело.
# Файл-метка в tmp хранит «версию» данных; каждый воркер на каждом запросе
# дешёво сверяет её и перечитывает данные при расхождении.
_CACHE_STAMP_PATH = PROJECT_DIR / "tmp" / ".data_cache_stamp"


def _read_cache_stamp() -> str:
    try:
        return _CACHE_STAMP_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


_data_cache = {
    "ts": 0.0,
    "body": None,
    "etag": None,
    "stamp": None,
}


def get_data_json() -> "tuple[bytes, str]":
    """Сериализованный /api/constructions: (тело, ETag)."""
    now = time.monotonic()
    cached = _data_cache
    stamp = _read_cache_stamp()

    if (
        cached["body"] is not None
        and cached["stamp"] == stamp
        and (now - cached["ts"]) < DATA_CACHE_TTL
    ):
        return cached["body"], cached["etag"]

    body = json.dumps(
        get_data(),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    etag = '"' + hashlib.sha1(body).hexdigest() + '"'

    _data_cache["ts"] = now
    _data_cache["body"] = body
    _data_cache["etag"] = etag
    _data_cache["stamp"] = stamp

    return body, etag


def invalidate_data_cache() -> None:
    """Сбросить кэш /api/constructions (вызывается после импорта/правок).

    Обновляет файл-метку, чтобы данные перечитали ВСЕ воркеры, а не только
    тот, что обработал запрос на изменение.
    """
    _data_cache["ts"] = 0.0
    _data_cache["body"] = None
    _data_cache["etag"] = None
    _data_cache["stamp"] = None

    try:
        _CACHE_STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_STAMP_PATH.write_text(str(time.time_ns()), encoding="utf-8")
    except OSError:
        pass


# Нормализованный ключ физической конструкции.
#
# Одна физическая конструкция может занимать несколько строк в constructions:
# например, призматрон «40 Лет Победы пр-кт 146А» хранится двумя строками
# «…(в Александровку)» и «…(в город)» (по одной стороне в каждой), а
# двусторонний щит на разделительной — строками «…(в центр)» / «…(из центра)».
# Поэтому физическую конструкцию считаем по адресу без хвостовой скобки.
# Исключения (строки остаются разными объектами):
#   · в скобке — самостоятельная позиция (км/поз./№/«конструкция N»/начало-середина-конец);
#   · видеоэкран: по одному адресу у него две стороны — но это ДВА отдельных
#     экрана, поэтому такие строки не склеиваем (ключ — полный адрес).
_PHYSICAL_KEY = (
    "CASE WHEN EXISTS (SELECT 1 FROM surfaces vs "
    "WHERE vs.construction_id = c.id AND vs.is_active AND vs.type = 'Видеоэкран') "
    "THEN c.address "
    "WHEN c.address ~* "
    r"'\([^)]*(поз|позиц|км|№|конструкц|начал|середин|конец)[^)]*\)\s*$' "
    "THEN c.address "
    r"ELSE regexp_replace(c.address, '\s*\([^)]*\)\s*$', '') END"
)
# Сторона физической конструкции: у поверхности side вида «A1(1)» сторона — «A1».
_PARENT_SIDE = r"regexp_replace(s.side, '\(.*\)$', '')"

_CTE_PHYSICAL = (
    "WITH cc AS (SELECT c.id, c.city_id, " + _PHYSICAL_KEY + " AS pkey "
    "FROM constructions c WHERE c.is_active) "
)


def get_constructions_stats() -> dict:
    """Сводка по рекламной сети: конструкции, стороны, поверхности, форматы.

    конструкции/стороны — по физическим объектам (см. ``_PHYSICAL_KEY``);
    поверхности — все строки-поверхности. Разбивка ``formats`` — число
    ПОВЕРХНОСТЕЙ по формату, поэтому её сумма совпадает с ``surfaces`` и
    со списком на странице «Возможности».
    """
    with get_connection() as conn:
        total = conn.execute(
            _CTE_PHYSICAL + "SELECT COUNT(DISTINCT (city_id, pkey)) FROM cc"
        ).fetchone()[0]

        surfaces = conn.execute(
            "SELECT COUNT(*) FROM surfaces WHERE is_active"
        ).fetchone()[0]

        sides = conn.execute(
            _CTE_PHYSICAL
            + "SELECT COUNT(DISTINCT (c.city_id, c.pkey, " + _PARENT_SIDE + ")) "
            "FROM surfaces s JOIN cc c ON c.id = s.construction_id "
            "WHERE s.is_active"
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT COALESCE(NULLIF(type, ''), '—') AS tp, COUNT(*) AS c "
            "FROM surfaces WHERE is_active GROUP BY tp ORDER BY c DESC"
        ).fetchall()

    return {
        "constructions": total,
        "surfaces": surfaces,
        "sides": sides,
        "formats": [{"name": r[0], "count": r[1]} for r in rows],
    }


def get_geo_location_stats() -> dict:
    """Статистика по городам/районам для geo-слайда главной.

    Возвращает словарь ``{имя_города_lower: {"constructions": N,
    "surfaces": M, "formats": [...]}}``:
    ``constructions`` — число физических конструкций (см. ``_PHYSICAL_KEY``),
    ``surfaces`` — общее число поверхностей,
    ``formats`` — число ПОВЕРХНОСТЕЙ по формату (как в списке «Возможности»).
    """
    with get_connection() as conn:
        obj_rows = conn.execute(
            _CTE_PHYSICAL
            + "SELECT ci.name, COUNT(DISTINCT cc.pkey) "
            "FROM cc JOIN cities ci ON ci.id = cc.city_id GROUP BY ci.name"
        ).fetchall()
        fmt_rows = conn.execute(
            "SELECT ci.name, COALESCE(NULLIF(s.type, ''), '—') AS tp, COUNT(*) "
            "FROM surfaces s JOIN constructions c ON c.id = s.construction_id "
            "JOIN cities ci ON ci.id = c.city_id "
            "WHERE s.is_active AND c.is_active GROUP BY 1, 2"
        ).fetchall()

    result: dict[str, dict] = {}
    for name, count in obj_rows:
        result[str(name or "").strip().lower()] = {
            "constructions": count, "formats": []
        }
    for name, tp, count in fmt_rows:
        key = str(name or "").strip().lower()
        item = result.setdefault(key, {"constructions": 0, "formats": []})
        item["formats"].append({"name": tp, "count": count})

    for item in result.values():
        item["formats"].sort(key=lambda f: (-f["count"], f["name"]))
        # Для карточек на главной показываем общее число поверхностей,
        # а не физических конструкций.
        item["surfaces"] = sum(int(f["count"]) for f in item["formats"])

    return result
