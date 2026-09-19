import os
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
            s.photo,
            s.price,
            s.side,
            s.size,
            s.type,

            a.month,
            a.raw_value,
            a.status

        FROM surfaces s
        JOIN constructions c
            ON c.id = s.construction_id
        JOIN cities ci
            ON ci.id = c.city_id
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
                    photo,
                    price,
                    side,
                    size,
                    media_type,
                    month,
                    raw_value,
                    db_status,
                ) = row

                if surface_id not in records:
                    records[surface_id] = {
                        "address": _text(address),
                        "city": _text(city),
                        "district": _text(district),
                        "lat": latitude,
                        "lng": longitude,
                        "map": _text(map_url),
                        "months": {},
                        "name": _text(name),
                        "number": _text(external_number),
                        "photo": _text(photo),
                        "price": _text(price),
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

    result = []

    for item in records.values():
        for month_name in MONTHS.values():
            item["months"].setdefault(month_name, "")
            item["statuses"].setdefault(month_name, "Свободно")

        result.append(item)

    return result
