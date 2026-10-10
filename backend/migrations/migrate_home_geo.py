"""Geo-контент главной: города/районы и достопримечательности.

Изображения привязываются к существующей медиатеке через media_id. Для каждой
фотографии обязательны данные атрибуции источника/лицензии.
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file

load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция geo-контента главной")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_geo_settings (
                    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    map_links_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                INSERT INTO home_geo_settings (id)
                VALUES (1)
                ON CONFLICT (id) DO NOTHING
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_geo_locations (
                    id BIGSERIAL PRIMARY KEY,
                    kind TEXT NOT NULL CHECK (kind IN ('city', 'district')),
                    label TEXT NOT NULL,
                    map_value TEXT NOT NULL DEFAULT '',
                    parent_city TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (kind, label)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_geo_attractions (
                    id BIGSERIAL PRIMARY KEY,
                    location_id BIGINT REFERENCES home_geo_locations(id)
                        ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_geo_attraction_photos (
                    id BIGSERIAL PRIMARY KEY,
                    attraction_id BIGINT NOT NULL
                        REFERENCES home_geo_attractions(id) ON DELETE CASCADE,
                    media_id BIGINT REFERENCES media(id) ON DELETE RESTRICT,
                    image_path TEXT NOT NULL DEFAULT '',
                    alt_text TEXT NOT NULL DEFAULT '',
                    source_name TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    license TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_cover BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS home_geo_locations_order_idx "
                "ON home_geo_locations (is_active, kind, sort_order, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS home_geo_attractions_order_idx "
                "ON home_geo_attractions (is_active, location_id, sort_order, id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS home_geo_photos_order_idx "
                "ON home_geo_attraction_photos (attraction_id, sort_order, id)"
            )

            for table in (
                "home_geo_settings",
                "home_geo_locations",
                "home_geo_attractions",
                "home_geo_attraction_photos",
            ):
                conn.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO albion_app"
                )
                if table != "home_geo_settings":
                    conn.execute(
                        "GRANT USAGE, SELECT, UPDATE ON SEQUENCE "
                        f"{table}_id_seq TO albion_app"
                    )

            # Полный список городов/районов, уже присутствующих в XLS-данных.
            conn.execute(
                """
                INSERT INTO home_geo_locations
                    (kind, label, map_value, sort_order)
                SELECT 'city', c.name, c.name,
                       ROW_NUMBER() OVER (ORDER BY c.name) - 1
                FROM cities c
                WHERE c.is_active = TRUE
                ON CONFLICT (kind, label) DO NOTHING
                """
            )
            conn.execute(
                """
                INSERT INTO home_geo_locations
                    (kind, label, map_value, parent_city, sort_order)
                SELECT 'district', x.district, x.district, '',
                       ROW_NUMBER() OVER (ORDER BY x.district) - 1
                FROM (
                    SELECT DISTINCT NULLIF(TRIM(district), '') AS district
                    FROM constructions
                    WHERE district IS NOT NULL AND TRIM(district) <> ''
                ) x
                WHERE x.district IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM cities c
                      WHERE lower(c.name) = lower(x.district)
                  )
                ON CONFLICT (kind, label) DO NOTHING
                """
            )

    print("COMMIT: geo-миграция главной завершена.")


if __name__ == "__main__":
    run()
