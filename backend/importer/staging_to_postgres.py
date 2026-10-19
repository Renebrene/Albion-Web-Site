from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path

import psycopg
from psycopg.types.json import Json


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_DB = PROJECT_DIR / "tmp" / "import"

# Таблицы, которые полностью пересоздаются импортом. После COMMIT
# autovacuum может обновить статистику не сразу, поэтому ANALYZE выполняем
# явно, пока транзакция импорта ещё открыта: планировщик получает свежие
# оценки сразу после загрузки.
ANALYZE_TABLES = (
    "construction_imports",
    "cities",
    "constructions",
    "surfaces",
    "surface_availability",
    "construction_media",
)


def analyze_loaded_tables(conn) -> None:
    conn.execute("ANALYZE " + ", ".join(ANALYZE_TABLES))


def db_connection():
    return psycopg.connect(
        host=os.getenv("ALBION_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("ALBION_DB_PORT", "5432")),
        dbname=os.getenv("ALBION_DB_NAME", "albion"),
        user=os.getenv("ALBION_DB_USER", "albion_app"),
        password=os.getenv("ALBION_DB_PASSWORD"),
    )


def find_staging_db() -> Path:
    configured = os.getenv("ALBION_STAGING_DB")

    if configured:
        path = Path(configured)
        if not path.exists():
            raise RuntimeError(f"Staging DB не найден: {path}")
        return path

    candidates = list(DEFAULT_STAGING_DB.glob("*/staging.sqlite"))

    if not candidates:
        raise RuntimeError(
            f"Staging DB не найден в {DEFAULT_STAGING_DB}"
        )

    return max(candidates, key=lambda path: path.stat().st_mtime)


def open_staging_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def validate_staging(conn: sqlite3.Connection) -> dict[str, int]:
    checks = {
        "cities": "SELECT COUNT(*) FROM cities",
        "constructions": "SELECT COUNT(*) FROM constructions",
        "surfaces": "SELECT COUNT(*) FROM surfaces",
        "availability": (
            "SELECT COUNT(*) FROM surface_availability"
        ),
        "warnings": (
            "SELECT COUNT(*) FROM import_log "
            "WHERE level = 'warning'"
        ),
        "errors": (
            "SELECT COUNT(*) FROM import_log "
            "WHERE level = 'error'"
        ),
    }

    result = {
        name: int(conn.execute(sql).fetchone()[0])
        for name, sql in checks.items()
    }

    if result["surfaces"] == 0:
        raise RuntimeError("Staging не содержит surfaces")

    if result["errors"] > 0:
        raise RuntimeError(
            f"В staging обнаружены ошибки: {result['errors']}"
        )

    return result


def validate_surface_hashes(conn: sqlite3.Connection) -> None:
    row = conn.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT surface_hash
            FROM surfaces
            GROUP BY surface_hash
            HAVING COUNT(*) > 1
        )
    """).fetchone()

    if int(row[0]):
        raise RuntimeError(
            f"Найдены дубли surface_hash: {row[0]}"
        )

    row = conn.execute("""
        SELECT COUNT(*)
        FROM surfaces
        WHERE surface_hash IS NULL
           OR TRIM(surface_hash) = ''
    """).fetchone()

    if int(row[0]):
        raise RuntimeError(
            f"Surfaces без surface_hash: {row[0]}"
        )


def validate_availability(conn: sqlite3.Connection) -> None:
    row = conn.execute("""
        SELECT COUNT(*)
        FROM surface_availability a
        LEFT JOIN surfaces s
          ON s.id = a.surface_id
        WHERE s.id IS NULL
    """).fetchone()

    if int(row[0]):
        raise RuntimeError(
            f"Availability без surface: {row[0]}"
        )


def read_media_plan(staging_path: Path) -> dict:
    plan_path = (
        staging_path.parent / "media_plan.json"
    )

    if not plan_path.exists():
        raise RuntimeError(
            f"media_plan.json не найден: {plan_path}. "
            "Запустите construction_media_download "
            "перед загрузкой в PostgreSQL."
        )

    return json.loads(
        plan_path.read_text(encoding="utf-8"),
    )


def validate_media_files(
    staging_path: Path,
) -> dict[str, int]:
    """
    Проверяет результат media-плана:
    REUSE и успешно скачанные media должны иметь
    large/card/thumb preview в storage новой версии.

    Media с ошибкой скачивания не блокируют импорт:
    для них просто не будет записи construction_media.
    """
    plan = read_media_plan(staging_path)
    entries: list[dict] = plan["entries"]

    expected = len(entries)
    reuse = sum(
        1
        for entry in entries
        if entry["decision"] == "reuse"
    )
    downloaded = sum(
        1
        for entry in entries
        if entry["decision"] == "download"
        and entry["status"] == "ok"
    )
    failed = sum(
        1
        for entry in entries
        if entry["decision"] == "download"
        and entry["status"] == "error"
    )
    missing_previews = 0

    for entry in entries:
        if entry["status"] != "ok":
            continue

        paths: dict = entry.get("paths") or {}

        for variant in ("large", "card", "thumb"):
            relative = paths.get(variant)

            if not relative:
                missing_previews += 1
                break

            if not (PROJECT_DIR / relative).is_file():
                missing_previews += 1
                break

    return {
        "media_tasks": expected,
        "media_reuse": reuse,
        "media_downloaded": downloaded,
        "media_successful": reuse + downloaded,
        "media_failed": failed,
        "missing_previews": missing_previews,
    }


def validate_postgres_state(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM construction_imports
            WHERE status = 'active'
        """)
        active_count = int(cur.fetchone()[0])

        # 0 допустимо — это первый импорт «с нуля» (active-версии ещё нет).
        # Больше одной active-версии быть не должно.
        if active_count > 1:
            raise RuntimeError(
                "Ожидался один active construction import (или ни одного "
                f"при первом импорте), получено: {active_count}"
            )


