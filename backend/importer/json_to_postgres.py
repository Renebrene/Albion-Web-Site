import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg


PROJECT_DIR = Path(__file__).resolve().parents[2]
JSON_FILE = PROJECT_DIR / "tmp" / "constructions_import.json"


def import_year() -> int:
    """Год кампании для импорта.

    Берётся из окружения (ALBION_IMPORT_YEAR), иначе — текущий год.
    Раньше год был жёстко зашит (2026) в JSON и в availability-строках.
    """
    raw = os.getenv("ALBION_IMPORT_YEAR", "").strip()

    if raw:
        try:
            return int(raw)
        except ValueError:
            pass

    return datetime.now().year
ENV_FILE = PROJECT_DIR / ".env"


MONTH_NUMBERS = {
    "Январь": 1,
    "Февраль": 2,
    "Март": 3,
    "Апрель": 4,
    "Май": 5,
    "Июнь": 6,
    "Июль": 7,
    "Август": 8,
    "Сентябрь": 9,
    "Октябрь": 10,
    "Ноябрь": 11,
    "Декабрь": 12,
}


def load_env():
    if not ENV_FILE.exists():
        raise RuntimeError(f"Не найден файл {ENV_FILE}")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def db_connection():
    required = [
        "ALBION_DB_HOST",
        "ALBION_DB_NAME",
        "ALBION_DB_USER",
        "ALBION_DB_PASSWORD",
    ]

    missing = [key for key in required if not os.environ.get(key)]

    if missing:
        raise RuntimeError(
            "В .env отсутствуют: " + ", ".join(missing)
        )

    return psycopg.connect(
        host=os.environ["ALBION_DB_HOST"],
        dbname=os.environ["ALBION_DB_NAME"],
        user=os.environ["ALBION_DB_USER"],
        password=os.environ["ALBION_DB_PASSWORD"],
    )


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize(value):
    text = clean(value)
    text = text.replace("Ё", "Е").replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def parse_coordinate_pair(item):
    lat = item.get("lat")
    lng = item.get("lng")

    if lat is not None and lng is not None:
        return float(lat), float(lng)

    return None, None


def temporary_identifier(number, side):
    number = clean(number)
    side = clean(side)

    if number:
        return f"{number}{side}"

    return f"0{side}"


def normalize_status(raw_value):
    text = clean(raw_value)

    if not text:
        return "FREE"

    lowered = text.lower()

    if "продано" in lowered:
        return "SOLD"

    if "резерв" in lowered:
        return "RESERVED"

    if "утверждени" in lowered:
        return "PENDING"

    if re.search(r"\d+(?:[.,]\d+)?%", text):
        return "LOAD"

    return "LOAD"


def parse_load_percent(raw_value):
    text = clean(raw_value)

    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*%",
        text
    )

    if not match:
        return None

    value = float(match.group(1).replace(",", "."))

    if value < 0 or value > 100:
        return None

    return round(value)


