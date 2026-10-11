# Фронтенд

Обзор приложения: сборка, роутер, страницы, boot, layouts, компоненты, настройки.
Код — в `frontend/`.

## Стек и сборка

- Quasar 2.29 + Vue 3 + vue-router; сборка — Quasar CLI (Vite).
- `frontend/quasar.config.js`:
  - `boot: ['tracking']`, `css: ['app.scss']`, `extras: ['material-icons']`
    (`roboto-font` убран — шрифты грузятся лениво, см. `config/fontLoader.js`);
  - `build.vueRouterMode: 'history'`;
  - `build.env.clientPrefix: ['QCLI_', 'VITE_']` — добавляет `VITE_` к дефолтному
    `QCLI_`, чтобы `VITE_YANDEX_MAPS_KEY` попадал в бандл (значение **вшивается при сборке**);
  - `devServer.proxy`: `/api` и `/storage` → `http://127.0.0.1:8000`;
  - `allowedHosts: ['albion.cloudpub.ru']`.
- `frontend/index.html` — CSP в meta (домены Яндекса, OSM-тайлы, Google Fonts;
  в dev добавляются `localhost`/`127.0.0.1`). Новые внешние хосты — правка и здесь,
  и в `deploy/nginx.conf.example`.
- Скрипты (`package.json`): `dev`, `build`, `lint` (`oxfmt && oxlint --fix`),
  `lint:check` (`oxfmt --check && oxlint`). `engines.node: ^22.22.0 || ^24.0.0`.

## Роутер (`src/router/routes.js`)

Все маршруты ленивые. Публичный родитель — `MainLayout`, админский — `AdministrationLayout`;
дети админки (кроме входа) помечены `meta.requiresAdmin`.

| Путь | Страница |
|---|---|
| `/` | `HomePage` (главная, `HomeSlider`) |
| `vozmozhnosti` | `AdvertisingPage` — карта + список |
| `napravleniya` | `DirectionsPage` (заглушка) |
| `novosti`, `novosti/:slug` | `NewsPage`, `NewsDetailPage` |
| `o-kompanii` | `AboutPage` |
| `kontakty` | `ContactsPage` |
| `chat` | `SmartChatPage` — умный чат |
| `account` | `AccountPage` — личный кабинет |
| `informaciya` | `InfoPage` — закладки «Информация» |
| `portfolio` | `PortfolioPage` |
| `/administration` | `AdministrationLoginPage` |
| `/administration/{dashboard, media, constructions, chat-log, base, site, contacts, site-menu, settings, news, home, info, about, users, audit, statistics}` | соответствующие админ-страницы |
| `/:catchAll(.*)*` | `ErrorNotFound` |

`router/index.js`: history из `QUASAR_VUE_ROUTER_MODE`; глобальный `beforeEach` —
если `meta.requiresAdmin` и нет `sessionStorage['albion_admin_token']` → редирект на
`/administration`.

## Страницы (`src/pages/`)

- Публичные: главная (`HomeSlider`), рекламные возможности (карта/список),
  новости, о компании, контакты, умный чат, личный кабинет, «информация», портфель.
- Админка: «Администрирование» (плитки), «Обновление базы», «Конструкции», «Медиатека»,
  «Главная страница», «Настройки», «Меню и подвал», «Бекап сайта», «Контакты»,
  «Новости», «Информация», «О компании», «Пользователи», «Журнал действий»,
  «Журнал умного чата», «Статистика», вход.
- Осиротевшие (вне роутера): `IndexPage`, `SecondPage`, `PlaceholderPage`,
  `AdministrationPlaceholderPage` — не используются.

## Boot-файлы (`src/boot/`)

- **`tracking.js`** — зарегистрирован в `boot`; на `router.afterEach` шлёт визит
  `POST /api/track` (sendBeacon/fetch), пропуская `/api`, `/storage`, `/administration`.
- **`settings.js`** — **не** в `boot`-массиве, подключается вручную (`MainLayout`,
  админ-настройки, `MapView`). Тянет `GET /api/settings`, выставляет CSS-переменные
  `--albion-*` и реактивные конфиги; обновляет на `focus`/`visibilitychange` (кроме
  админки) с троттлингом.

## Layouts (`src/layouts/`)

- **`MainLayout`** — `AppHeader` + `router-view` + `AppFooter` + `PhotoViewer`;
  измеряет высоты шапки/подвала в CSS-переменные; на `onMounted` применяет настройки.
- **`AdministrationLayout`** — только контейнер и `router-view`, без шапки/подвала.

## Компоненты (`src/components/`)

`layout/` (шапка, подвал — меню из `/api/site-menu`), `home/` (секции главной,
`HomeSlider`), `filters/` (`FiltersSidebar`), `workspace/` (`MapSearch`,
`PointSearchPanel`), `portfolio/` (`PortfolioPanel`), `common/` (`PhotoViewer`),
`chat/` (`SmartChatPanel`, `ChatSaveButton`), `news/`, `contacts/`,
`admin/` (`MediaPicker`, `NewsMediaField`, `VisitChart`).
Смежное: `src/map/` — движки и попапы (см. `doc/map.md`).

## Config-модули (`src/config/`)

`mapConfig` (движок карты + ключ Яндекса), `mapColors` (цвета/режим точек),
`availableMode` (режим доступности: `surfaces`/`sides`), `dynCount` (показ «динамика (N)»),
`fontLoader` (ленивая загрузка шрифтов).

## Настройки с сервера и состояние

- `boot/settings.js` → `GET /api/settings`: `font_*`, `color_*`, `radius_*`, `map_engine`,
  `map_color_mode`, `map_color_free/busy/mixed`, `available_mode`, `show_dyn_count` →
  CSS-переменные и ref'ы конфигов. Дефолты — в `:root` (`src/css/app.scss`).
  Админка применяет изменения сразу после сохранения.
- **localStorage:** портфель (`albion_portfolio`), токен аккаунта (`albion_account_token`).
- **sessionStorage:** токен админки (`albion_admin_token`), состояние чата
  (`albion_smart_chat`).

## Стили и линт

- Глобальный `src/css/app.scss`: дефолтные `--albion-*`, базовые правила, стили
  маркеров/попапов Leaflet, карточек. `src/css/quasar.variables.scss` — Sass-переменные Quasar.
- `.oxfmtrc.json`: `printWidth 80`, без точек с запятой, одинарные кавычки,
  `htmlWhitespaceSensitivity: strict`. `.oxlintrc.json`: плагины vue/import/eslint/
  promise/unicorn, активна только `correctness`.

## Грабли

- `settings.js` лежит в `boot/`, но **не** подключён в `quasar.config.js` — не
  переносить в `boot`-массив без проверки побочек.
- Env-префиксы Quasar: клиенту отдаются `QCLI_*` (+ добавленный `VITE_*`); `VITE_*`
  вшивается в бандл — после правки `.env.local` нужна пересборка.
- Прокси `/api` и `/storage` требует поднятого бэкенда на `:8000`.
- В дереве много `*.bak`/`*.save` (`AdvertisingPage.vue.*`, `MapView.vue.bak`,
  `useMap.js.bak`, `PointSearchPanel.vue.bak`, `routes.js.save`) — вне графа импортов,
  но мусорят; стоит вычистить.
