# Конвейер импорта данных

Как выгрузка 1С (Excel) попадает в PostgreSQL вместе с медиа. Код —
`backend/importer/`, оркестратор `import_pipeline.py`, запуск/статус —
`backend/services/update_service.py`, эндпоинты — `backend/api/admin_base.py`.

## Общая схема

Оркестратор `import_pipeline.run` запускает стадии **отдельными подпроцессами**
(`run_stage`), каждая — самостоятельный CLI. 7 шагов (`STEP_MARKERS`):

| # | Шаг | Модуль |
|---|---|---|
| 1 | Excel → JSON | `constructions_excel_to_json` |
| 2 | JSON → SQLite staging | `staging` |
| 3 | Скачивание медиа (dry-run: проверка ссылок) | `construction_media_download` / `construction_media_check` |
| 4 | Превью large/card/thumb | `construction_media_preview` |
| 5 | SQLite → PostgreSQL | `staging_to_postgres` |
| 6 | Архивация старого импорта | `import_archive_service` |
| 7 | Очистка временных каталогов + retention | `import_pipeline` |

- `--commit` — реальный прогон (COMMIT + архивация); без него — **DRY-RUN**
  (файлы не качаются, PostgreSQL не меняется).
- `import_key` — имя каталога вида `YYYYMMDD-HHMMSS` (генерируется в staging).

## Стадии

**1. Excel → JSON** (`input/` → `tmp/constructions_import.json`).
В `input/` должен быть ровно один `.xls/.xlsx`. Читает формулы `=HYPERLINK(...)`
(`data_only=False`), поэтому ссылки фото/карты не теряются. Считает `surface_hash`
(SHA-256 по город/район/адрес/название/сторона/номер/тип/размер/координаты).

**2. JSON → SQLite staging** (`tmp/import/<key>/staging.sqlite`).
Таблицы: `cities`, `constructions`, `surfaces`, `surface_availability`, `import_log`.
Ключ конструкции = город + нормализованный адрес + номер; дубли `surface_hash`
отбрасываются с warning. Контрольные проверки количеств и координат.

**3. Медиа.** Строит `media_plan.json`: для каждого фото/карты решает `reuse`
(совпал `original_url` и все превью на диске) или `download`. Скачивает атомарно
(`.tmp` + replace) в `tmp/import/<key>/downloads/<type>/<hash>/…`, лог —
`logs/media_download.jsonl`, 12 потоков. Ссылки Яндекс.Диска резолвятся через
публичный download-API. В dry-run вместо скачивания — `HEAD`-проверка ссылок
(`construction_media_check`), но `media_plan.json` всё равно пишется.

**4. Превью.** Для `download` строит три варианта и кладёт в
`storage/constructions/imports/<key>/<photo|map>/<large|card|thumb>/<stem><ext>`
(размеры 2400 / 1000 / 400 px). Для `reuse` копирует старые превью в новую
директорию импорта. ZIP-выгрузка разбирается (берётся файл с «карта» в имени).

**5. SQLite → PostgreSQL.** Одной транзакцией: создаёт запись `construction_imports`
(`staging`), старую помечает `obsolete`, удаляет активные `constructions` (каскад),
загружает города/конструкции/поверхности (PostGIS `ST_GeomFromText(...,4326)`)/
доступность/медиа, новый импорт → `active`. Есть набор `validate_*` (staging,
surface_hash, availability, медиа-файлы, ≤1 active). Режим dry-run задаётся
`ALBION_IMPORT_DRY_RUN`; результат — `load_result.json`.

**6. Архивация** (`archive/constructions/<key>/`): `source.xlsx`,
`database.dump` (`pg_dump -Fc` только по таблицам конструкций и их sequence),
`media/` — копия медиа предыдущего импорта.

**7. Очистка + retention.** Удаляются временные каталоги; хранится не более
**5** архивов конструкций (`cleanup_old_archives(root, keep=5)`).

## Медиа и таблица `construction_media`

На шаге 5 в `construction_media` вставляются записи со `status=ok`
(`import_id`, `surface_id`, `surface_hash`, `media_type`, `url`, метаданные,
`large_path/card_path/thumb_path`). Медиа со `status=error` **пропускаются** и не
подменяются старыми. Уникальность — `(import_id, surface_hash, media_type)`.