def create_import(conn, import_key: str) -> int:
    with conn.cursor() as cur:
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
        return int(cur.fetchone()[0])


def load_cities(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
) -> dict[int, int]:
    mapping: dict[int, int] = {}

    rows = sqlite_conn.execute("""
        SELECT id, name, normalized_name
        FROM cities
        ORDER BY id
    """).fetchall()

    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                SELECT id
                FROM cities
                WHERE normalized_name = %s
                """,
                (row["normalized_name"],),
            )
            existing = cur.fetchone()

            if existing:
                mapping[int(row["id"])] = int(existing[0])
                continue

            cur.execute(
                """
                INSERT INTO cities (
                    uuid,
                    name,
                    normalized_name,
                    is_active
                )
                VALUES (%s, %s, %s, TRUE)
                RETURNING id
                """,
                (
                    uuid.uuid4(),
                    row["name"],
                    row["normalized_name"],
                ),
            )
            mapping[int(row["id"])] = int(cur.fetchone()[0])

    return mapping


def load_constructions(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    city_map: dict[int, int],
) -> dict[int, int]:
    mapping: dict[int, int] = {}

    rows = sqlite_conn.execute("""
        SELECT
            id,
            city_id,
            district,
            address,
            name,
            address_key
        FROM constructions
        ORDER BY id
    """).fetchall()

    with pg_conn.cursor() as cur:
        for row in rows:
            city_id = city_map.get(int(row["city_id"]))

            if city_id is None:
                raise RuntimeError(
                    f"Не найден city mapping: "
                    f"{row['city_id']}"
                )

            cur.execute(
                """
                INSERT INTO constructions (
                    uuid,
                    city_id,
                    district,
                    address,
                    name,
                    address_key,
                    is_active
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, TRUE
                )
                RETURNING id
                """,
                (
                    uuid.uuid4(),
                    city_id,
                    row["district"],
                    row["address"],
                    row["name"],
                    row["address_key"],
                ),
            )

            mapping[int(row["id"])] = int(cur.fetchone()[0])

    return mapping


def load_surfaces(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    construction_map: dict[int, int],
) -> dict[int, int]:
    mapping: dict[int, int] = {}

    rows = sqlite_conn.execute("""
        SELECT
            id,
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
            surface_hash
        FROM surfaces
        ORDER BY id
    """).fetchall()

    with pg_conn.cursor() as cur:
        for row in rows:
            construction_id = construction_map.get(
                int(row["construction_id"])
            )

            if construction_id is None:
                raise RuntimeError(
                    "Не найден construction mapping: "
                    f"{row['construction_id']}"
                )

            latitude = row["latitude"]
            longitude = row["longitude"]

            if latitude is not None and longitude is not None:
                location = (
                    f"SRID=4326;POINT("
                    f"{longitude} {latitude})"
                )
            else:
                location = None

            cur.execute(
                """
                INSERT INTO surfaces (
                    uuid,
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
                    photo,
                    map,
                    location,
                    latitude,
                    longitude,
                    surface_hash,
                    is_active
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s,
                    CASE
                        WHEN %s::text IS NULL THEN NULL
                        ELSE ST_GeomFromText(%s::text, 4326)
                    END,
                    %s, %s, %s, TRUE
                )
                RETURNING id
                """,
                (
                    uuid.uuid4(),
                    construction_id,
                    row["side"],
                    row["name"],
                    row["external_number"],
                    row["temporary_identifier"],
                    row["type"],
                    row["size"],
                    row["price"],
                    row["light"],
                    row["material"],
                    row["photo_url"],
                    row["map_url"],
                    location,
                    location,
                    latitude,
                    longitude,
                    row["surface_hash"],
                ),
            )

            mapping[int(row["id"])] = int(cur.fetchone()[0])

    return mapping


def load_availability(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    surface_map: dict[int, int],
) -> int:
    rows = sqlite_conn.execute("""
        SELECT
            surface_id,
            year,
            month,
            raw_value,
            status,
            load_percent,
            price
        FROM surface_availability
        ORDER BY surface_id, year, month
    """).fetchall()

    with pg_conn.cursor() as cur:
        for row in rows:
            surface_id = surface_map.get(
                int(row["surface_id"])
            )

            if surface_id is None:
                raise RuntimeError(
                    "Не найден surface mapping: "
                    f"{row['surface_id']}"
                )

            cur.execute(
                """
                INSERT INTO surface_availability (
                    uuid,
                    surface_id,
                    year,
                    month,
                    raw_value,
                    status,
                    load_percent,
                    price,
                    is_active
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, TRUE
                )
                """,
                (
                    uuid.uuid4(),
                    surface_id,
                    row["year"],
                    row["month"],
                    row["raw_value"],
                    row["status"],
                    row["load_percent"],
                    row["price"],
                ),
            )

    return len(rows)


def load_media(
    staging_path: Path,
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    import_id: int,
    surface_map: dict[int, int],
) -> dict[str, int]:
    """
    Создаёт construction_media для новой версии импорта
    из media_plan.json.

    - REUSE переносит записи старой ACTIVE версии;
    - DOWNLOAD берёт только успешно скачанные media;
    - media с ошибкой скачивания пропускаются
      (без fallback на старое медиа).
    """
    plan = read_media_plan(staging_path)
    entries: list[dict] = plan["entries"]

    inserted = 0
    skipped_errors = 0
    skipped_no_surface = 0

    with pg_conn.cursor() as cur:
        for entry in entries:
            if entry["status"] != "ok":
                skipped_errors += 1
                continue

            surface_id = surface_map.get(
                int(entry["surface_id"])
            )

            if surface_id is None:
                skipped_no_surface += 1
                continue

            paths: dict = entry.get("paths") or {}

            cur.execute(
                """
                INSERT INTO construction_media (
                    uuid,
                    import_id,
                    surface_id,
                    surface_hash,
                    media_type,
                    original_url,
                    original_name,
                    mime_type,
                    file_size,
                    width,
                    height,
                    large_path,
                    card_path,
                    thumb_path
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    uuid.uuid4(),
                    import_id,
                    surface_id,
                    entry["surface_hash"],
                    entry["media_type"],
                    entry["url"],
                    entry.get("original_name"),
                    entry.get("mime_type"),
                    entry.get("file_size"),
                    entry.get("width"),
                    entry.get("height"),
                    paths.get("large"),
                    paths.get("card"),
                    paths.get("thumb"),
                ),
            )

            inserted += 1

    return {
        "inserted": inserted,
        "skipped_errors": skipped_errors,
        "skipped_no_surface": skipped_no_surface,
    }


