"""Модальная карточка geo-слайда: описание локации и выбранная обложка.

Для каждой локации (города/района) храним многопараграфное описание и
достопримечательность-обложку, фото которой показывается слева в модальном окне.
Если обложка не выбрана, фронтенд возьмёт первую достопримечательность локации.

Запуск:  .venv/bin/python -m backend.migrations.migrate_home_geo_modal
Идемпотентно: повторный запуск ничего не меняет.
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file

load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция модальной карточки geo-слайда")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE home_geo_locations "
                "ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''"
            )
            conn.execute(
                "ALTER TABLE home_geo_locations "
                "ADD COLUMN IF NOT EXISTS cover_attraction_id BIGINT "
                "REFERENCES home_geo_attractions(id) ON DELETE SET NULL"
            )

    print("COMMIT: geo-миграция модальной карточки завершена.")


if __name__ == "__main__":
    run()
