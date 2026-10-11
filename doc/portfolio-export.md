# Портфель и экспорт

Как формируется «портфель» и как он выгружается в файл. Код: `frontend/src/composables/usePortfolio.js`,
`frontend/src/components/portfolio/PortfolioPanel.vue`, `frontend/src/services/portfolioExport.js`,
`backend/api/portfolio.py`, `backend/services/portfolio_export.py`.

## Портфель

- **Что это** — «корзина» выбранных **поверхностей** с месяцами (см. `doc/glossary.md`).
- **Синглтон** — состояние это модульные `ref` в `usePortfolio.js`, общие для всего
  приложения (шапка, карточка, страница портфеля видят один список).
- **Позиция** — `surfaceId` + `months: { [monthFull]: { price, addedAt, stale } }`,
  снимки по всем месяцам (`prices`, `statuses`, `monthTexts`) и «паспортные» поля
  (`address, city, side, type, size, photo*, map*`).
- **Хранилище:** `localStorage['albion_portfolio']` (`{ version, title, items }`);
  при авторизации — синхронизация с ЛК (`GET/PUT/DELETE /api/account/portfolio`,
  таблица `account_portfolios`).
- **Автосохранение:** `watch(items, title, deep)` пишет в localStorage всегда; на
  сервер — только когда пользователь авторизован, с дебаунсом 1 с.
- **Синхронизация с каталогом** (`syncWithConstructions`) обновляет паспортные поля
  и помечает месяц `stale`, если он больше не свободен.
- Позиция **не удаляется** при снятии последнего месяца (остаётся «ничего не
  выбрано»); удаляют `clear()` и `removeSurface()`.

## Эндпоинт экспорта

`POST /api/portfolio/export?format=<fmt>` — **без авторизации** (данных в теле достаточно).

- **Query:** `format` (по умолчанию `xlsx`), `with_photos`, `with_maps`, `full_output`
  (строки; `"1"/"true"/"yes"/"on"/"да"`).
- **Тело:** `{ title, items, with_photos?, with_maps?, full_output?, requisites? }`.
  Приоритет у тела; query используется, если поле в теле не задано.
- **Ответ:** байты файла, `Content-Type` по формату,
  `Content-Disposition: attachment; filename="albion-portfolio-YYYYMMDD.<ext>"`.
- **Ошибки:** `400` — неподдерживаемый формат / пустой портфель / >500 позиций;
  `500` — нет кириллического шрифта для PDF (reportlab) либо прочий сбой сборки.

## Форматы

| Формат | Как собирается |
|---|---|
| `xlsx` | канонический XLSX (openpyxl) |
| `xls`, `ods` | LibreOffice из XLSX |
| `docx` | канонический DOCX (python-docx) |
| `doc`, `odt`, `rtf`, `pdf` | LibreOffice из DOCX (поэтому pdf/doc/odt/rtf идентичны) |
| `csv`, `txt`, `md`, `json` | только текст, без фото/карт |

- **«Только текст»** (`TEXT_FORMATS`) игнорируют «полный/краткий вывод» и не содержат
  фото/карт. CSV — разделитель `;`, `utf-8-sig` (BOM для Excel).
- **PDF-fallback:** если LibreOffice недоступен, `pdf` собирается через reportlab
  (при наличии шрифта). У `doc/odt/rtf/xls/ods` фолбэка нет — будет `400`.
- **Лимиты:** `MAX_ITEMS = 500`; поля реквизитов обрезаются до 300 символов.
- **Фото только с сервера:** `resolve_photo_path` принимает лишь пути `/storage/…`,
  реальный путь обязан лежать внутри `storage/`, файл ≤ 15 МБ; иначе ячейка пустая.

## Требования окружения

- **LibreOffice** (`soffice`/`libreoffice`) — для doc/odt/rtf/xls/ods/pdf;
  конвертация идёт в отдельном временном профиле, таймаут 120 с.
- **Шрифты** (для PDF/reportlab) — в порядке предпочтения: `DejaVuSans`,
  `LiberationSans`, `FreeSans`, `NotoSans`; иначе `FontUnavailableError` → `500`.
  Пакеты: `fonts-dejavu`, `fonts-liberation`.
- Библиотеки: `python-docx`, `openpyxl`, `reportlab`, `Pillow`, `pillow-heif`.

## Фронтенд

- **«Вывод»** — выпадающий список из 12 форматов → скачивание blob.
- **«Действия»** — «Принтер» (печать), «Почта» (`mailto:`), «Чат» (заглушка: копирует
  текст, при наличии `window.jivo_api` открывает виджет).
- **«Краткий/Полный вывод»** — один чекбокс: полный режим включает и фото, и карты.
  Отдельных галочек «Фото»/«Карта» в UI нет.
- **Печать** открывает окно синхронно, затем грузит PDF и печатает; при блокировке —
  HTML-фолбэк.
- **Сохранение в ЛК** доступно только авторизованным (иначе тултип «Войдите в личный
  кабинет» и переход на `/account`). Экспорт/печать/почта/чат авторизации не требуют.
- **Очистить** — с подтверждением.

## Грабли и детали

- **Имя файла расходится:** сервер формирует `albion-portfolio-YYYYMMDD.<ext>`, но
  фронт сохраняет как `albion-portfolio.<ext>` (без даты), игнорируя
  `Content-Disposition`.
- **LibreOffice-фолбэк — только для PDF.** Отсутствие `soffice` ломает
  doc/odt/rtf/xls/ods (отдаётся `400`, не `500`).
- **Фото в письме:** `emailPortfolio` передаёт `withMaps`, но не `withPhotos` —
  поведение стоит проверять при изменениях.
- Устаревшие комментарии в `portfolio_export.py` (бокс/ширина картинки) расходятся с
  константами — ориентироваться на константы (`FULL_IMAGE_BOX`, `FULL_IMAGE_WIDTH_CM`).
