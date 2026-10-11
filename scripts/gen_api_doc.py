#!/usr/bin/env python3
"""Генерирует doc/api.md из OpenAPI-схемы приложения.

Запуск из корня проекта (нужен venv с зависимостями backend):

    .venv/bin/python scripts/gen_api_doc.py

Скрипт детерминированный: при неизменном API вывод не меняется.
Правьте шаблон здесь, а не сгенерированный doc/api.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Корень проекта в sys.path, чтобы импортировался пакет backend.
PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

OUT_PATH = PROJECT_DIR / "doc" / "api.md"

HEADER = (
    "<!-- СГЕНЕРИРОВАНО: scripts/gen_api_doc.py. "
    "Не редактировать вручную — правьте генератор. -->"
)

NO_TAG = "Прочее (без тега)"

AUTH_NOTE = """\
## Аутентификация

- Публичные эндпоинты (`/api/settings`, `/api/home`, `/api/constructions`,
  `/api/contacts`, `/api/about`, `/api/news`, `/api/pages/...`) — без токена.
- Админские (`/api/admin/*`) — заголовок `Authorization: Bearer <admin-token>`
  (получается через `POST /api/admin/login`).
- Личный кабинет (`/api/account/*`) — `Authorization: Bearer <account-token>`
  (`POST /api/account/login`).
- Вход и восстановление ограничены rate-limit (in-memory, см. `backend/main.py`).
"""


def _method_order(method: str) -> int:
    order = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}
    return order.get(method, 99)


def main() -> None:
    from backend.main import app

    schema = app.openapi()
    info = schema.get("info", {})
    paths = schema.get("paths", {})

    # Группируем операции по тегу (первый), внутри — по пути и методу.
    groups: dict[str, list[tuple[str, str, str]]] = {}

    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            tags = operation.get("tags") or [NO_TAG]
            tag = tags[0]
            summary = (operation.get("summary") or "").strip()

            groups.setdefault(tag, []).append((path, method, summary))

    lines: list[str] = [HEADER, "", "# API — справочник эндпоинтов", ""]
    lines.append(
        f"Сгенерировано из OpenAPI (`/openapi.json`). "
        f"Версия приложения: `{info.get('version', '?')}`. "
        f"Путей: {len(paths)}, операций: {sum(len(v) for v in groups.values())}."
    )
    lines.append("")
    lines.append(
        "Регенерация: `.venv/bin/python scripts/gen_api_doc.py`."
    )
    lines.append("")
    lines.append(AUTH_NOTE)

    # (без тега) — в конце, остальные теги по алфавиту.
    for tag in sorted(groups, key=lambda name: (name == NO_TAG, name)):
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| Метод | Путь | Описание |")
        lines.append("|---|---|---|")

        for path, method, summary in sorted(
            groups[tag], key=lambda item: (item[0], _method_order(item[1]))
        ):
            lines.append(f"| {method.upper()} | `{path}` | {summary} |")

        lines.append("")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"OK: {OUT_PATH} ({len(paths)} paths, {len(groups)} groups)")


if __name__ == "__main__":
    main()
