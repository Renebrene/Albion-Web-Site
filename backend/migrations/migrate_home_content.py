"""Миграция главной: тип слайда + сообщения формы обратной связи.

  • home_slides.kind — тип слайда:
      hero          — верхний, горизонтальные карточки (о компании/мотивация);
      constructions — список конструкций с переходом на карту;
      news          — несколько новостей;
      form          — форма обратной связи;
      text          — обычный текстовый слайд (по умолчанию).
  • site_feedback — сообщения из формы на главной.

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_content
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция главной (типы слайдов + форма)")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE home_slides "
                "ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'text'"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS site_feedback (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON site_feedback TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE "
                "ON SEQUENCE site_feedback_id_seq TO albion_app"
            )

            # Верхний слайд — hero.
            conn.execute(
                "UPDATE home_slides SET kind = 'hero' "
                "WHERE is_hero = TRUE AND kind = 'text'"
            )

            # Первому не-верхнему слайду — тип «конструкции».
            conn.execute(
                """
                UPDATE home_slides SET kind = 'constructions'
                WHERE id = (
                    SELECT id FROM home_slides
                    WHERE is_hero = FALSE AND kind = 'text'
                    ORDER BY sort_order, id LIMIT 1
                )
                """
            )

            # Добавляем недостающие слайды news/form.
            for kind, title, text in (
                ("news", "Новости", "Последние события и проекты Albion"),
                (
                    "form",
                    "Обратная связь",
                    "Оставьте контакты — мы свяжемся с вами",
                ),
            ):
                exists = conn.execute(
                    "SELECT 1 FROM home_slides WHERE kind = %s LIMIT 1",
                    (kind,),
                ).fetchone()

                if not exists:
                    conn.execute(
                        """
                        INSERT INTO home_slides (sort_order, kind, title, text)
                        VALUES (
                            (SELECT COALESCE(MAX(sort_order), -1) + 1
                             FROM home_slides),
                            %s, %s, %s
                        )
                        """,
                        (kind, title, text),
                    )

    print("COMMIT: миграция главной (типы/форма) завершена.")
    print("  • home_slides.kind, site_feedback")


if __name__ == "__main__":
    run()
