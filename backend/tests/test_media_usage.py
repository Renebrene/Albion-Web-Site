"""Медиатека: учёт использованных файлов по всем разделам сайта."""
from __future__ import annotations

from backend.services.data_service import get_connection, load_env_file, PROJECT_DIR
from backend.services.media_service import list_media, used_section_names
from backend.tests.conftest import requires_db

load_env_file(PROJECT_DIR / ".env")


def test_used_section_names_covers_all_sections():
    sections = used_section_names(
        in_news=True,
        in_geo=True,
        page_slugs=["kontakty"],
        in_contacts=True,
        in_menu=True,
        in_settings=True,
        in_info=True,
        in_home=True,
        in_portfolio=True,
    )

    assert set(sections) == {
        "Новости",
        "География",
        "Контакты",
        "Меню сайта",
        "Настройки сайта",
        "Информация",
        "Главная",
        "Портфель",
    }


@requires_db
def test_catalog_marks_files_used_outside_news_and_pages():
    """Файл из меню/настроек не должен помечаться «не используется»."""
    items = list_media(limit=200)

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT m.id
            FROM media m
            JOIN site_menu_items mi ON mi.url LIKE '%' || split_part(m.storage_path, '/', -1) || '%'
            LIMIT 1
            """
        ).fetchone()

    if not row:
        return

    item = next((m for m in items if m["id"] == row[0]), None)
    assert item is not None
    assert "Меню сайта" in item["used_sections"]


@requires_db
def test_catalog_returns_used_sections_for_geo_photos():
    items = list_media(limit=200)
    geo = [m for m in items if "География" in (m["used_sections"] or [])]

    assert geo, "в базе должны быть фото географии"
