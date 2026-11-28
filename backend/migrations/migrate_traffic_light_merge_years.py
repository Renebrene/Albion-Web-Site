"""Переработка закладки «Светофорные объекты» (kind='traffic-light').

Убирает переключение годов: текст объединяется в один статический блок
(без строк-годов-маркеров), сгруппированный по заказчику, опечатки
исправлены, дубли объединены. Не трогает image_url, custom_html, photos,
id/title/kind/sort_order/is_active.

Идемпотентна. Запуск:
  .venv/bin/python -m backend.migrations.migrate_traffic_light_merge_years
"""
from __future__ import annotations

import json

from backend.services.data_service import PROJECT_DIR, get_connection, load_env_file
from scripts.init_traffic_light_content import TRAFFIC_LIGHT_TEXT


load_env_file(PROJECT_DIR / ".env")


def _reworked_content(existing: str) -> str:
    """Возвращает JSON-контент с новым text, сохраняя прочие поля."""
    try:
        data = json.loads(existing) if existing.strip() else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    if not isinstance(data, dict):
        data = {}

    data["text"] = TRAFFIC_LIGHT_TEXT
    data.setdefault("image_url", data.get("image_url") or "")
    data.setdefault("custom_html", data.get("custom_html") or "")
    data.setdefault("photos", data.get("photos") or [])

    return json.dumps(data, ensure_ascii=False, indent=2)


def run() -> None:
    print("ALBION · Миграция: объединение текста «Светофорные объекты»")

    with get_connection() as conn:
        with conn.transaction():
            rows = conn.execute(
                "SELECT id, content FROM info_tabs WHERE kind = 'traffic-light'"
            ).fetchall()

            if not rows:
                print("  → закладка kind='traffic-light' не найдена, пропуск")
                return

            for tab_id, content in rows:
                conn.execute(
                    """
                    UPDATE info_tabs
                    SET content = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (_reworked_content(content or ""), tab_id),
                )
                print(f"  → обновлена закладка id={tab_id}")

    print("COMMIT: миграция завершена.")


if __name__ == "__main__":
    run()