def write_load_result(import_key: str, result: dict) -> None:
    result_path = (
        PROJECT_DIR
        / "tmp"
        / "import"
        / import_key
        / "load_result.json"
    )

    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def perform_load(
    staging_path: Path,
    sqlite_conn: sqlite3.Connection,
    pg_conn,
) -> dict[str, int | str | None]:
    import_key = staging_path.parent.name

    import_id = create_import(
        pg_conn,
        import_key,
    )

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT import_key
            FROM construction_imports
            WHERE status = 'active'
            """
        )
        row = cur.fetchone()
        old_active_import_key = row[0] if row else None

        cur.execute(
            """
            UPDATE construction_imports
            SET status = 'obsolete',
                finished_at = NOW()
            WHERE status = 'active'
            """
        )

        cur.execute(
            """
            DELETE FROM constructions
            WHERE is_active = TRUE
            """
        )

    city_map = load_cities(
        sqlite_conn,
        pg_conn,
    )

    construction_map = load_constructions(
        sqlite_conn,
        pg_conn,
        city_map,
    )

    surface_map = load_surfaces(
        sqlite_conn,
        pg_conn,
        construction_map,
    )

    availability_count = load_availability(
        sqlite_conn,
        pg_conn,
        surface_map,
    )

    media_result = load_media(
        staging_path,
        sqlite_conn,
        pg_conn,
        import_id,
        surface_map,
    )

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE construction_imports
            SET status = 'active',
                finished_at = NOW()
            WHERE id = %s
            """,
            (import_id,),
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM constructions
            WHERE is_active = TRUE
            """
        )
        constructions = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(*)
            FROM surfaces
            WHERE is_active = TRUE
            """
        )
        surfaces = int(cur.fetchone()[0])

        cur.execute(
            """
            SELECT COUNT(*)
            FROM surface_availability
            WHERE is_active = TRUE
            """
        )
        availability = int(cur.fetchone()[0])

    return {
        "import_id": import_id,
        "constructions": constructions,
        "surfaces": surfaces,
        "availability": availability,
        "media": media_result["inserted"],
        "media_skipped_errors": (
            media_result["skipped_errors"]
        ),
        "media_skipped_no_surface": (
            media_result["skipped_no_surface"]
        ),
        "old_active_import_key": old_active_import_key,
    }