## Архивы и восстановление (`import_archive_service`)

- Корни: `archive/constructions/` (данные XLS), `archive/_safety/` (страховочные копии).
- `restore_archive(import_key, dry_run)`: dry-run — только план (какие таблицы в
  дампе); реально — safety-дамп текущей БД, `DROP TABLE … CASCADE` только для таблиц
  конструкций, затем `pg_restore` дампа **целиком** (не `-t`, иначе теряются
  DEFAULT/PK/constraints), копирование медиа, контрольные счётчики.
- Идемпотентность: `archive_source` падает, если `source.xlsx` уже есть; медиа не
  перезаписывается.
- Ремонт схемы после неполных восстановлений —
  `backend/migrations/migrate_repair_constructions_schema.py` (возвращает
  DEFAULT/PK/UNIQUE/FK/CHECK/индексы; идемпотентен).

## Запуск и контроль (`update_service.py`)

- `start_update(dry_run)` — под in-process `Lock`: проверяет наличие файла в
  `input/`, пишет статус `running`, запускает подпроцесс `import_pipeline`, стартует
  поток-монитор. `stop_update` убивает группу процессов.
- Статусы: `running/success/error/stopped`; прогресс — по маркерам `STEP n:` в логе;
  при ошибке сохраняется первый traceback. Лог прогона архивируется в `tmp/update_logs/`.
- `save_uploaded_file` принимает только `.xls/.xlsx` (лимит 50 МБ), пересохраняет
  через LibreOffice и кладёт в `input/`.

## Админ-эндпоинты (`/api/admin/base`, под `require_admin`)

`GET /archives`, `GET /restore-info`, `POST /archives/{key}/restore` (query `dry_run`),
`POST /upload`, `POST /update` (query `dry_run`), `POST /update/stop`,
`GET /update/status`, `GET /update/log`, `GET /update/logs`, `GET /update/logs/{name}`.
Бекапы сайта: `GET /site-backups`, `POST /site-backups`, `POST /site-backups/{name}/restore`.

## Таблицы PostgreSQL

`cities`, `constructions` (geometry Point 4326), `surfaces` (side, surface_hash,
type, size, price, photo, map, location), `surface_availability` (по месяцам),
`construction_imports` (статусы active/staging/obsolete/failed), `construction_media`,
`media_import_registry`.

## Пути на диске

```
input/                                  ровно один Excel (+ input/.previous/)
tmp/constructions_import.json
tmp/import/<key>/{staging.sqlite, media_plan.json, downloads/, logs/, load_result.json}
storage/constructions/imports/<key>/<photo|map>/<large|card|thumb>/
archive/constructions/<key>/{source.xlsx, database.dump, media/}
archive/constructions/_previous/        archive/_safety/        archive/site/<key>/
```

## Грабли

- **Advisory-lock у импорта** (`update_service`, `_UPDATE_LOCK_ID`): запуск
  обновления берёт `pg_try_advisory_lock` на отдельном удерживаемом соединении,
  поэтому второй запуск из другого воркера получает «Обновление уже выполняется».
  (Ранее защита была только in-process, и при нескольких воркерах два обновления
  могли пойти одновременно.) Есть у авто-бекапа сайта и у импорта.
- **`media_import_registry`:** DDL в репозитории отсутствует (таблица используется
  в `CONSTRUCTIONS_TABLES` и repair-миграции, но нигде не создаётся) — при
  развёртывании «с нуля» её придётся создать отдельно.
- **Год кампании** берётся из `ALBION_IMPORT_YEAR`, иначе — текущий год
  (`import_year()` в `json_to_postgres.py`). Раньше был жёстко зашит `2026`
  в JSON и в строках `surface_availability`.
- **LibreOffice** нужен для конвертации сырых выгрузок 1С; при отсутствии бинарника
  файл сохраняется как есть.
- Формулы `=HYPERLINK`: Excel обязан читаться со `data_only=False`.
- Медиа с ошибкой скачивания **не блокируют** импорт и не подменяются старыми.
- Легаси/вспомогательные модули вне конвейера: `json_to_postgres.main`,
  `construction_media_downloader`, `construction_media_staging`,
  `constructions_validate`, `excel_to_json`, `news_import`.
