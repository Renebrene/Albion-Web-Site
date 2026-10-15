# Личный кабинет и авторизация (сейчас скрыты)

> **Статус: скрыт, но не удалён.** Интерфейс входа и кабинета выключен
> флагом `ACCOUNT_UI_ENABLED = false` в
> [`frontend/src/config/features.js`](../frontend/src/config/features.js).
> Портфель и умный чат работают **в рамках сессии браузера**
> (localStorage/cookies). Бэкенд, таблицы и код страниц на месте — вернуть
> кабинет можно, поставив флагу `true`.

Документ описывает, что именно есть в кабинете, чтобы решение можно было
пересмотреть осознанно.

## Что умеет кабинет

| Возможность | Где в UI | API |
|---|---|---|
| Регистрация по логину/паролю | `/account?tab=register` | `POST /api/account/register` |
| Вход | `/account` | `POST /api/account/login` |
| Выход | меню аккаунта в шапке | `POST /api/account/logout` |
| Текущий пользователь | — | `GET /api/account/me` |
| Восстановление по секретной фразе | `/account` | `POST /api/account/recover` |
| Реквизиты (для выгрузки портфеля) | раздел «Реквизиты» | `PUT /api/account/requisites` |
| Сохранение портфеля | панель портфеля → «Сохранить» | `GET/PUT/DELETE /api/account/portfolio` |
| Сохранение истории чата | панель чата | `GET/PUT/DELETE /api/account/chats` |
| Заявки | личный кабинет | `GET/POST /api/account/requests` |

Профиль хранит логин, роль и `requisites` (JSONB: название организации,
ИНН, КПП и т.п. — подставляются в выгрузку портфеля).

## Данные

| Таблица | Назначение | Колонки (основные) |
|---|---|---|
| `user_accounts` | учётки кабинета (**не** путать с `admin_users` — учётками панели) | `login`, `password_hash`, `role`, `secret_phrase_hash`, `is_active`, `requisites` (JSONB) |
| `account_portfolios` | сохранённый портфель (payload JSONB) | `account_id` → `user_accounts` ON DELETE CASCADE |
| `account_chats` | сохранённая история чата (payload JSONB) | `account_id` → `user_accounts` CASCADE |
| `client_requests` | заявки клиентов | `account_id`, `title`, `surface_id`, `payload` (JSONB), `status` |

Миграция схемы — `backend/migrations/migrate_accounts.py`; сид-миграция
аккаунта администратора — отдельная (см. `doc/database.md`).

## Админка

- `GET /api/admin/cabinet-users` — список зарегистрированных в кабинете
  и число их заявок. Показывается на странице **Админка → Пользователи**
  (`AdministrationUsersPage.vue`), отдельно от учёток панели
  (`admin_users`, `/administration/users`).
- Учётные записи панели управления ведутся в `admin_users` и к кабинету
  отношения не имеют.

## Как вернуть кабинет

1. В `frontend/src/config/features.js` поставить `ACCOUNT_UI_ENABLED = true`.
2. Пересобрать фронтенд (`cd frontend && bun run build`) или дождаться HMR
   в dev-режиме.

После этого снова появятся: вход/регистрация в меню шапки, адрес
`/account` (без флага он редиректит на `/portfolio`), кнопка «Сохранить» в
панели портфеля и подсказки про вход. Бэкенд трогать не нужно — он никогда
не отключался.

## Что изменилось при скрытии

- Шапка: убраны пункты ВОЙТИ / РЕГИСТРАЦИЯ / ВЫХОД и данные пользователя;
  пункт ПОРТФЕЛЬ ведёт на публичную `/portfolio`.
- Убран пункт **АДМИНКА** из шапки (и кнопка в кабинете): администратор
  заходит напрямую на `/administration`.
- Шапка больше не дёргает `/api/account/me`, пока интерфейс входа выключен.
- Заявки вынесены в публичную форму — см. `doc/smart-chat.md` и раздел
  «Заявки» ниже.

## Заявки

Заявки теперь можно отправить **без входа** (заказчик просил оставить их
вне кабинета): публичный эндпоинт `POST /api/requests` пишет в
`client_requests` с `account_id = NULL` и контактами в `payload`.
Внутри кабинета (если его включат) заявки по-прежнему привязываются к
аккаунту через `/api/account/requests`.
