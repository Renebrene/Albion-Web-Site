"""Режим управления колодой карточек geo-слайда колесом мыши.

deck_wheel_mode:
  off — колесо листает вертикальные слайды (как раньше);
  v1  — колесо вниз: перемотка вправо/влево по положению курсора
        относительно центра главной карточки; колесо вверх: раскрыть карточку;
  v2  — колесо вверх: вперёд (вправо), колесо вниз: назад (влево); клик: раскрыть;
  v3  — колесо вниз: вперёд, колесо вверх: назад; у краёв колоды колесо
        отдаётся вертикальной навигации; клик: раскрыть.

Запуск:  .venv/bin/python -m backend.migrations.migrate_home_geo_wheel
Идемпотентно.
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file

load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция режима колеса для geo-колоды")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                "ALTER TABLE home_geo_settings "
                "ADD COLUMN IF NOT EXISTS deck_wheel_mode TEXT NOT NULL DEFAULT 'off'"
            )

    print("COMMIT: geo-миграция режима колеса завершена.")


if __name__ == "__main__":
    run()
