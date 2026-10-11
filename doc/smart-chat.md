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
- Ошибки: `400` (не распознан запрос / нет периода для FREE), `410` (сессия не
  найдена), `404` (reset).
- Модели — `extra="forbid"`; `message` — 1…2000 символов.
- **Rate-limit для чата не задан** (в in-memory лимитере `main.py` путей `/api/chat*` нет).

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
   (`llm.extract`); иначе — `ValueError` «Не удалось распознать запрос…».
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

- **По умолчанию — процесс-локальный** `ChatStore`: TTL **45 минут**, кэш до **20**
  ответов на сессию, `pending` и `last_result_ids`. Просроченные удаляются при обращении.
- **Опционально — PostgreSQL** (`postgres_store.py`), включается `ALBION_CHAT_PERSIST`
  (после миграции). `get()` берёт строку `FOR UPDATE`; ответы — upsert по
  `(session_id, request_id)`. Таблицы: `chat_sessions`, `chat_requests`.
- **Журнал** (всегда, отдельно от сессий) — `chat_turns` (`migrate_chat_log`):
  вопрос/ответ, `chat_key`, признак `selected`. Пишется только текст, без медиа и
  перс. данных. Админ-эндпоинты: `GET /api/admin/chat-log`,
  `POST /api/admin/chat-log/selection`, `GET /api/admin/chat-log/export`.
- Явного фонового удаления просроченных сессий в коде нет.

## LLM-fallback (`backend/chat/llm.py`)

- По умолчанию **выключена** (`ALBION_CHAT_LLM_ENABLED`); провайдеры: `ollama`
  (default) и `openai`/`openai_compatible`. HTTP — только stdlib `urllib`.
- Env: `ALBION_CHAT_LLM_PROVIDER`, `ALBION_CHAT_LLM_BASE_URL`, `ALBION_CHAT_LLM_MODEL`,
  `ALBION_CHAT_LLM_API_KEY`, `ALBION_CHAT_LLM_TIMEOUT` (default 10 с).
- Ответ валидируется: только объект JSON, значения — по белому списку ключей
  (LLM не может задать SQL/URL/идентификаторы). Ошибка/timeout → возврат пустого
  результата; сервис либо использует правила, либо отдаёт `400`. **500 не отдаётся.**

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
- Страница `/chat` (`SmartChatPage.vue`) — сетка из 1–4 независимых чатов.

## Грабли

- **Мультиворкер:** store по умолчанию процесс-локальный — сессии не общие, пока не
  включён `ALBION_CHAT_PERSIST` (+ миграция).
- **Районы хранятся как города** (например, «ОКТЯБРЬСКИЙ РАЙОН» — это `city`); сервис
  восстанавливает район из фразы «<прилагательное> район».
- **Доступность берётся за все месяцы года**, а не только за запрошенный; фильтры по
  цене/загрузке применяются в Python (цена в БД — TEXT).
- `source="fallback"` объявлен в модели, но сервисом не выставляется (реально
  `rules`/`llm`).
- Поле `message.actions` (map/list/media/portfolio/export) формируется, но **UI его не
  использует** — экспорт/карта из чата через него не подключены.
- **Несогласованность `chat=1`:** `AdvertisingPage.vue` при `route.query.chat === '1'`
  читает `resultIds` из `useChatWorkspace`, но этот композабл его не экспортирует, и
  саму ссылку `/vozmozhnosti?chat=1` никто не формирует — требует починки.
- Env-флаги чата читаются при импорте `backend/api/chat.py` → выставлять до старта процесса.
- Миграции: `python -m backend.migrations.migrate_chat` и `…migrate_chat_log`.
