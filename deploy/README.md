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
| `ALBION_SMTP_HOST/PORT/USER/PASSWORD/FROM` | SMTP для уведомлений о заявках (адрес получателя задаётся в админке: Пользователи → Заявки) |
| `ALBION_SMTP_TLS` | `0` — отключить STARTTLS (по умолчанию включён) |

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

## Тесты

```bash
pip install -r requirements-dev.txt
pytest backend/tests          # интеграционные: API, auth, БД, миграции, upload, export
```

Тестам нужна PostgreSQL: без неё соответствующие кейсы помечаются `skip`.

Браузерный смоук (нужны Chrome и запущенный фронтенд):

```bash
uv run --with websockets python deploy/browser-smoke.py --base http://localhost:9000
```

## Планировщик авто-бекапа и multiworker

Backend при старте поднимает фоновый поток авто-бекапа сайта
(`site_backup_service.start_scheduler`, раз в 7 дней). При запуске
uvicorn с несколькими worker'ами поток стартует в каждом процессе, но
создание бекапа защищено **advisory-блокировкой PostgreSQL**
(`pg_try_advisory_lock`): бекап создаёт ровно один worker, остальные
пропускают итерацию. Дополнительно не чаще раза в 7 дней.

Это покрыто тестом `backend/tests/test_site_backup_scheduler.py`
(параллельный вызов → создание один раз).

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

## Службы systemd (автозапуск)

Готовые юниты — `deploy/systemd/`. Запускают ровно то же, что и руками:
backend (`uvicorn`, :8000) и frontend (dev-сервер Quasar, :9000, проксирует
`/api`, `/storage`, `/robots.txt`, `/sitemap.xml` на backend).

Установка (пользовательские службы — root не нужен):

```bash
# 1. Симлинк без пробелов и скобок: systemd не переваривает
#    «albion_yandex_maps_presentation_demo (Copy)» в WorkingDirectory.
ln -sfn "/home/alexice/projects/albion_yandex_maps_presentation_demo (Copy)" \
        /home/alexice/albion

# 2. Юниты + запуск
cp deploy/systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now albion-backend.service albion-frontend.service
```

Автозапуск при загрузке требует linger (один раз, уже включён):

```bash
loginctl show-user "$USER" | grep Linger      # Linger=yes
sudo loginctl enable-linger "$USER"           # если выключен
```

Управление и логи:

```bash
systemctl --user status  albion-backend albion-frontend
systemctl --user restart albion-frontend        # после правок в коде фронта
journalctl --user -u albion-backend -f
```

Чтобы применить правки в `deploy/systemd/*.service`, скопируйте файл в
`~/.config/systemd/user/` и выполните `systemctl --user daemon-reload`.

**Вариант без dev-сервера (прод).** Соберите SPA (`npm run build`) и не
запускайте `albion-frontend`: backend умеет сам отдавать `frontend/dist/spa`
историю с fallback — включите `ALBION_SERVE_SPA=1` в `.env` и направьте
трафик на порт backend. Тогда достаточно одной службы.

### Системные службы (старт до входа любого пользователя)

Вариант выше — пользовательские службы: они стартуют при загрузке, если у
пользователя включён linger. Если нужен старт системно (например, сервер
перезагрузился и никто не входил, или linger отключён), есть готовые
системные юниты — `deploy/systemd/system/` — и установщик:

```bash
sudo deploy/systemd/install-system.sh
```

Скрипт создаёт симлинк, копирует юниты в `/etc/systemd/system`, включает их,
запускает и **отключает пользовательские копии** (иначе конфликт по портам
8000/9000). Идемпотентен — можно запускать повторно после правок юнитов.

Управление — как у системных служб:

```bash
sudo systemctl status albion-backend albion-frontend
sudo systemctl restart albion-frontend
journalctl -u albion-backend -f
```
