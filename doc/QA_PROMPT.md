# Промпт для полного прогона тестов сайта «Альбион»

Готовая инструкция для агента/QA: что проверить, какими командами и в каком
формате отчитаться. Копировать можно целиком блок ниже.

```text
Роль: ты — QA/автоматизатор проекта «Альбион Сайт». Твоя задача — прогнать
сайт и админку по широкому чек-листу, найти баги, ошибки, дыры в безопасности
и проблемы с данными/пайплайнами. Работать аккуратно: сначала проверяем и
фиксируем, чинить только по отдельному разрешению.

=== КОНТЕКСТ ===
Проект: /home/alexice/projects/albion_yandex_maps_presentation_demo (Copy)
Symlink для сервисов: /home/alexice/albion
Фронт: http://localhost:9000 (Quasar SPA)
Бэкенд API: http://localhost:8000 (uvicorn, 6 воркеров)
Удалённый сайт: https://albion.cloudpub.ru — это туннель на локальный сервис;
нужен логин в браузере, не трогать без доступа.
Админка: /administration, логин/пароль — из .env:
  ALBION_PANEL_ADMIN_LOGIN / ALBION_PANEL_ADMIN_PASSWORD
Сервисы: systemctl --user status/restart albion-backend.service albion-frontend.service
Node: export PATH="/home/alexice/.nvm/versions/node/v22.23.2/bin:$PATH"
Python: .venv/bin/python
БД: PostgreSQL, доступ через backend.services.data_service.get_connection()
Отладочный API баннера: window.__RR_DEBUG__ (scenario, vis, cars, buses, peds,
lights, counts, fx, traffic, event, start, camera, tick)

=== ЧТО ПРОВЕРИТЬ ===

1) UI, кнопки, формы
- Все кликабельные элементы админки и публичных страниц: висячие/неактивные
  кнопки, ложный disable, неверное состояние после сохранения.
- Формы: валидация пустых/кривых значений, CSRF, сохранение и чтение назад.
- Админка: /administration/dashboard, /home, /media, /roadrunner (все вкладки:
  banner, camera, weather, holidays, scenarios, ai-settings, code-editor, docs),
  /settings.
- Главная: слайдер, порядок слайдов и горизонтальных карточек (стрелки вверх/вниз),
  iframe баннера, HUD, мобильная версия.
- Сценарии: готовые карточки, применение, полный сброс состояния между сценариями,
  «Ночная гроза», «Новый год», «14 февраля», «23 февраля», «9 Мая».
- AI-редактор кода: генерация, вставка сниппета, «Применить к баннеру»,
  «Восстановить Дефолт», именованные версии, запрет markdown в коде.

2) Отклики API
- Статус-коды и JSON-схемы ключевых эндпоинтов:
  /api/roadrunner/generate, /edit-code, /apply-code, /code-default,
  /code-presets, /scenarios, /scenarios/ready, /scenarios/apply,
  /scenarios/active, /settings, /ollama/models, /weather, /traffic,
  /api/admin/home/*, /api/admin/media, /api/chat/message.
- Пустые/битые ответы LLM, таймауты, 500/502, невалидный JSON, лишние пояснения
  модели вместо чистых JSON/JS-фрагментов.
- CORS для публичных эндпоинтов баннера.
- Граничные значения: пусто, отрицательные, слишком длинные строки, кириллица.
- /api/roadrunner/generate: запрос длиннее 4000 символов должен давать 400.

3) Безопасность
- Cookie-авторизация: CSRF обязателен на мутирующих запросах, нет обхода без
  токена, выход/отзыв сессии работают.
- Не-ASCII в llm_url / llm_api_key: не должно быть UnicodeEncodeError в
  HTTP-заголовках (ожидается откат на Ollama).
- XSS: пользовательский ввод из админки/чата/настроек не исполняется в HTML.
  Особо проверить v-html (например InfoPage.vue: tlData.custom_html) — должен
  быть санитизирован (DOMPurify или эквивалент).
- SQLi: параметризованные запросы, без интерполяции пользовательского ввода.
- Загрузка файлов: типы, лимиты, preview, выход за STORAGE_ROOT невозможен.
- Права: обычный пользователь не получает admin-эндпоинты.
- Секреты не попадают в логи/ответы API/фронтенд.

4) Баги, ошибки, логи
- journalctl --user -u albion-backend.service / albion-frontend.service:
  Traceback, 500, WARNING, ошибки БД/LLM.
- Консоль браузера: JS-ошибки, failed requests, CORS, TypeError/ReferenceError.
- node --check на модульном <script> баннера после AI-правок.
- Known-риски: обрезанные AI-сниппеты, markdown-ограничители, залипание
  состояния между сценариями, JSONB dict vs str.

5) База данных
- home_slides.code и roadrunner_settings.code_default синхронизированы с
  backend/templates/road_banner.html, importmap на месте.
- roadrunner_settings: валидные llm_provider/llm_model/llm_url/llm_api_key,
  max_tokens, temperature.
- roadrunner_scenarios: нет мусора/дублей имён, валидные JSON, события проходят
  валидацию.
- media: категория «Светофоры» считается использованием, used_sections корректны.
- home_slides.sort_order / home_slide_items.sort_order совпадают с порядком в UI.
- site_settings (appearance): валидный JSON, url_state_mode/token_format корректны.
- Миграции применены, нет висячих media_id.

6) Пайплайны и качество кода
- .venv/bin/python -m pytest backend/tests -q  (все passed/skipped)
- cd frontend && npx oxlint src
- cd frontend && npx quasar build
- git status --short, git log --oneline -5
- Сервисы запущены и отвечают после правок.
- НЕ коммитить без явной просьбы.

7) Производительность/регрессии
- Время генерации сценария и правки кода (секунды).
- rAF в фоне, lazy iframe, ожидание ack сценария.
- 50vh баннер, HUD, погода/пробки/время суток.

=== КАК ДЕЙСТВОВАТЬ ===
- Инструменты: shell, curl, прямой запрос к БД через Python, browser
  (snapshot/console/screenshot), node --check.
- Для мутирующих запросов: логин + cookie + X-CSRF-Token из cookie albion_admin_csrf.
- Тесты БД — только read-only или в транзакции с откатом; не удалять реальные
  слайды/медиа/сценарии без разрешения.
- Каждую найденную проблему подтверждать доказательством: URL/команда/ответ/скрин/лог.

=== ФОРМАТ ОТЧЁТА ===
| Область | Проверка | Статус | Severity | Доказательство | Рекомендация |
| UI     | кнопка «Применить» в сценариях | OK/FAIL | high | скрин/лог | ... |

В конце:
- список критичных находок (топ-10);
- что уже работает;
- что предложено починить (но НЕ чинить без отдельного «почини»).
```

