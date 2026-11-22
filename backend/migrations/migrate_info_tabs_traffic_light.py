"""Добавление поддержки закладки «traffic-light» (3D светофор) в таблицу info_tabs.

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_info_tabs_traffic_light
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция: добавление kind='traffic-light' в info_tabs")

    with get_connection() as conn:
        with conn.transaction():
            # Проверяем, есть ли уже ограничение с traffic-light
            row = conn.execute(
                """
                SELECT conname, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'info_tabs'::regclass
                  AND contype = 'c'
                  AND conname LIKE '%kind%'
                """
            ).fetchone()

            if row:
                conname, condef = row
                if 'traffic-light' not in condef:
                    print(f"  → Обновление ограничения {conname}: {condef}")
                    conn.execute(f"ALTER TABLE info_tabs DROP CONSTRAINT {conname}")
                    conn.execute(
                        """
                        ALTER TABLE info_tabs
                        ADD CONSTRAINT info_tabs_kind_check
                        CHECK (kind IN ('text', 'geo', 'traffic-light'))
                        """
                    )
                    print("  → Ограничение обновлено")
                else:
                    print("  → Ограничение уже актуально, пропуск")
            else:
                print("  → Ограничение не найдено, таблица возможно не существует")

            # Также добавляем пример закладки, если таблица пустая
            count = conn.execute("SELECT COUNT(*) FROM info_tabs").fetchone()[0]
            if count == 0:
                conn.execute(
                    """
                    INSERT INTO info_tabs (title, kind, content, sort_order, is_active)
                    VALUES
                        ('ОБЩЕЕ', 'text', '', 0, TRUE),
                        ('КОНСТРУКЦИИ', 'text', '', 10, TRUE),
                        ('ГОРОДА И РАЙОНЫ', 'geo', '', 20, TRUE),
                        ('ТЕХ ТРЕБОВАНИЯ', 'text', '', 30, TRUE),
                        ('3D СВЕТОФОР', 'traffic-light', '', 40, TRUE)
                    """
                )
                print("  → Добавлены стартовые закладки (включая 3D Светофор)")

    print("COMMIT: миграция завершена.")


if __name__ == "__main__":
    run()