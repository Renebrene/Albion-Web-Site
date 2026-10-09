import hashlib
import json
import os
import time
from pathlib import Path

import psycopg


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


def get_connection():
    return psycopg.connect(
        host=os.getenv("ALBION_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("ALBION_DB_PORT", "5432")),
        dbname=os.getenv("ALBION_DB_NAME", "albion"),
        user=os.getenv("ALBION_DB_USER", "albion_app"),
        password=os.getenv("ALBION_DB_PASSWORD"),
    )


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
           AND a.year = 2026
           AND a.month BETWEEN 8 AND 12

        WHERE s.is_active = TRUE

        ORDER BY s.id, a.month
    """

    records = {}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

            for row in cur.fetchall():
                (
                    surface_id,
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
                    month,
                    raw_value,
                    db_status,
                    month_price,
                ) = row

                if surface_id not in records:
                    records[surface_id] = {
                        "id": surface_id,
                        "address": _text(address),
                        "city": _text(city),
                        "district": _text(district),
                        "lat": latitude,
                        "lng": longitude,
                        "map": _text(map_url),
                        "months": {},
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

                if month is not None and month in MONTHS:
                    month_name = MONTHS[month]
                    records[surface_id]["months"][month_name] = _text(
                        raw_value
                    )
                    records[surface_id]["statuses"][month_name] = _status(
                        db_status
                    )
                    records[surface_id].setdefault("month_prices", {})[
                        month_name
                    ] = _text(month_price)

    result = []

    for item in records.values():
        for month_name in MONTHS.values():
            item["months"].setdefault(month_name, "")
            item["statuses"].setdefault(month_name, "Свободно")
            item.setdefault("month_prices", {}).setdefault(month_name, "")

        result.append(item)

    return result


# --------------------------------------------------------------- кэш ответа

# Публичный /api/constructions отдаётся целиком и стоит ~100 мс CPU
# (SQL + сборка + сериализация). Данные меняются только при импорте,
# поэтому кэшируем сериализованное тело и повторно отдаём его с ETag.
# TTL — страховка на случай правок мимо импорта; основной сброс —
# invalidate_data_cache() после успешного импорта.
DATA_CACHE_TTL = float(os.environ.get("ALBION_DATA_CACHE_TTL", "30"))

_data_cache = {
    "ts": 0.0,
    "body": None,
    "etag": None,
}


def get_data_json() -> "tuple[bytes, str]":
    """Сериализованный /api/constructions: (тело, ETag)."""
    now = time.monotonic()
    cached = _data_cache

    if (
        cached["body"] is not None
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

    return body, etag


def invalidate_data_cache() -> None:
    """Сбросить кэш /api/constructions (вызывается после импорта)."""
    _data_cache["ts"] = 0.0
    _data_cache["body"] = None
    _data_cache["etag"] = None
