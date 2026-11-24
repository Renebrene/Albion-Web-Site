"""Слайд главной «Светофорные объекты» с загружаемым HTML-кодом баннера.

  • home_slides.code — TEXT с самостоятельным HTML-документом баннера;
    он открывается в sandbox-iframe внизу слайда (kind='road-banner').
  • Слайд вставляется непосредственно перед новостным слайдом (если его
    ещё нет) и получает стартовый код из
    backend/templates/road_banner.html.

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_banner_code
"""
from pathlib import Path

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "road_banner.html"
)

TITLE = "Светофорные объекты"

TEXT = (
    "Рекламное агентство «Альбион» активно участвует в программах "
    "по благоустройству города.\n"
    "Одной из таких программ является обеспечение безопасности движения "
    "в городе.\n"
    "Альбион – это своя производственная база, сварочный участок,\n"
    "автоподъемник со стрелой 23 м, кран-манипулятор."
)


def run() -> None:
    print("ALBION · Миграция: слайд «Светофорные объекты» с кодом баннера")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE home_slides "
                "ADD COLUMN IF NOT EXISTS code TEXT NOT NULL DEFAULT ''"
            )

            existing = conn.execute(
                """
                SELECT id FROM home_slides
                WHERE kind = 'road-banner'
                ORDER BY sort_order, id
                LIMIT 1
                """
            ).fetchone()

            if existing:
                print(f"  → слайд уже есть (id={existing[0]}), пропуск")
                return

            code = TEMPLATE.read_text(encoding="utf-8")

            news = conn.execute(
                """
                SELECT sort_order FROM home_slides
                WHERE kind = 'news'
                ORDER BY sort_order, id
                LIMIT 1
                """
            ).fetchone()

            if news:
                order = int(news[0])

                # Освобождаем место ровно перед новостным слайдом.
                conn.execute(
                    "UPDATE home_slides SET sort_order = sort_order + 1 "
                    "WHERE sort_order >= %s",
                    (order,),
                )
            else:
                row = conn.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) + 1 "
                    "FROM home_slides"
                ).fetchone()
                order = int(row[0])

            new_id = conn.execute(
                """
                INSERT INTO home_slides
                    (sort_order, kind, title, text, code, is_active)
                VALUES (%s, 'road-banner', %s, %s, %s, TRUE)
                RETURNING id
                """,
                (order, TITLE, TEXT, code),
            ).fetchone()[0]

            print(f"  → добавлен слайд id={new_id}, sort_order={order}")
            print(f"  → код баннера: {len(code)} символов")

    print("COMMIT: миграция завершена.")
    print("  • home_slides.code, слайд kind='road-banner'")


if __name__ == "__main__":
    run()
