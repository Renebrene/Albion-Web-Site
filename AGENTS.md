# Albion — заметки для агентов

Короткий входной документ: карта репозитория, правила и грабли. Глубина —
в каталоге [`doc/`](doc/INDEX.md).

## Что это

Сайт рекламной сети «Альбион» (Ростов-на-Дону): публичный сайт + интерактивная
карта рекламных конструкций + личный кабинет/портфель + админка + «умный чат».
Стек: FastAPI + PostgreSQL/PostGIS (бэкенд), Quasar/Vue 3 (фронтенд).

## Карта репозитория

| Путь | Что там |
|---|---|
| `backend/main.py` | FastAPI-приложение: CORS, rate-limit, лимит размера запроса, часть роутов |
| `backend/api/` | `APIRouter`-ы: `admin_*`, `account`, `chat`, `portfolio`, … |
| `backend/services/` | Бизнес-логика: data, settings, home, news, contacts, media, portfolio_export, site_backup, auth, cms_url… |
| `backend/search/` | Мост к движку поиска (`bridge`, `repository`, `api`) |
| `backend/chat/` | «Умный чат»: парсер, LLM-fallback, хранилище сессий |
| `backend/importer/` | Импорт Excel → staging → PostgreSQL, скачивание медиа |
| `backend/migrations/` | Идемпотентные миграции схемы (запускаются отдельно) |
| `engine/` | Вендоренный движок поиска `albion-search` (top-level import `engine`) |
| `frontend/src/pages/` | Страницы: публичные и админские |
| `frontend/src/components/` | UI-компоненты (home, filters, layout, portfolio, chat…) |
| `frontend/src/map/` | Карта: `MapView.vue`, `useMap.js` (Leaflet), `useYandexMap.js`, `popupContent.js` |
| `frontend/src/composables/` | Общие сторы: `usePortfolio`, `usePhotoViewer`, `useConstructionsFilter`, … |
| `frontend/src/config/` | Настройки: `mapConfig`, `mapColors`, `availableMode`, `dynCount` |
| `frontend/src/boot/` | Boot-файлы: применение настроек, трекинг |
| `scripts/`, `deploy/` | Служебные скрипты и деплой (см. `deploy/README.md`) |
| `doc/` | Документация (см. `doc/INDEX.md`) |

## Как запускать и проверять

```bash
# Бэкенд (6 воркеров)
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 6

# Фронтенд (dev, :9000, проксирует /api и /storage на :8000)
cd frontend && bun run dev

# Тесты (нужны pytest+httpx: pip install -r requirements-dev.txt)
.venv/bin/python -m pytest backend/tests

# Линт фронтенда (non-mutating)
cd frontend && bun run lint:check

# Браузерный смоук (нужны Chrome и запущенный фронт)
uv run --with websockets python deploy/browser-smoke.py --base http://localhost:9000

# Справочники API и БД (генерируются — не правьте doc/api.md и doc/database.md руками)
.venv/bin/python scripts/gen_api_doc.py
.venv/bin/python scripts/gen_db_doc.py
```

## Правила работы

- **Один коммит на логический блок**, прямо в `main` + `git push`. Сообщение
  заканчивать строкой `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- **Не коммитить**: `.env`, `frontend/.env.local`, файл `ChatGPT-САЙТ 6-…md`.
  Секреты — только в окружении.
- Перед правкой смотреть `git status`: в дереве бывают **чужие незакоммиченные
  изменения** (импортёр, `update_service.py` и т.п.) — их не трогать и не коммитить.
- Не менять поведение без проверки: `cd frontend && bun run build`, `pytest
  backend/tests`, а для UI — браузерная проверка.
- Не ослаблять серверные проверки (валидация CMS-ссылок, цветов, лимиты загрузки).

## Грабли (подробнее — `doc/troubleshooting.md`)

- `psycopg3`: `with get_connection() as conn` **коммитит на выходе** без исключения.
- Несколько воркеров uvicorn: фоновые задачи защищать advisory-lock (пример —
  `backend/services/site_backup_service.py`).
- LibreOffice (`soffice`) — тяжёлый; используется для экспорта doc/odt/rtf/pdf/xls/ods.
  Нужны шрифты `DejaVu`/`Liberation`.
- Yandex-карта: ключ только из `VITE_YANDEX_MAPS_KEY`. Quasar отдаёт в клиент лишь
  префиксы `QCLI_`/`VITE_` (см. `build.env` в `frontend/quasar.config.js`).
  Без ключа карта тихо откатывается на Leaflet. Значение **вшивается в бандл** —
  после правки `.env.local` нужен рестарт dev / пересборка.
- CSP задан в `frontend/index.html` и в `deploy/nginx.conf.example` — новые внешние
  хосты добавлять в оба места.