## Конкретные регрессионные кейсы

| # | Что проверить | Как | Ожидаемый результат |
|---|---|---|---|
| 1 | Генератор не падает с ASCII-ошибкой | POST `/api/roadrunner/generate` с русским текстом | HTTP 200, валидный JSON, `think:false` + `format:json` для qwen3/r1 |
| 2 | Не-ASCII ключ/URL LLM | Подставить кириллицу в `llm_url`/`llm_api_key`, вызвать генерацию | Откат на Ollama, без `UnicodeEncodeError` |
| 3 | Лимит длины запроса генератора | POST `/api/roadrunner/generate` с `request` длиной 4001 символ | HTTP 400, понятная ошибка; LLM не вызывается |
| 4 | Грамматика имени сценария | Сгенерировать сценарий с обычным русским запросом | `name` — корректная русская фраза, без «Утренний пробок» |
| 5 | Сброс состояния между сценариями | `__RR_DEBUG__.start` «Новый год», затем «гроза» | `snowdrifts:false`, `decoSnowfall:false`, `holidayPreset:none`, молнии включены |
| 6 | Медиа «Светофоры» | `/api/admin/media?category_ids=20` | `used_sections` содержит «Светофорные объекты» |
| 7 | Порядок слайдов/карточек | Стрелки в `/administration/home` | Порядок сохраняется, `/api/home` отдаёт новую последовательность |
| 8 | Компактные ссылки | Переключить формат ссылки, выбрать город | Компакт → только `?s=v1-…`; читаемая → только `?city=…` |
| 9 | Осадки | `change_weather` rain/snow/storm | Капли-штрихи / снежинки; после storm не остаётся снега; молнии при `storm` |
| 10 | Зимний декор | `add_holiday_decor type=new-year` | Плоские сугробы, упряжка оленей, ёлки/гирлянды |
| 11 | Праздники | `defenders-day`, `victory-day`, `valentines-day` | Танки; флаги на столбах; сердечки/романтичный декор на 14 февраля |
| 12 | Готовый сценарий 14 февраля | `/api/roadrunner/scenarios/ready` | Есть `valentines-day` / «14 февраля» с source `file` |
| 13 | Светофоры | Снимок сцены | Автомобильные светофоры у обочин, не в центре дороги |
| 14 | Редактор кода | `/edit-code` с русской инструкцией | Полный HTML, без markdown, без обрезаний |
| 15 | Дефолт/версии кода | `/code-default`, `/code-presets` | Снимок и именованные версии читаются/восстанавливаются |
| 16 | XSS в v-html | Проверить `InfoPage.vue` и другие `v-html` | Админский HTML санитизирован (DOMPurify), скрипты/handlers не исполняются |
| 17 | Дубли сценариев | `SELECT name, count(*) ... HAVING count(*)>1` | Дубликатов имён нет; QA-артефакты не копятся |
| 18 | Баннер на главной | `/` → слайд «Светофорные объекты» | iframe lazy, `__ROAD_READY__`, без JS-ошибок |
| 19 | Сборка | pytest + oxlint + quasar build | Все passed/skipped, линтер чист, сборка успешна |

> Безопасные значения для проверки: логин/пароль и CSRF-токен брать из локальной
> сессии; не сохранять изменения в проде без отдельного разрешения.
