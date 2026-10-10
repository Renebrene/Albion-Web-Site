"""Дополнительные поля карточек/слайдов главной (для админки).

Добавляет редактируемые поля:
  • home_slide_items (горизонтальные карточки верхнего слайда):
    eyebrow (надзаголовок), slogan (крупный слоган), button2_label, button2_url.

Идемпотентно. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_items_fields
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

COLS = [
    ("eyebrow", "TEXT NOT NULL DEFAULT ''"),
    ("slogan", "TEXT NOT NULL DEFAULT ''"),
    ("button2_label", "TEXT NOT NULL DEFAULT ''"),
    ("button2_url", "TEXT NOT NULL DEFAULT ''"),
]


def run() -> None:
    print("ALBION · Миграция полей карточек главной")

    with get_connection() as conn:
        with conn.transaction():
            for name, ddl in COLS:
                conn.execute(
                    f"ALTER TABLE home_slide_items "
                    f"ADD COLUMN IF NOT EXISTS {name} {ddl}"
                )

            # Осмысленный первый слайд по умолчанию.
            row = conn.execute(
                """
                SELECT i.id FROM home_slide_items i
                JOIN home_slides s ON s.id = i.slide_id
                WHERE s.kind = 'hero'
                ORDER BY i.sort_order, i.id
                LIMIT 1
                """
            ).fetchone()

            if row:
                conn.execute(
                    """
                    UPDATE home_slide_items
                    SET eyebrow = COALESCE(NULLIF(eyebrow, ''), 'Группа компаний'),
                        slogan  = COALESCE(NULLIF(slogan, ''),
                                          'Более 30 лет делаем бизнес заметнее'),
                        button2_label = COALESCE(NULLIF(button2_label, ''), 'Деятельность'),
                        button2_url   = COALESCE(NULLIF(button2_url, ''), '/napravleniya')
                    WHERE id = %s
                    """,
                    (row[0],),
                )

    print("COMMIT: поля карточек главной добавлены.")


if __name__ == "__main__":
    run()