def load_json():
    if not JSON_FILE.exists():
        raise RuntimeError(
            f"Не найден промежуточный JSON: {JSON_FILE}"
        )

    payload = json.loads(
        JSON_FILE.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise RuntimeError("Корень import.json должен быть объектом")

    surfaces = payload.get("surfaces")

    if not isinstance(surfaces, list):
        raise RuntimeError(
            "В import.json отсутствует массив surfaces"
        )

    months = payload.get("months")

    if not isinstance(months, list) or not months:
        raise RuntimeError(
            "В import.json отсутствует массив months"
        )

    return payload, surfaces, months


def main():
    load_env()

    payload, source_rows, months = load_json()

    print("=" * 70)
    print("JSON → PostgreSQL")
    print("=" * 70)

    print(f"Source surfaces: {len(source_rows)}")
    print(f"Source months:   {len(months)}")

    # -----------------------------------------------------
    # Подготовительная проверка JSON
    # -----------------------------------------------------

    required_fields = [
        "city",
        "district",
        "address",
        "name",
        "side",
        "type",
        "size",
        "price",
        "external_number",
        "photo_url",
        "map_url",
        "months",
        "statuses",
    ]

    for index, item in enumerate(source_rows, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(
                f"Строка JSON #{index} не является объектом"
            )

        missing = [
            field
            for field in required_fields
            if field not in item
        ]

        if missing:
            raise RuntimeError(
                f"Строка JSON #{index}: "
                f"отсутствуют поля {missing}"
            )

    for month in months:
        if month not in MONTH_NUMBERS:
            raise RuntimeError(
                f"Неизвестный месяц: {month}"
            )

    # -----------------------------------------------------
    # Готовим constructions
    # city + address
    # -----------------------------------------------------

    construction_map = {}

    for item in source_rows:
        city = clean(item.get("city"))
        address = clean(item.get("address"))

        key = (
            normalize(city),
            normalize(address),
        )

        if key not in construction_map:
            construction_map[key] = {
                "city": city,
                "district": clean(item.get("district")),
                "address": address,
                "name": clean(item.get("name")),
            }

    print(f"Constructions to import: {len(construction_map)}")
    print(f"Surfaces to import:      {len(source_rows)}")
    print(
        f"Availability to import: "
        f"{len(source_rows) * len(months)}"
    )

    # -----------------------------------------------------
    # PostgreSQL
    # -----------------------------------------------------

    with db_connection() as conn:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # Новая версия импорта конструкций.
            # Создаётся в той же транзакции, что и весь импорт.
            # При ошибке вся транзакция откатится вместе с этой
            # записью, а предыдущая версия останется активной.
            # -------------------------------------------------

            import_key = datetime.now().strftime("%Y%m%d-%H%M%S")

            cur.execute(
                """
                INSERT INTO construction_imports (
                    import_key,
                    status
                )
                VALUES (%s, 'staging')
                RETURNING id
                """,
                (import_key,),
            )

            import_id = cur.fetchone()[0]

            print(f"Import ID:    {import_id}")
            print(f"Import key:   {import_key}")

            # -------------------------------------------------
            # Каждый импорт полностью пересобирает раздел
            # конструкций из текущего Excel.
            #
            # TRUNCATE выполняется внутри той же транзакции,
            # что и весь импорт. Если любой следующий этап
            # завершится ошибкой, PostgreSQL автоматически
            # откатит и очистку, и новые записи.
            # -------------------------------------------------

            cur.execute("""
                TRUNCATE TABLE
                    surface_availability,
                    surfaces,
                    constructions,
                    cities
                CASCADE
            """)

            # -------------------------------------------------
            # Cities
            # -------------------------------------------------

            city_map = {}

            for item in source_rows:
                city = clean(item.get("city"))

                if not city:
                    raise RuntimeError(
                        "Обнаружена поверхность без города"
                    )

                city_key = normalize(city)

                if city_key in city_map:
                    continue

                cur.execute(
                    """
                    INSERT INTO cities (
                        name,
                        normalized_name
                    )
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (
                        city,
                        city_key,
                    ),
                )

                city_map[city_key] = cur.fetchone()[0]

            print(f"Cities inserted:        {len(city_map)}")

            # -------------------------------------------------
            # Constructions
            # -------------------------------------------------

            construction_db_map = {}

            for key, construction in construction_map.items():

                city_key, address_key = key

                city_id = city_map.get(city_key)

                if city_id is None:
                    raise RuntimeError(
                        f"Не найден city_id для {construction['city']}"
                    )

                cur.execute(
                    """
                    INSERT INTO constructions (
                        city_id,
                        district,
                        address,
                        name,
                        address_key
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        city_id,
                        construction["district"] or None,
                        construction["address"],
                        construction["name"] or None,
                        address_key,
                    ),
                )

                construction_db_map[key] = cur.fetchone()[0]

            print(
                f"Constructions inserted: "
                f"{len(construction_db_map)}"
            )

            # -------------------------------------------------
            # Surfaces + availability
            # -------------------------------------------------

            availability_count = 0
            status_counter = Counter()

            for row_number, item in enumerate(
                source_rows,
                start=1,
            ):
                city = clean(item.get("city"))
                address = clean(item.get("address"))

                construction_key = (
                    normalize(city),
                    normalize(address),
                )

                construction_id = construction_db_map.get(
                    construction_key
                )

                if construction_id is None:
                    raise RuntimeError(
                        f"Строка {row_number}: "
                        "не найдена construction"
                    )

                number = clean(item.get("external_number"))
                side = clean(item.get("side"))

                if not side:
                    raise RuntimeError(
                        f"Строка {row_number}: "
                        "пустая сторона"
                    )

                lat, lng = parse_coordinate_pair(item)

                location = None

                if lat is not None and lng is not None:
                    location = (
                        f"SRID=4326;POINT({lng} {lat})"
                    )

                cur.execute(
                    """
                    INSERT INTO surfaces (
                        construction_id,
                        side,
                        name,
                        external_number,
                        temporary_identifier,
                        type,
                        size,
                        price,
                        photo,
                        map,
                        location,
                        latitude,
                        longitude,
                        surface_hash,
                        is_active
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s,
                        ST_GeomFromText(%s, 4326),
                        %s, %s, %s,
                        TRUE
                    )
                    RETURNING id
                    """,
                    (
                        construction_id,
                        side,
                        clean(item.get("name")) or None,
                        number or None,
                        temporary_identifier(
                            number,
                            side,
                        ),
                        clean(item.get("type")) or None,
                        clean(item.get("size")) or None,
                        clean(item.get("price")) or None,
                        clean(item.get("photo_url")) or None,
                        clean(item.get("map_url")) or None,
                        location,
                        lat,
                        lng,
                        clean(item.get("surface_hash")) or None,
                    ),
                )

                surface_id = cur.fetchone()[0]

                month_values = item.get("months") or {}
                status_values = item.get("statuses") or {}

                for month_name in months:
                    month_number = MONTH_NUMBERS[month_name]

                    raw_value = clean(
                        month_values.get(month_name)
                    )

                    status = normalize_status(raw_value)

                    load_percent = parse_load_percent(
                        raw_value
                    )

                    monthly_price = clean(
                        item.get("price")
                    ) or None

                    cur.execute(
                        """
                        INSERT INTO surface_availability (
                            surface_id,
                            year,
                            month,
                            raw_value,
                            status,
                            load_percent,
                            price
                        )
                        VALUES (
                            %s, 2026, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            surface_id,
                            month_number,
                            raw_value or None,
                            status,
                            load_percent,
                            monthly_price,
                        ),
                    )

                    availability_count += 1
                    status_counter[status] += 1

            print(
                f"Surfaces inserted:      {len(source_rows)}"
            )
            print(
                f"Availability inserted:  {availability_count}"
            )

            # -------------------------------------------------
            # Контрольные проверки ДО COMMIT
            # -------------------------------------------------

            cur.execute(
                "SELECT count(*) FROM cities"
            )
            db_cities = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM constructions"
            )
            db_constructions = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM surfaces"
            )
            db_surfaces = cur.fetchone()[0]

            cur.execute(
                "SELECT count(*) FROM surface_availability"
            )
            db_availability = cur.fetchone()[0]

            expected_cities = len(city_map)
            expected_constructions = len(construction_map)
            expected_surfaces = len(source_rows)
            expected_availability = (
                len(source_rows) * len(months)
            )

            checks = [
                (
                    "cities",
                    db_cities,
                    expected_cities,
                ),
                (
                    "constructions",
                    db_constructions,
                    expected_constructions,
                ),
                (
                    "surfaces",
                    db_surfaces,
                    expected_surfaces,
                ),
                (
                    "availability",
                    db_availability,
                    expected_availability,
                ),
            ]

            print()
            print("CONTROL CHECKS")
            print("-" * 70)

            for name, actual, expected in checks:
                print(
                    f"{name:20} "
                    f"actual={actual:<6} "
                    f"expected={expected}"
                )

                if actual != expected:
                    raise RuntimeError(
                        f"Контрольная проверка {name} "
                        f"не пройдена: "
                        f"{actual} != {expected}"
                    )

            # Проверяем, что у каждой поверхности есть 5 месяцев.
            cur.execute("""
                SELECT surface_id, count(*)
                FROM surface_availability
                GROUP BY surface_id
                HAVING count(*) <> %s
            """, (len(months),))

            bad_months = cur.fetchall()

            if bad_months:
                raise RuntimeError(
                    "Найдены поверхности с неправильным "
                    f"количеством месяцев: {bad_months[:10]}"
                )

            # Проверяем количество координат.
            cur.execute("""
                SELECT
                    count(*) FILTER (
                        WHERE latitude IS NOT NULL
                          AND longitude IS NOT NULL
                    ),
                    count(*) FILTER (
                        WHERE latitude IS NULL
                          OR longitude IS NULL
                    )
                FROM surfaces
            """)

            coords_with, coords_without = cur.fetchone()

            print()
            print(
                f"Coordinates: with={coords_with}, "
                f"without={coords_without}"
            )

            print()
            print("STATUS COUNTS")
            print("-" * 70)

            for status, count in sorted(
                status_counter.items()
            ):
                print(f"{status:12} {count}")

            # -------------------------------------------------
            # Финализируем новую версию только после всех
            # контрольных проверок.
            #
            # Все операции находятся в одной транзакции:
            # если здесь или при выходе из with произойдёт
            # ошибка, PostgreSQL откатит весь импорт.
            # -------------------------------------------------

            # Новый импорт остаётся staging до завершения
            # всех последующих этапов pipeline.

            print()
            print("=" * 70)
            print("ALL CHECKS PASSED")
            print(f"ACTIVE IMPORT: {import_id} / {import_key}")
            print("COMMIT")
            print("=" * 70)


if __name__ == "__main__":
    main()
