"""
Миграция для Roadrunner — программной дороги Альбион.

Создаёт таблицы:
- roadrunner_scenarios — сценарии (JSON)
- roadrunner_settings — настройки (JSON)

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_roadrunner
"""
from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file


load_env_file(PROJECT_DIR / ".env")


def run() -> None:
    print("ALBION · Миграция: Roadrunner (программная дорога)")

    with get_connection() as conn:
        with conn.transaction():
            # Сценарии
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roadrunner_scenarios (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    scenario_data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    author TEXT NOT NULL DEFAULT 'system'
                )
                """
            )

            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON roadrunner_scenarios TO albion_app"
            )
            conn.execute(
                "GRANT USAGE, SELECT ON SEQUENCE roadrunner_scenarios_id_seq TO albion_app"
            )

            # Настройки
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roadrunner_settings (
                    key TEXT PRIMARY KEY,
                    settings JSONB NOT NULL
                )
                """
            )

            conn.execute(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON roadrunner_settings TO albion_app"
            )

            # Стартовые сценарии (если пусто)
            count = conn.execute(
                "SELECT COUNT(*) FROM roadrunner_scenarios"
            ).fetchone()[0]

            if count == 0:
                # Копируем из api/scenarios/
                import json
                from pathlib import Path

                scenarios_dir = (
                    Path(__file__).resolve().parents[1]
                    / "roadrunner" / "api" / "scenarios"
                )

                if scenarios_dir.exists():
                    for path in scenarios_dir.glob("*.json"):
                        with path.open(encoding="utf-8") as f:
                            scenario = json.load(f)

                        conn.execute(
                            """
                            INSERT INTO roadrunner_scenarios
                                (name, description, scenario_data, author)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            (
                                scenario.get("name", path.stem),
                                scenario.get("description", ""),
                                json.dumps(scenario, ensure_ascii=False),
                                "import",
                            ),
                        )

                # Стартовые настройки
                conn.execute(
                    """
                    INSERT INTO roadrunner_settings (key, settings)
                    VALUES ('roadrunner', %s)
                    ON CONFLICT (key) DO NOTHING
                    """,
                    (
                        json.dumps(
                            {
                                "default_scenario": "rostov-evening-rain",
                                "weather_enabled": True,
                                "traffic_enabled": True,
                                "llm_provider": "ollama",
                                "llm_model": "qwen2.5:7b",
                            }
                        ),
                    ),
                )

    print("COMMIT: миграция Roadrunner завершена.")
    print("  • roadrunner_scenarios, roadrunner_settings")


if __name__ == "__main__":
    run()
