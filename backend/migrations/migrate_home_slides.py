"""Миграция БД для главной страницы: вертикальные слайды + горизонтальные.

Создаёт таблицы:
  • home_slides      — вертикальные слайды главной (по одному на экран);
                       у верхнего слайда is_hero = TRUE, он листается
                       горизонтальными «инстанциями» (home_slide_items).
  • home_slide_items — горизонтальные карточки слайда (фото/заголовок/
                       текст/кнопка), показываются каруселью.

Одна карточка = фото + заголовок + текст + (необязательная) кнопка.

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_slides
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция главной страницы (слайды)")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_slides (
                    id BIGSERIAL PRIMARY KEY,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_hero BOOLEAN NOT NULL DEFAULT FALSE,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    button_label TEXT NOT NULL DEFAULT '',
                    button_url TEXT NOT NULL DEFAULT '',
                    image_path TEXT NOT NULL DEFAULT '',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_slide_items (
                    id BIGSERIAL PRIMARY KEY,
                    slide_id BIGINT NOT NULL
                        REFERENCES home_slides(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    button_label TEXT NOT NULL DEFAULT '',
                    button_url TEXT NOT NULL DEFAULT '',
                    image_path TEXT NOT NULL DEFAULT '',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS home_slide_items_slide_idx "
                "ON home_slide_items (slide_id, sort_order)"
            )

            for table in ("home_slides", "home_slide_items"):
                conn.execute(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    f"ON {table} TO albion_app"
                )
                conn.execute(
                    "GRANT USAGE, SELECT, UPDATE ON SEQUENCE "
                    f"{table}_id_seq TO albion_app"
                )

            # Небольшой стартовый контент, если таблица пустая.
            row = conn.execute(
                "SELECT COUNT(*) FROM home_slides"
            ).fetchone()

            if not row or row[0] == 0:
                hero_id = conn.execute(
                    """
                    INSERT INTO home_slides
                        (sort_order, is_hero, title, text)
                    VALUES (0, TRUE, 'АЛЬБИОН', 'Рекламная сеть Ростова-на-Дону')
                    RETURNING id
                    """
                ).fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO home_slide_items
                        (slide_id, sort_order, title, text)
                    VALUES
                        (%s, 0, 'Наружная реклама', 'Щиты, пилоны, призматроны и видеоэкраны'),
                        (%s, 1, 'Размещение под ключ', 'От идеи и макета до печати и монтажа')
                    """,
                    (hero_id, hero_id),
                )

                conn.execute(
                    """
                    INSERT INTO home_slides (sort_order, title, text)
                    VALUES (1, 'Возможности', 'Карта рекламных конструкций города')
                    """
                )

    print("COMMIT: миграция главной завершена.")
    print("  • таблицы: home_slides, home_slide_items")


if __name__ == "__main__":
    run()
