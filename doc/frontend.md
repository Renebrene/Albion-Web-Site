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
- Осиротевшие страницы (`IndexPage`, `SecondPage`, `PlaceholderPage`,
  `AdministrationPlaceholderPage`) удалены как неиспользуемые.

## Boot-файлы (`src/boot/`)

- **`tracking.js`** — зарегистрирован в `boot`; на `router.afterEach` шлёт визит
  `POST /api/track` (sendBeacon/fetch), пропуская `/api`, `/storage`, `/administration`.
- **`settings.js`** — **не** в `boot`-массиве, подключается вручную (`MainLayout`,
  админ-настройки, `MapView`). Тянет `GET /api/settings`, выставляет CSS-переменные
  `--albion-*` и реактивные конфиги; обновляет на `focus`/`visibilitychange` (кроме
  админки) с троттлингом.

## Layouts (`src/layouts/`)

- **`MainLayout`** — `AppHeader` + `router-view` + `AppFooter` + `PhotoViewer` +
  `CookieConsent`; измеряет высоты шапки/подвала в CSS-переменные; на `onMounted`
  применяет настройки.
- **`AdministrationLayout`** — только контейнер и `router-view`, без шапки/подвала.

## Компоненты (`src/components/`)

`layout/` (шапка, подвал — меню из `/api/site-menu`), `home/` (секции главной,
`HomeSlider` + `slides/`), `filters/` (`FiltersSidebar`), `workspace/` (`MapSearch`,
`PointSearchPanel`), `portfolio/` (`PortfolioPanel`), `common/` (`PhotoViewer`),
`chat/` (`SmartChatPanel`, `ChatSaveButton`), `news/`, `contacts/`,
`admin/` (`MediaPicker`, `NewsMediaField`, `VisitChart`).
Смежное: `src/map/` — движки и попапы (см. `doc/map.md`).

### Слайды главной (`components/home/slides/`)

`HomeSlider` остаётся «хозяином» страницы: грузит данные (`/api/home`, новости,
статистику), держит индекс слайда, колесо/клавиатуру и переключает `slide.kind`.
Сами слайды — отдельные компоненты:

| Компонент | `slide.kind` | Что получает |
|---|---|---|
| `GeoSlide` | `geo` | `slide`; наружу — `v-model:expanded` (модалка), методы `move(dir)` / `reset()` через ref |
| `NewsSlide` | `news` | `slide` + загруженный список `news` |
| `FeedbackSlide` | `form` | `slide` (форма и отправка внутри) |
| `TextSlide` | любой другой (запасной) | `slide` |

Тонкости, на которых легко ошибиться:

- `ref` на компонент **внутри `v-for` даёт массив** — в `HomeSlider` для этого
  есть `geoSlideApi()`; состояние модалки geo-слайда живёт в родителе
  (`geoExpanded`), потому что от него зависит перехват колеса и клавиатура;
- `@keyframes geo-marquee` обязан лежать в том же компоненте, что и
  `animation:` — Vue переименовывает имена анимаций в scoped-стилях.

Правила при добавлении нового типа слайда:

- компонент получает **весь** `slide` (включая `settings` из админки) и сам
  собирает кнопки через `slides/slideButtons.js` — правок в родителе не нужно;
- новый `kind` добавляется одной веткой в цепочке `v-if` в `HomeSlider`;
- у компонентов нет корневой обёртки: заголовок, текст и действия остаются
  прямыми элементами `.slide-inner` (иначе ломаются отступы `gap`);
- стили слайда — `scoped` внутри компонента; базовые классы (`.slide-title`,
  `.slide-text`, `.slide-btn`) продублированы, потому что scoped-стили родителя
  на дочерние элементы не действуют.

## Config-модули (`src/config/`)

`mapConfig` (движок карты + ключ Яндекса), `mapColors` (цвета/режим точек),
`availableMode` (режим доступности: `surfaces`/`sides`), `dynCount` (показ «динамика (N)»),
`fontLoader` (ленивая загрузка шрифтов).

## Медиатеки сайта и конструкций

Это две **разные** подсистемы:

| | Медиа сайта | Медиа конструкций |
|---|---|---|
| Таблицы | `media`, `media_categories` | `construction_media` |
| Файлы | `storage/media/...` | `storage/constructions/imports/<key>/...` |
| Теги | разделы-теги (массив `category_id`) | статусы импорта, фото/карта |
| Админка | `AdministrationMediaPage` | медиатека в конструкциях |

### Разделы-теги медиа сайта

Список разделов заводят миграцией
`backend/migrations/migrate_media_categories_sections.py` (идемпотентно):
Разное, Новости, О компании, Сотрудники, Конструкции, Прочее, Офис,
География, Документы, Главная, Слайдеры, Пользователи, Информация,
Контакты, Медиа. Часть из них пока не используется загрузчиками — они
нужны для ручной простановки.

**Загрузчик каждой страницы проставляет свой раздел** (по умолчанию):

| Загрузчик | Раздел |
|---|---|
| Новости (`NewsMediaField`) | Новости |
| Слайды главной (`AdministrationHomePage`) | Слайдеры |
| Меню сайта, плитки дашборда | Прочее |
| Контакты (`AdministrationContactsPage`) | Офис / Сотрудники |

Раздел задаётся именем (`section` у `MediaSourceButtons`) и разрешается в
id через `composables/useMediaCategory.js` (`mediaCategoryId(name)`) —
существующий находится, отсутствующий создаётся.

В медиахранилище теги можно менять. **Тег раздела, где файл реально
используется, снять нельзя** (добавлять другие — можно): сервер проверяет
ссылки `news_media` (Новости), `home_geo_attraction_photos` (География) и
`page_block_media` (по slug страницы) — см. `used_sections_for` в
`backend/services/media_service.py`.

## Настройки с сервера и состояние

- `boot/settings.js` → `GET /api/settings`: `font_*`, `color_*`, `radius_*`, `map_engine`,
  `map_color_mode`, `map_color_free/busy/mixed`, `available_mode`, `show_dyn_count` →
  CSS-переменные и ref'ы конфигов. Дефолты — в `:root` (`src/css/app.scss`).
  Админка применяет изменения сразу после сохранения.
- **localStorage:** портфель (`albion_portfolio`), токен аккаунта (`albion_account_token`),
  согласие с cookie (`albion_cookie_consent`).
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
- Резервные копии `*.bak`/`*.save`/`*.before-*` не хранятся в репозитории
  (игнорируются `.gitignore`).
