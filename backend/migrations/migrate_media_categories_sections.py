"""Разделы-теги медиатеки сайта по типам страниц.

Загрузчики разных страниц проставляют свой раздел (новости → «Новости»,
слайды главной → «Слайдеры» и т.д.). Здесь заводим полный список
разделов — включая те, что пока не используются: они нужны для ручной
простановки в медиахранилище.

Медиа рекламных конструкций это **не** касается: у них своя подсистема
(`construction_media`, `storage/constructions/...`).

Разделы виртуальные: файлы не двигаются, меняется только `category_id`.
Скрипт идемпотентен — повторный запуск ничего не меняет.

Запуск:  .venv/bin/python -m backend.migrations.migrate_media_categories_sections
"""

from __future__ import annotations

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


# (название, порядок сортировки). Существующие разделы сохраняют свой
# порядок — добавляем только отсутствующие.
SECTIONS: list[tuple[str, int]] = [
    ("Разное", 0),
    ("Новости", 10),
    ("О компании", 20),
    ("Сотрудники", 30),
    ("Конструкции", 40),
    ("Прочее", 50),
    ("Офис", 60),
    ("География", 70),
    ("Документы", 80),
    ("Главная", 90),
    ("Слайдеры", 100),
    ("Пользователи", 110),
    ("Информация", 120),
    ("Контакты", 130),
    ("Медиа", 140),
]


def main() -> None:
    print("ALBION · Миграция: разделы-теги медиатеки сайта")

    created: list[str] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for name, order in SECTIONS:
                cur.execute(
                    "SELECT id FROM media_categories WHERE name = %s",
                    (name,),
                )

                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO media_categories (name, sort_order)
                    VALUES (%s, %s)
                    """,
                    (name, order),
                )
                created.append(name)

            cur.execute(
                "SELECT id, name, sort_order FROM media_categories "
                "ORDER BY sort_order, id"
            )
            rows = cur.fetchall()

    print(f"Создано разделов: {len(created)}" + (f" — {', '.join(created)}" if created else ""))

    for row in rows:
        print(f"  {row[0]:>3}  {row[1]}  (порядок {row[2]})")


if __name__ == "__main__":
    main()
