"""Закладки страницы «Информация» (/informaciya).

Число и содержание закладок управляются из админки. Закладка бывает двух
видов:
  • text — обычный текст (заголовок + содержимое), правится в админке;
  • geo  — список городов и районов слева и описание справа; данные берутся
           из geo-контента главной (home_geo_locations / home_geo_attractions).

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_info_tabs
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


# Стартовый набор закладок (используется только если таблица пустая).
SEED_TABS = (
    ("ОБЩЕЕ", "text", ""),
    ("КОНСТРУКЦИИ", "text", ""),
    ("ГОРОДА И РАЙОНЫ", "geo", ""),
    ("ТЕХ ТРЕБОВАНИЯ", "text", ""),
)


def run() -> None:
    print("ALBION · Миграция закладок страницы «Информация»")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS info_tabs (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'text'
                        CHECK (kind IN ('text', 'geo')),
                    content TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS info_tabs_order_idx "
                "ON info_tabs (is_active, sort_order, id)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON info_tabs TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE "
                "info_tabs_id_seq TO albion_app"
            )

            row = conn.execute("SELECT COUNT(*) FROM info_tabs").fetchone()

            if not row or row[0] == 0:
                for index, (title, kind, content) in enumerate(SEED_TABS):
                    conn.execute(
                        """
                        INSERT INTO info_tabs (title, kind, content, sort_order)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (title, kind, content, index * 10),
                    )

    print("COMMIT: миграция закладок «Информация» завершена.")
    print("  • таблица: info_tabs")


if __name__ == "__main__":
    run()
