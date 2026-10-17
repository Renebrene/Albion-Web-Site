# Документация Albion

Точка входа в `doc/`. Сначала прочитайте корневой [`AGENTS.md`](../AGENTS.md) —
там карта репозитория и правила.

## Состав

| Документ | О чём |
|---|---|
| [`architecture.md`](architecture.md) | Как устроено: слои, потоки данных, состояние |
| [`api.md`](api.md) | Справочник эндпоинтов — **генерируется** |
| [`database.md`](database.md) | Схема БД: таблицы, ключи, расширения — **генерируется** |
| [`import-pipeline.md`](import-pipeline.md) | Импорт Excel → PostgreSQL: 7 стадий, медиа, архивы |
| [`map.md`](map.md) | Интерактивная карта: движки Leaflet/Яндекс, попапы, статусы |
| [`portfolio-export.md`](portfolio-export.md) | Портфель и выгрузка: форматы, LibreOffice |
| [`smart-chat.md`](smart-chat.md) | Умный чат: парсер, LLM-fallback, сессии |
| [`search-v2.md`](search-v2.md) | Поиск 2.0: каталог в памяти, типы/размеры/локации, `/api/search/v2` |
| [`account-cabinet.md`](account-cabinet.md) | Личный кабинет и авторизация — **сейчас скрыты**, бэкенд сохранён |
| [`frontend.md`](frontend.md) | Обзор фронтенда: роутер, страницы, boot, компоненты |
| [`glossary.md`](glossary.md) | Термины: конструкция, сторона, поверхность, статусы, портфель |
| [`troubleshooting.md`](troubleshooting.md) | Известные грабли: симптом → причина → что делать |
| [`../deploy/README.md`](../deploy/README.md) | Деплой: env, nginx, Docker/нативно, тесты |

> `api.md` и `database.md` генерируются скриптами (`scripts/gen_api_doc.py`,
> `scripts/gen_db_doc.py`) — правьте генераторы, а не эти файлы.

## С чего начать по задаче

- **Понять, как всё связано** → `architecture.md`.
- **Найти эндпоинт** → `api.md` (или живой `/docs` на запущенном бэкенде).
- **Понять таблицу/связи** → `database.md`.
- **Разобраться с картой / портфелем / чатом / импортом** → `map.md`,
  `portfolio-export.md`, `smart-chat.md`, `import-pipeline.md`.
- **Ориентироваться в страницах и сборке фронтенда** → `frontend.md`.
- **Уточнить термин** → `glossary.md`.
- **Что-то сломалось / странно себя ведёт** → `troubleshooting.md`.
- **Что-то не запускается локально** → раздел «Как запускать» в `AGENTS.md`.
- **Развернуть на VDS** → `deploy/README.md`.
