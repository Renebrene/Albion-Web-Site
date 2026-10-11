from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .json_to_postgres import (
    clean,
    import_year,
    normalize,
    normalize_status,
    parse_coordinate_pair,
    parse_load_percent,
    temporary_identifier,
    MONTH_NUMBERS,
)


def address_key_of(value: Any) -> str:
    """Ключ адреса без различий форматирования («/ », «п. »).

    «20В / Добровольского 9А п. 1» и «20В/Добровольского 9А п.1»
    должны давать один и тот же ключ.
    """
    text = normalize(value)
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\bп\.\s*", "п.", text)
    return text.strip()


def number_key_of(value: Any) -> str:
    """Номер конструкции входит в ключ: разные номера — разные конструкции."""
    return normalize(value)


PROJECT_DIR = Path(__file__).resolve().parents[2]
TMP_DIR = PROJECT_DIR / "tmp"
JSON_FILE = TMP_DIR / "constructions_import.json"


def create_database(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript(
        """
        CREATE TABLE cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE constructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            district TEXT,
            address TEXT NOT NULL,
            name TEXT,
            address_key TEXT NOT NULL,
            FOREIGN KEY (city_id) REFERENCES cities(id)
        );

        CREATE TABLE surfaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            construction_id INTEGER NOT NULL,
            side TEXT NOT NULL,
            name TEXT,
            external_number TEXT,
            temporary_identifier TEXT,
            type TEXT,
            size TEXT,
            price TEXT,
            light TEXT,
            material TEXT,
            photo_url TEXT,
            map_url TEXT,
            latitude REAL,
            longitude REAL,
            surface_hash TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (construction_id) REFERENCES constructions(id)
        );

        CREATE TABLE surface_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surface_id INTEGER NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            raw_value TEXT,
            status TEXT NOT NULL,
            load_percent REAL,
            price TEXT,
            FOREIGN KEY (surface_id) REFERENCES surfaces(id)
        );

        CREATE TABLE import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            stage TEXT NOT NULL,
            code TEXT NOT NULL,
            message TEXT NOT NULL,
            source_row INTEGER,
            surface_hash TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_import_log_level
            ON import_log(level);

        CREATE INDEX idx_import_log_stage
            ON import_log(stage);

        CREATE INDEX idx_import_log_code
            ON import_log(code);

        CREATE INDEX idx_import_log_surface_hash
            ON import_log(surface_hash);

        CREATE INDEX idx_constructions_city
            ON constructions(city_id);

        CREATE INDEX idx_surfaces_construction
            ON surfaces(construction_id);

        CREATE INDEX idx_surfaces_hash
            ON surfaces(surface_hash);

        CREATE INDEX idx_availability_surface
            ON surface_availability(surface_id);
        """
    )

    return conn


def log_import_event(
    conn: sqlite3.Connection,
    *,
    level: str,
    stage: str,
    code: str,
    message: str,
    source_row: int | None = None,
    surface_hash: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO import_log (
            level,
            stage,
            code,
            message,
            source_row,
            surface_hash
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            level,
            stage,
            code,
            message,
            source_row,
            surface_hash,
        ),
    )


def load_json() -> dict[str, Any]:
    if not JSON_FILE.exists():
        raise RuntimeError(
            f"JSON-файл не найден: {JSON_FILE}"
        )

    return json.loads(
        JSON_FILE.read_text(encoding="utf-8")
    )


def validate_source(payload: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    months = payload.get("months") or []
    source_rows = payload.get("surfaces") or []

    if not isinstance(months, list):
        raise RuntimeError("Поле months должно быть списком")

    if not isinstance(source_rows, list):
        raise RuntimeError("Поле surfaces должно быть списком")

    for month in months:
        if month not in MONTH_NUMBERS:
            raise RuntimeError(
                f"Неизвестный месяц: {month}"
            )

    required_fields = [
        "city",
        "district",
        "address",
        "name",
        "side",
        "external_number",
        "type",
        "size",
        "price",
        "photo_url",
        "map_url",
        "latitude",
        "longitude",
        "surface_hash",
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
                f"Строка JSON #{index}: отсутствуют поля {missing}"
            )

    return months, source_rows


def populate(
    conn: sqlite3.Connection,
    months: list[str],
    source_rows: list[dict[str, Any]],
) -> Counter:
    construction_map: dict[tuple[str, str, str], dict[str, str]] = {}

    for item in source_rows:
        city = clean(item.get("city"))
        address = clean(item.get("address"))

        key = (
            normalize(city),
            address_key_of(address),
            number_key_of(item.get("external_number")),
        )

        if key not in construction_map:
            construction_map[key] = {
                "city": city,
                "district": clean(item.get("district")),
                "address": address,
                "name": clean(item.get("name")),
            }

    city_map: dict[str, int] = {}

    for item in source_rows:
        city = clean(item.get("city"))

        if not city:
            raise RuntimeError("Обнаружена поверхность без города")

        city_key = normalize(city)

        if city_key in city_map:
            continue

        cur = conn.execute(
            """
            INSERT INTO cities (
                name,
                normalized_name
            )
            VALUES (?, ?)
            """,
            (city, city_key),
        )

        city_map[city_key] = cur.lastrowid

    construction_db_map: dict[tuple[str, str, str], int] = {}

    for key, construction in construction_map.items():
        city_key, address_key, _number_key = key
        city_id = city_map.get(city_key)

        if city_id is None:
            raise RuntimeError(
                f"Не найден city_id для {construction['city']}"
            )

        cur = conn.execute(
            """
            INSERT INTO constructions (
                city_id,
                district,
                address,
                name,
                address_key
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                city_id,
                construction["district"] or None,
                construction["address"],
                construction["name"] or None,
                address_key,
            ),
        )

        construction_db_map[key] = cur.lastrowid

    status_counter = Counter()
    seen_surface_hashes: set[str] = set()
    skipped_duplicates = 0

    for row_number, item in enumerate(source_rows, start=1):
        city = clean(item.get("city"))
        address = clean(item.get("address"))

        construction_key = (
            normalize(city),
            address_key_of(address),
            number_key_of(item.get("external_number")),
        )

        construction_id = construction_db_map.get(
            construction_key
        )

        if construction_id is None:
            raise RuntimeError(
                f"Строка {row_number}: не найдена construction"
            )

        number = clean(item.get("external_number"))
        side = clean(item.get("side"))

        if not side:
            raise RuntimeError(
                f"Строка {row_number}: пустая сторона"
            )

        lat = item.get("latitude")
        lng = item.get("longitude")

        if lat is not None:
            lat = float(lat)

        if lng is not None:
            lng = float(lng)

        surface_hash = clean(item.get("surface_hash"))

        if surface_hash in seen_surface_hashes:
            skipped_duplicates += 1

            log_import_event(
                conn,
                level="warning",
                stage="staging",
                code="DUPLICATE_SURFACE_HASH",
                message=(
                    f"Дубликат surface_hash пропущен: "
                    f"строка JSON #{row_number}; "
                    f"адрес={address}; "
                    f"сторона={side}; "
                    f"№={number or '-'}"
                ),
                source_row=row_number,
                surface_hash=surface_hash,
            )

            continue

        seen_surface_hashes.add(surface_hash)

        cur = conn.execute(
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
                light,
                material,
                photo_url,
                map_url,
                latitude,
                longitude,
                surface_hash,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                construction_id,
                side,
                clean(item.get("name")) or None,
                number or None,
                temporary_identifier(number, side),
                clean(item.get("type")) or None,
                clean(item.get("size")) or None,
                clean(item.get("price")) or None,
                clean(item.get("light")) or None,
                clean(item.get("material")) or None,
                clean(item.get("photo_url")) or None,
                clean(item.get("map_url")) or None,
                lat,
                lng,
                clean(item.get("surface_hash")) or None,
            ),
        )

        surface_id = cur.lastrowid

        month_values = item.get("months") or {}

        for month_name in months:
            month_number = MONTH_NUMBERS[month_name]

            raw_value = clean(
                month_values.get(month_name)
            )

            status = normalize_status(raw_value)
            load_percent = parse_load_percent(raw_value)

            monthly_price = clean(
                item.get("price")
            ) or None

            conn.execute(
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    surface_id,
                    import_year(),
                    month_number,
                    raw_value or None,
                    status,
                    load_percent,
                    monthly_price,
                ),
            )

            status_counter[status] += 1

    return status_counter, skipped_duplicates


def run() -> Path:
    payload = load_json()
    months, source_rows = validate_source(payload)

    import_key = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    db_path = (
        TMP_DIR
        / "import"
        / import_key
        / "staging.sqlite"
    )

    print("=" * 70)
    print("ALBION SQLITE STAGING")
    print("=" * 70)
    print(f"JSON:        {JSON_FILE}")
    print(f"Staging DB:  {db_path}")
    print(f"Surfaces:    {len(source_rows)}")
    print(f"Months:      {len(months)}")

    conn = create_database(db_path)

    try:
        status_counter, skipped_duplicates = populate(
            conn,
            months,
            source_rows,
        )

        db_cities = conn.execute(
            "SELECT count(*) FROM cities"
        ).fetchone()[0]

        db_constructions = conn.execute(
            "SELECT count(*) FROM constructions"
        ).fetchone()[0]

        db_surfaces = conn.execute(
            "SELECT count(*) FROM surfaces"
        ).fetchone()[0]

        db_availability = conn.execute(
            "SELECT count(*) FROM surface_availability"
        ).fetchone()[0]

        expected_cities = len({
            normalize(clean(item.get("city")))
            for item in source_rows
        })

        expected_constructions = len({
            (
                normalize(clean(item.get("city"))),
                address_key_of(clean(item.get("address"))),
                number_key_of(item.get("external_number")),
            )
            for item in source_rows
        })

        expected_surfaces = len(source_rows) - skipped_duplicates
        expected_availability = (
            expected_surfaces * len(months)
        )

        checks = [
            ("cities", db_cities, expected_cities),
            (
                "constructions",
                db_constructions,
                expected_constructions,
            ),
            ("surfaces", db_surfaces, expected_surfaces),
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
                    f"не пройдена: {actual} != {expected}"
                )

        bad_months = conn.execute(
            """
            SELECT surface_id, count(*)
            FROM surface_availability
            GROUP BY surface_id
            HAVING count(*) <> ?
            """,
            (len(months),),
        ).fetchall()

        if bad_months:
            raise RuntimeError(
                "Найдены поверхности с неправильным "
                f"количеством месяцев: {bad_months[:10]}"
            )

        coords_with, coords_without = conn.execute(
            """
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
            """
        ).fetchone()

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
            print(f"{status:20} {count}")

        conn.commit()

        print()
        print("=" * 70)
        print("STAGING READY")
        print(f"SQLite: {db_path}")
        print("PostgreSQL: НЕ ИЗМЕНЁН")
        print("=" * 70)

        return db_path

    except Exception:
        conn.rollback()
        if db_path.exists():
            db_path.unlink()
        raise

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Создание SQLite staging из import.json"
    )
    parser.parse_args()

    run()


if __name__ == "__main__":
    main()
