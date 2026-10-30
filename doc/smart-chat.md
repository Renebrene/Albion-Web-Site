# Умный чат

Диалоговый поиск по конструкциям. Чат — **фасад над существующим поисковым
bridge**, а не отдельная поисковая система: основой служит детерминированный
парсер, LLM — только необязательный fallback. Код: `backend/chat/`,
`backend/api/chat.py`, `frontend/src/composables/useSmartChat.js`,
`frontend/src/components/chat/SmartChatPanel.vue`.

## Эндпоинты (`/api/chat`)

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/chat` | создать сессию (`{session_id}`) |
| POST | `/api/chat/message` | обработать сообщение |
| POST | `/api/chat/{session_id}/message` | то же, session_id из пути |
| POST | `/api/chat/reset` | сбросить сессию |

- Фронтенд create-эндпоинт **не вызывает** — сессия создаётся неявно в `/message`.
- Ошибки: `400` (не распознан запрос / нет периода для FREE), `404` (reset).
  `410` больше не используется: неизвестная сессия прозрачно создаёт новую.
- Модели — `extra="forbid"`; `message` — 1…2000 символов; `context.selected_months`
  ограничен 12 значениями 1…12, `portfolio_surface_ids` — 500.
- **Rate-limit** — prefix-правила `/api/chat` (по умолчанию 60/мин с IP) и
  `/api/search` (30/мин): `ALBION_RATE_CHAT_PER_MIN`, `ALBION_RATE_SEARCH_PER_MIN`.
  Лимитер процесс-локальный; за несколькими воркерами дополнительно нужен
  `limit_req` в nginx.

## Поток обработки сообщения (`ChatService.message`)

1. **Сессия** — новая при пустом `session_id`; неизвестный/просроченный `session_id`
   **прозрачно** создаёт новую сессию (перезапуск не ломает диалог).
2. **Идемпотентность** — при повторном `request_id` возвращается сохранённый ответ.
3. **Уточнение** — если висит `pending`, пробуем его разрешить; при неудаче — новый разбор.
4. **Разбор** (`_parse`): нормализация (`октябрь-ноябрь-декабрь` → список,
   `экран(ы…)` → `видеоэкран`), `QueryParser.parse`, восстановление района из фразы
   «…район» в поле города, `period_mode="ALL"` для списка/диапазона месяцев.
   Ошибка парсера добавляется в `warnings`, разбор продолжается.
5. **LLM-fallback** — только если парсер не дал уточнения и ограничений и LLM включена
   (`llm.extract`). Ответ проходит `backend/chat/query_validation.py`: пустые/`null`
   поля отбрасываются, проверяются месяцы 1…12, год 2000…2100, лимит 1…1000,
   цены/загрузка, `sort_by` и `availability`. Ответ, где все поля `null`, считается
   неуспешным — иначе поиск без ограничений вернул бы весь каталог.
   «До 90%»/«не более 90%» трактуется как `max_load=90` (а не
   `min_load=max_load=90`); «от 20% до 90%» — как диапазон.
6. **Контекст из UI** — `context.year` переопределяет год, `context.selected_months`
   подставляется, если в запросе нет периода.
7. **Ветка уточнения** — сохраняем `PendingSearchQuery`, отвечаем `pending=true` с
   вариантами («Статика/щиты», «Динамика/призматроны»).
8. **Ветка поиска** — `bridge.search_rich(query)`; при пустой выдаче формируются
   `suggestions` («Другие варианты…»); ответ собирается на русском
   (`format_answer`). **FREE требует период**: без месяца/периода — `400`.
9. **Ответ** — `actions` вычисляются по товарам, `message_id` генерируется заново;
   при `request_id` ответ кэшируется, отдельно пишется журнал (`log_turn`, обёрнут
   в `try/except` — журнал не ломает чат).

## Состояние сессий

- **По умолчанию — PostgreSQL** (`ALBION_CHAT_STORE=auto`): при доступной БД и
  применённой миграции сессии общие для всех воркеров. `ALBION_CHAT_STORE=memory`
  оставляет процесс-локальный `ChatStore` (только разработка/один воркер),
  `postgres` требует БД и падает на старте, если схема недоступна.
- Ходы одной сессии сериализуются: per-session `RLock` в памяти или
  `pg_advisory_lock` в PostgreSQL. `pending` и `last_result_ids` сохраняются
  **каждый ход**, независимо от `request_id`.
- `ChatStore` ограничен: `ALBION_CHAT_MAX_SESSIONS` (1000), до 20 ответов на
  сессию. PostgreSQL-store чистит истёкшие сессии и старые `chat_requests`
  (`ALBION_CHAT_REQUEST_RETENTION_DAYS`, по умолчанию 7).
- Миграции: `python -m backend.migrations.migrate_chat` и
  `python -m backend.migrations.migrate_chat_v2` (колонка `state_version`,
  индекс по `chat_requests.created_at`).
- **Журнал** (всегда, отдельно от сессий) — `chat_turns` (`migrate_chat_log`):
  вопрос/ответ, `chat_key`, признак `selected`. Пишется только текст, без медиа и
  перс. данных. Админ-эндпоинты: `GET /api/admin/chat-log`,
  `POST /api/admin/chat-log/selection`, `GET /api/admin/chat-log/export`.

## LLM-fallback (`backend/chat/llm.py`)

- По умолчанию **выключена** (`ALBION_CHAT_LLM_ENABLED`); провайдеры: `ollama`
  (default) и `openai`/`openai_compatible`. HTTP — только stdlib `urllib`.
- Env: `ALBION_CHAT_LLM_PROVIDER`, `ALBION_CHAT_LLM_BASE_URL`, `ALBION_CHAT_LLM_MODEL`
  (default `qwen3:14b`), `ALBION_CHAT_LLM_API_KEY`, `ALBION_CHAT_LLM_TIMEOUT`
  (default 10 с), `ALBION_CHAT_LLM_ANSWER_TIMEOUT` (20 с),
  `ALBION_CHAT_LLM_MAX_CONCURRENCY` (1), `ALBION_CHAT_LLM_QUEUE_TIMEOUT` (5 с),
  `ALBION_CHAT_LLM_KEEP_ALIVE` (`10m` — держать модель после последнего запроса и
  выгрузить после 10 минут простоя; значение `0` отключает удержание).
- **Два режима:** извлечение сущностей (`extract`, JSON) и живые ответы
  (`answer`, 2–4 предложения строго по найденным результатам). Второй отключается
  `ALBION_CHAT_LLM_ANSWERS=false`; при любой ошибке/таймауте используется
  детерминированный `format_answer`. Точное число найденных вариантов добавляет
  сервер, а не модель.
- Ответ LLM валидируется: только объект JSON, значения — по белому списку ключей
  (LLM не может задать SQL/URL/идентификаторы). Ошибка/timeout → возврат пустого
  результата; сервис либо использует правила, либо отдаёт `400`. **500 не отдаётся.**
- Для локального запуска на RTX 3060 12 ГБ проверены `qwen3:14b`
  (извлечение ≈2.5 с, ответ ≈3–4 с) и `qwen3:8b` (ответ ≈2 с, но JSON-извлечение
  ненадёжно). `qwen3:1.7b` быстрее, но хуже понимает русские формулировки.
- **Гибрид:** извлечение можно оставить локальным, а ответы отдать облаку.
  Базовые `ALBION_CHAT_LLM_*` задают извлечение; `ALBION_CHAT_LLM_ANSWER_*`
  переопределяют провайдера/URL/модель/ключ только для ответов:

  ```env
  ALBION_CHAT_LLM_PROVIDER=ollama
  ALBION_CHAT_LLM_MODEL=qwen3:14b

  ALBION_CHAT_LLM_ANSWER_PROVIDER=openai_compatible
  ALBION_CHAT_LLM_ANSWER_BASE_URL=https://openrouter.ai/api/v1
  ALBION_CHAT_LLM_ANSWER_MODEL=qwen/qwen-2.5-7b-instruct
  ALBION_CHAT_LLM_ANSWER_API_KEY=...
  ALBION_CHAT_LLM_ANSWER_MAX_CONCURRENCY=4
  ```

  Для облачных провайдеров телефоны и e-mail вырезаются из запроса до отправки.
  Активные провайдеры/модели (без ключей): `GET /api/admin/chat/llm`.
  Облачные профили для меню задаются JSON-переменной (ключи — только через
  `api_key_env`, в БД и ответах API их нет):

  ```env
  ALBION_LLM_PROFILES={"yandex-cloud":{"label":"YandexGPT Lite","provider":"openai_compatible","base_url":"https://llm.api.cloud.yandex.net/v1","model":"gpt://<folder>/yandexgpt-lite/latest","api_key_env":"YANDEX_API_KEY"},"openrouter-qwen25":{"label":"Qwen2.5 7B (OpenRouter)","provider":"openai_compatible","base_url":"https://openrouter.ai/api/v1","model":"qwen/qwen-2.5-7b-instruct","api_key_env":"OPENROUTER_API_KEY"}}
  ```
- **Выбор модели в админке:** `Администрация → Журнал умного чата`
  (`/administration/chat-log`) — два селектора «Разбор запросов» и «Живые ответы».
  В списке: установленные модели Ollama и облачные профили. Выбор хранится в
  `site_settings['chat_llm']`; API — `GET/PUT /api/admin/chat/llm`.
  Облачные профили задаются оператором в `ALBION_LLM_PROFILES` (JSON), ключи —
  только через `api_key_env`, в БД не попадают.
- Проверена локальная **YandexGPT-5-Lite-8B-instruct Q4_K_M** (GGUF, 4.6 ГБ,
  контекст 32k): извлечение ≈2.2 с, ответ ≈1 с, хороший русский. Лицензия
  кастомная (`yandexgpt-5-lite-8b`) — перед коммерческим использованием
  проверьте условия LICENSE.

## UI

- `frontend/src/services/chatApi.js` — `sendChatMessage` (`POST /chat/message`),
  `resetChat`.
- `frontend/src/composables/useSmartChat.js` — реестр чатов по `chatKey` (не
  синглтон), снапшот в `sessionStorage` (`albion_smart_chat_v2_<key>`, последние 50
  сообщений), `request_id` через `crypto.randomUUID()`.
- `frontend/src/composables/useChatWorkspace.js` — список чатов общий для окна в
  шапке и страницы `/chat`; сохранение в ЛК (`GET/PUT/DELETE /api/account/chats`,
  таблица `account_chats`), очистка с задержкой 10 с и отменой.
- `frontend/src/components/chat/SmartChatPanel.vue` — варианты `compact` (шапка) и
  `page`; результаты группируются как на карте (`groupByPoint`/`groupSides`); клик по
  фото открывает общий `usePhotoViewer`; портфель — через `usePortfolio`.
- В ответе есть `answer_source` (`rules` или `llm`): UI может показывать, что текст
  переформулирован моделью, сохраняя тот же блок результатов.
- Страница `/chat` (`SmartChatPage.vue`) — сетка из 1–4 независимых чатов.

## Словари синонимов

Словарь (`types`, `cities`, `keywords`) задаёт, какие слова парсер и чат
считают форматом, городом и ключевым словом. По умолчанию берётся
`engine/dictionary/synonyms.json`; правки из админки
(`Настройки → Словари синонимов`) хранятся в `site_settings['synonyms']`
и не меняют файл в репозитории. Сброс удаляет запись, и снова действует
упакованный словарь.

API: `GET/PUT /api/admin/settings/synonyms`,
`POST /api/admin/settings/synonyms/reset` (только admin). Перед записью
словарь проверяется `SynonymDictionary.from_dict` (структура и конфликты
алиасов), поэтому сломанное значение в БД не сохранится. `ChatService`
сравнивает `updated_at` записи перед каждым сообщением и пересобирает
парсер — правку видят все uvicorn-воркеры.

## Грабли

- **Мультиворкер:** PostgreSQL-store включается автоматически (`ALBION_CHAT_STORE=auto`)
  после миграции; `memory` годится только для одного воркера.
- **Районы хранятся как города** (например, «ОКТЯБРЬСКИЙ РАЙОН» — это `city`); сервис
  восстанавливает район из фразы «<прилагательное> район».
- **Доступность берётся за все месяцы года**, а не только за запрошенный; фильтры по
  цене/загрузке применяются в Python (цена в БД — TEXT).
- `source="fallback"` объявлен в модели, но сервисом не выставляется (реально
  `rules`/`llm`).
- `message.actions.map/list` UI использует для перехода на карту/список;
  `media/portfolio/export` пока только формируются на бэкенде.
- **`chat=1`:** `resultIds` сохраняются в `sessionStorage` (`albion_chat_result_ids`) и
  переживают F5; `chat`/`mode` не теряются при изменении фильтров, а смена `mode` на
  уже открытой странице применяется watcher-ом.
- Месяцы в чате берутся из `query.month/months` ответа и `monthly_*` результатов, а
  не из глобального списка карты.
- Env-флаги чата читаются при импорте `backend/api/chat.py` → выставлять до старта процесса.
- Миграции: `python -m backend.migrations.migrate_chat`,
  `…migrate_chat_v2` и `…migrate_chat_log`.
