"""Миграция переопределений фото конструкций (медиатека конструкций).

Переопределение — временное: строка привязана к активному импорту (`import_id`)
и действует, пока этот импорт активен. Следующий импорт меняет активный импорт,
и переопределение перестаёт применяться (файлы остаются в каталоге превью).

Идемпотентна.

Запуск:  .venv/bin/python -m backend.migrations.migrate_construction_media_overrides
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция переопределений фото конструкций")

    with get_connection() as conn:
        with conn.transaction():
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS construction_media_overrides (
                    id BIGSERIAL PRIMARY KEY,

                    import_id BIGINT,
                    surface_hash TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'photo',

                    large_path TEXT,
                    card_path TEXT,
                    thumb_path TEXT,

                    original_name TEXT,

                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                    UNIQUE (surface_hash, media_type)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cm_overrides_active "
                "ON construction_media_overrides (import_id)"
            )
            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE "
                "ON construction_media_overrides TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT, UPDATE "
                "ON SEQUENCE construction_media_overrides_id_seq TO albion_app"
            )

    print("COMMIT: миграция переопределений фото завершена.")
    print("  • таблица: construction_media_overrides")
    print("  • каталог превью: storage/constructions/overrides")


if __name__ == "__main__":
    run()
