"""Дополнительные кнопки на слайдах главной и карточках верхнего слайда.

Таблица ``home_slide_buttons``:
  • ``item_id IS NULL`` — кнопка слайда (страницы слайда);
  • ``item_id`` задан   — кнопка карточки верхнего (hero) слайда.

``variant``: ``primary`` (акцентная) | ``ghost`` (прозрачная).

Первичное наполнение переносит текущие кнопки:
  • одиночную кнопку слайда (button_label/button_url);
  • две кнопки geo-слайда;
  • «Все новости» у слайда новостей;
  • обе кнопки (button/button2) у карточек hero.

Идемпотентно. Запуск:
  .venv/bin/python -m backend.migrations.migrate_home_slide_buttons
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

# Зашитые ранее кнопки geo-слайда и новостей.
GEO_BUTTONS = [
    ("Перейти на интерактивную карту", "/vozmozhnosti", "primary"),
    (
        "Смотреть описание городов и районов",
        "/informaciya?tab=города и районы",
        "ghost",
    ),
]
NEWS_BUTTONS = [("Все новости", "/novosti", "ghost")]


def _has_slide_buttons(conn, slide_id: int) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM home_slide_buttons "
        "WHERE slide_id = %s AND item_id IS NULL",
        (slide_id,),
    ).fetchone()

    return bool(row and row[0])


def _has_item_buttons(conn, item_id: int) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM home_slide_buttons WHERE item_id = %s",
        (item_id,),
    ).fetchone()

    return bool(row and row[0])


def _insert_buttons(conn, slide_id, item_id, buttons) -> None:
    for order, (label, url, variant) in enumerate(buttons):
        conn.execute(
            """
            INSERT INTO home_slide_buttons
                (slide_id, item_id, sort_order, label, url, variant)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (slide_id, item_id, order, label, url, variant),
        )


def run() -> None:
    print("ALBION · Миграция: кнопки слайдов главной")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS home_slide_buttons (
                    id BIGSERIAL PRIMARY KEY,
                    slide_id BIGINT NOT NULL
                        REFERENCES home_slides(id) ON DELETE CASCADE,
                    item_id BIGINT
                        REFERENCES home_slide_items(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    label TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    variant TEXT NOT NULL DEFAULT 'primary',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS home_slide_buttons_slide_idx "
                "ON home_slide_buttons (slide_id, item_id, sort_order)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON home_slide_buttons TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE ON SEQUENCE "
                "home_slide_buttons_id_seq TO albion_app"
            )

            # --- кнопки слайдов (страниц) ---
            slides = conn.execute(
                "SELECT id, kind, button_label, button_url FROM home_slides"
            ).fetchall()

            for slide_id, kind, button_label, button_url in slides:
                if _has_slide_buttons(conn, slide_id):
                    continue

                k = (kind or "").strip().lower()

                if k == "geo":
                    buttons = list(GEO_BUTTONS)
                elif k == "news":
                    buttons = list(NEWS_BUTTONS)
                elif (button_label or "").strip():
                    buttons = [
                        (button_label.strip(), (button_url or "").strip(), "primary")
                    ]
                else:
                    buttons = []

                if buttons:
                    _insert_buttons(conn, slide_id, None, buttons)

            # --- кнопки карточек верхнего слайда ---
            items = conn.execute(
                """
                SELECT id, slide_id, button_label, button_url,
                       button2_label, button2_url
                FROM home_slide_items
                """
            ).fetchall()

            for item_id, slide_id, bl, bu, bl2, bu2 in items:
                if _has_item_buttons(conn, item_id):
                    continue

                buttons = []

                if (bl or "").strip():
                    buttons.append((bl.strip(), (bu or "").strip(), "primary"))

                if (bl2 or "").strip():
                    buttons.append((bl2.strip(), (bu2 or "#").strip(), "ghost"))

                if buttons:
                    _insert_buttons(conn, slide_id, item_id, buttons)

    print("COMMIT: кнопки слайдов главной готовы.")


if __name__ == "__main__":
    run()
