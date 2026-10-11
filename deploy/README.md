# Деплой Albion (VDS)

Краткая шпаргалка по окружению и публикации. Секреты в репозиторий не
коммитятся — держите их в `.env` / `.env.local` (оба в `.gitignore`).

## Backend (FastAPI + uvicorn)

Переменные окружения backend (`.env` в корне проекта):

| Переменная | Назначение |
|---|---|
| `ALBION_DB_HOST/PORT/NAME/USER/PASSWORD` | подключение к PostgreSQL |
| `ALBION_ALLOWED_ORIGINS` | список origin через запятую для CORS (например `https://albion.example.ru`); пусто — только локальная разработка |
| `ALBION_SERVE_SPA` | `1` — backend сам отдаёт собранный `frontend/dist/spa` с history-fallback (если нет nginx) |

Запуск: `.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`

## Frontend (Quasar + Vite)

Сборка: `npm ci && npm run build` → `frontend/dist/spa`.

Переменные окружения фронтенда (`frontend/.env.local`, образец —
`frontend/.env.example`):

| Переменная | Назначение |
|---|---|
| `VITE_YANDEX_MAPS_KEY` | ключ Yandex Maps JS API 2.1 (см. ниже) |

## nginx

Готовый пример — `deploy/nginx.conf.example`: history-fallback SPA
(`try_files … /index.html`), прокси `/api` и `/storage`, кэш ассетов и
CSP-заголовок для боевого домена.

## Ключ Yandex Maps: ротация и ограничение

- Версия API — **2.1** (как в `frontend/src/map/yandexLoader.js`; ручной тест
  `test-yandex.html` тоже на 2.1). Если решите перейти на v3 — это отдельная
  задача: меняются и код загрузчика, и разметка карты.
- Ключ в коде **не хранится**. Задаётся только через `VITE_YANDEX_MAPS_KEY`.
  Если он не задан — загрузчик сразу откажется, и карта переключится на
  Leaflet/OSM (сайт продолжает работать).
- В кабинете <https://developer.tech.yandex.ru/> ограничьте ключ по домену
  (боевой домен + при необходимости localhost для разработки).
- При смене/компрометации — перевыпустите ключ и обновите `frontend/.env.local`,
  затем пересоберите фронтенд.
