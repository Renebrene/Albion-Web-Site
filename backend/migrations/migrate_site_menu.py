"""Миграция: таблица пунктов меню сайта (верхнее меню + подвал).

Создаёт site_menu_items и наполняет начальными значениями
(совпадают с текущими хардкод-пунктами). Идемпотентна.

Запуск:  .venv/bin/python -m backend.migrations.migrate_site_menu
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")

MENU_ITEMS = [
    # верхнее меню
    ("main", "home", "ГЛАВНАЯ СТРАНИЦА", "/", 10),
    ("main", "vozmozhnosti", "ВОЗМОЖНОСТИ", "/vozmozhnosti", 20),
    ("main", "napravleniya", "ДЕЯТЕЛЬНОСТЬ", "/napravleniya", 30),
    ("main", "novosti", "НОВОСТИ", "/novosti", 40),
    ("main", "informaciya", "ИНФОРМАЦИЯ", "/informaciya", 50),
    ("main", "portfolio", "ПОРТФЕЛЬ", "/portfolio", 60),
    ("main", "o-kompanii", "О КОМПАНИИ", "/o-kompanii", 70),
    ("main", "kontakty", "КОНТАКТЫ", "/kontakty", 80),
    # подвал
    ("footer", "privacy", "Политика конфиденциальности", "#", 10),
    ("footer", "tech-requirements", "Технические требования", "#", 20),
    ("footer", "sitemap", "Карта сайта", "#", 30),
    ("footer", "legal", "Юридическая информация", "#", 40),
]


def main() -> None:
    print("ALBION · Миграция меню сайта")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS site_menu_items (
                    id BIGSERIAL PRIMARY KEY,
                    section TEXT NOT NULL,
                    key TEXT NOT NULL UNIQUE,
                    label TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_site_menu_section
                ON site_menu_items (section, sort_order)
                """
            )

            for section, key, label, url, sort_order in MENU_ITEMS:
                conn.execute(
                    """
                    INSERT INTO site_menu_items (
                        section, key, label, url, sort_order, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (key) DO NOTHING
                    """,
                    (section, key, label, url, sort_order),
                )

            count = conn.execute(
                "SELECT COUNT(*) FROM site_menu_items"
            ).fetchone()[0]

    print(f"  • пунктов меню в БД: {count}")
    print("COMMIT: миграция меню завершена.")


if __name__ == "__main__":
    main()