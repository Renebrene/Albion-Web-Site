# Документация Albion

Точка входа в `doc/`. Сначала прочитайте корневой [`AGENTS.md`](../AGENTS.md) —
там карта репозитория и правила.

## Состав

| Документ | О чём |
|---|---|
| [`architecture.md`](architecture.md) | Как устроено: слои, потоки данных, состояние |
| [`api.md`](api.md) | Справочник эндпоинтов — **генерируется** |
| [`database.md`](database.md) | Схема БД: таблицы, ключи, расширения — **генерируется** |
| [`troubleshooting.md`](troubleshooting.md) | Известные грабли: симптом → причина → что делать |
| [`glossary.md`](glossary.md) | Термины: конструкция, сторона, поверхность, статусы, портфель |
| [`../deploy/README.md`](../deploy/README.md) | Деплой: env, nginx, Docker/нативно, тесты |

> `api.md` и `database.md` генерируются скриптами (`scripts/gen_api_doc.py`,
> `scripts/gen_db_doc.py`) — правьте генераторы, а не эти файлы.

## С чего начать по задаче

- **Понять, как всё связано** → `architecture.md`.
- **Найти эндпоинт** → `api.md` (или живой `/docs` на запущенном бэкенде).
- **Понять таблицу/связи** → `database.md`.
- **Что-то сломалось / странно себя ведёт** → `troubleshooting.md`.
- **Что-то не запускается локально** → раздел «Как запускать» в `AGENTS.md`.
- **Развернуть на VDS** → `deploy/README.md`.
- **Разобраться с картой / портфелем / чатом** → пока по коду: `frontend/src/map/`,
  `frontend/src/composables/usePortfolio.js`, `backend/chat/` (подробные
  документы по этим подсистемам — в планах, фаза 2).

## Ещё не задокументировано (запланировано)

`smart-chat.md`, `import-pipeline.md`, `portfolio-export.md`, `map.md`,
`frontend.md`, `glossary.md`.
