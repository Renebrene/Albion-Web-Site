# Архитектура

Общая картина: слои, потоки данных и состояние. Детали эндпоинтов — в
[`api.md`](api.md), схема БД — в [`database.md`](database.md).

## Стек

| Слой | Технологии |
|---|---|
| Фронтенд | Quasar 2 + Vue 3 (`<script setup>`), Vite, Leaflet / Yandex Maps JS API 2.1 |
| Бэкенд | FastAPI, Uvicorn, Pydantic v2 |
| БД | PostgreSQL 16 + PostGIS + pgcrypto, драйвер psycopg3 |
| Поиск | Вендоренный движок `engine/` (`albion-search`) |
| Экспорт | LibreOffice (`soffice`), python-docx, openpyxl, reportlab, Pillow |
| Файлы | Локальный диск: `storage/` (медиа), `archive/site/` (бекапы) |

## Схема

```
Браузер (SPA Quasar)
   │  /api/*, /storage/*        (в dev — через Vite-прокси :9000 → :8000;
   ▼                             в prod — через nginx; см. deploy/README.md)
FastAPI (backend/main.py + backend/api/*)
   ├─ backend/services/*        бизнес-логика
   ├─ backend/search/* → engine/  поиск
   ├─ backend/chat/*            умный чат
   ├─ backend/importer/*        импорт Excel → staging → PostgreSQL
   └─ get_connection()          psycopg3
   ▼
PostgreSQL (PostGIS)   +   диск: storage/, archive/
```

Внешние зависимости в рантайме: тайлы OpenStreetMap либо Yandex Maps
(подгружаются в браузере) и локальный `soffice` (только при экспорте).

## Бэкенд

- **`backend/main.py`** — сборка приложения: middleware (CORS из
  `ALBION_ALLOWED_ORIGINS`, rate-limit, лимит размера тела запроса), монтирование
  `/storage`, часть публичных роутов, подключение роутеров, опциональная раздача SPA
  (`ALBION_SERVE_SPA=1`).
- **`backend/api/`** — `APIRouter`-ы, сгруппированные по областям
  (`admin_*`, `account`, `chat`, `portfolio`, …). Админские — через
  `Depends(require_admin)`.
- **`backend/services/`** — вся бизнес-логика и доступ к БД. Ключевые:
  `data_service` (`get_connection`, данные конструкций), `settings_service`
  (внешний вид и `map_engine`), `home_service`, `news_service`, `contacts_service`,
  `media_service`, `portfolio_export`, `site_backup_service`, `auth_service`,
  `cms_url` (санитайз ссылок CMS).
- **`backend/migrations/`** — идемпотентные миграции; запускаются отдельным шагом.
- **`backend/search/`** — адаптер между сайтом и вендоренным движком `engine/`.
- **`backend/chat/`** — диалог: детерминированный разбор запроса, при
  необходимости LLM-fallback, хранение сессий.
- **`backend/importer/`** — конвейер импорта прайса (Excel → staging → PostgreSQL)
  и скачивание медиа.

## Фронтенд

- **`src/pages/`** — страницы; все маршруты ленивые (`src/router/routes.js`).
- **`src/boot/`** — boot-файлы: `settings.js` применяет настройки внешнего вида и
  `map_engine`, `tracking` шлёт визиты.
- **`src/config/`** — конфиг-реактивные значения: `mapConfig` (движок + ключ),
  `mapColors`, `availableMode`, `dynCount`.
- **`src/map/`** — `MapView.vue` выбирает движок; `useMap.js` (Leaflet) и
  `useYandexMap.js` (Yandex) реализуют один и тот же API; `popupContent.js` строит
  разметку попапа (с кэшем).
- **`src/composables/`** — общие синглтоны: `usePortfolio` (портфель),
  `usePhotoViewer` (просмотр фото), `useConstructionsFilter`, `useChatWorkspace`.

## Ключевые потоки

- **Публичные данные.** Страница запрашивает `/api/home`, `/api/settings`,
  `/api/constructions`, `/api/contacts`, `/api/news`, `/api/pages/:slug`.
- **Настройки.** `settings_service` (ключ `appearance`) → `/api/settings` →
  `boot/settings.js` применяет тему/карту. Сохранение в админке переприменяет их
  на лету.
- **Карта.** `/api/constructions` → `AdvertisingPage` фильтрует →
  `MapView.setConstructions` → движок рисует маркеры (Leaflet — дифф-обновление)
  → попап из `popupContent`.
- **Портфель.** `usePortfolio` (синглтон, состояние в `localStorage`) → экспорт
  через `POST /api/portfolio/export` (форматы doc/docx/odt/rtf/pdf, xls/xlsx/ods,
  csv/txt/md/json; документы собираются через LibreOffice).
- **Умный чат.** `POST /api/chat/message` → разбор запроса → поиск через
  `backend/search` → ответ + результаты, совместимые с картой/списком/портфелем.
- **Админка.** `/api/admin/*` под `require_admin`; там же медиатека, настройки,
  новости, контакты, пользователи, журнал, статистика, импорт/обновление базы.

## Состояние и данные

- **PostgreSQL** — конструкции и их доступность по месяцам, медиа-метаданные, CMS
  (новости/страницы/контакты/меню), пользователи и сессии, настройки, визиты.
- **Диск**: `storage/` — медиа (отдаётся по `/storage/…`); `archive/site/` —
  бекапы сайта (авто-бекап не чаще раза в 7 дней).
- **Браузер** (`localStorage`): портфель (`albion_portfolio`) и токены авторизации.
- **Фон**: планировщик авто-бекапа стартует на старте приложения; при нескольких
  воркерах создаётся один бекап благодаря advisory-lock.

## Безопасность (что уже есть)

- CORS по списку origin из `ALBION_ALLOWED_ORIGINS`.
- In-memory rate-limit на логинах/восстановлении/форме обратной связи.
- Лимит размера тела запроса и потоковое чтение загрузок (защита от memory-DoS).
- Санитайз CMS-ссылок и цветов на бэкенде (`cms_url`, `settings_service`).
- Отзыв сессий при смене роли/активности/пароля.
