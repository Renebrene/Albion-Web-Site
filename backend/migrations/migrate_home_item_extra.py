"""Поле `extra` у карточек главной: блок дополнительного контента.

Значения:
  ''              — ничего;
  network_stats   — статистика сети (конструкции/форматы/стороны/поверхности).

Идемпотентно. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_item_extra
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция поля extra у карточек главной")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE home_slide_items "
                "ADD COLUMN IF NOT EXISTS extra TEXT NOT NULL DEFAULT ''"
            )

            # Вторая карточка верхнего слайда — статистика сети.
            row = conn.execute(
                """
                SELECT i.id FROM home_slide_items i
                JOIN home_slides s ON s.id = i.slide_id
                WHERE s.kind = 'hero'
                ORDER BY i.sort_order, i.id
                OFFSET 1 LIMIT 1
                """
            ).fetchone()

            if row:
                conn.execute(
                    "UPDATE home_slide_items SET extra = 'network_stats' "
                    "WHERE id = %s AND (extra IS NULL OR extra = '')",
                    (row[0],),
                )

    print("COMMIT: поле extra добавлено.")


if __name__ == "__main__":
    run()