def main() -> None:
    staging_path = find_staging_db()

    dry_run = os.getenv(
        "ALBION_IMPORT_DRY_RUN",
        "1",
    ) != "0"

    print("=" * 70)
    print("SQLITE STAGING → POSTGRESQL")
    print("=" * 70)
    print(f"Staging DB: {staging_path}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'COMMIT'}")

    sqlite_conn = open_staging_db(staging_path)

    try:
        stats = validate_staging(sqlite_conn)
        validate_surface_hashes(sqlite_conn)
        validate_availability(sqlite_conn)

        media = validate_media_files(
            staging_path,
        )

        if media["missing_previews"]:
            raise RuntimeError(
                "Не все успешные media имеют "
                "large/card/thumb"
            )

        print()
        print("PRE-CHECK")
        print("-" * 70)

        for name in (
            "cities",
            "constructions",
            "surfaces",
            "availability",
            "warnings",
            "errors",
        ):
            print(f"{name:24} {stats[name]}")

        print(
            f"{'media_tasks':24} "
            f"{media['media_tasks']}"
        )
        print(
            f"{'media_reuse':24} "
            f"{media['media_reuse']}"
        )
        print(
            f"{'media_downloaded':24} "
            f"{media['media_downloaded']}"
        )
        print(
            f"{'media_successful':24} "
            f"{media['media_successful']}"
        )
        print(
            f"{'media_failed (skip)':24} "
            f"{media['media_failed']}"
        )

        pg_conn = db_connection()

        try:
            validate_postgres_state(pg_conn)

            print()
            print("POSTGRES TRANSACTION")
            print("-" * 70)

            result = perform_load(
                staging_path,
                sqlite_conn,
                pg_conn,
            )

            print(
                f"{'new import id':24} "
                f"{result['import_id']}"
            )
            print(
                f"{'constructions':24} "
                f"{result['constructions']}"
            )
            print(
                f"{'surfaces':24} "
                f"{result['surfaces']}"
            )
            print(
                f"{'availability':24} "
                f"{result['availability']}"
            )
            print(
                f"{'new media':24} "
                f"{result['media']}"
            )
            print(
                f"{'media errors skipped':24} "
                f"{result['media_skipped_errors']}"
            )

            if dry_run:
                pg_conn.rollback()
                print()
                print("ROLLBACK")
                print("PostgreSQL: НЕ ИЗМЕНЁН")
                print("DRY-RUN: PASS")
            else:
                print()
                print("ANALYZE")
                print("-" * 70)
                analyze_loaded_tables(pg_conn)
                print("planner statistics updated")

                pg_conn.commit()
                write_load_result(
                    staging_path.parent.name,
                    result,
                )
                print()
                print("COMMIT")
                print("PostgreSQL: ИЗМЕНЁН")
                print("IMPORT: PASS")

        except Exception:
            pg_conn.rollback()
            raise
        finally:
            pg_conn.close()

    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    main()
