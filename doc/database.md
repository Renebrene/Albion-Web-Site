<!-- СГЕНЕРИРОВАНО: scripts/gen_db_doc.py. Не редактировать вручную — правьте генератор. -->

# База данных — схема

## Назначение и особенности

- СУБД: **PostgreSQL 16 + PostGIS** (расширения `postgis`, `pgcrypto`).
- Доступ из кода: `backend/services/data_service.py` → `get_connection()`.
  Контекстный менеджер psycopg3 **коммитит при выходе без исключения** —
  отдельный `commit()` обычно не нужен.
- Схема меняется **идемпотентными миграциями** в `backend/migrations/`
  (запускаются отдельно, не в каждом worker'е).
- Медиа/архивы хранятся на диске (`storage/`, `archive/`), в БД — метаданные.

Регенерация: `.venv/bin/python scripts/gen_db_doc.py`.

> Всего таблиц: 55, представлений: 2. 
> 🔑 — колонка первичного ключа.

## Расширения

- `pgcrypto` 1.3
- `plpgsql` 1.0
- `postgis` 3.4.2

## Таблицы

### about_activity_items

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('about_activity_items_id_seq'::regclass)` |
| page_id | bigint | нет |  |
| title | text | нет |  |
| body | text | да |  |
| icon | text | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### about_network_items

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('about_network_items_id_seq'::regclass)` |
| page_id | bigint | нет |  |
| item_type | text | нет |  |
| title | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### about_production_items

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('about_production_items_id_seq'::regclass)` |
| page_id | bigint | нет |  |
| title | text | нет |  |
| body | text | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### account_chats

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('account_chats_id_seq'::regclass)` |
| account_id | bigint | нет |  |
| payload | jsonb | нет | `'{}'::jsonb` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### account_portfolios

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('account_portfolios_id_seq'::regclass)` |
| account_id | bigint | нет |  |
| payload | jsonb | нет | `'{}'::jsonb` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### account_sessions

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('account_sessions_id_seq'::regclass)` |
| account_id | bigint | нет |  |
| token_hash | text | нет |  |
| created_at | timestamp with time zone | нет | `now()` |
| expires_at | timestamp with time zone | нет |  |

### admin_audit_log

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('admin_audit_log_id_seq'::regclass)` |
| user_id | bigint | да |  |
| action | text | нет |  |
| entity_type | text | да |  |
| entity_id | bigint | да |  |
| details | text | да |  |
| ip_address | inet | да |  |
| created_at | timestamp with time zone | нет | `now()` |

### admin_sessions

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('admin_sessions_id_seq'::regclass)` |
| user_id | bigint | нет |  |
| token_hash | text | нет |  |
| expires_at | timestamp with time zone | нет |  |
| created_at | timestamp with time zone | нет | `now()` |
| revoked_at | timestamp with time zone | да |  |
| ip_address | inet | да |  |
| user_agent | text | да |  |

### admin_users

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('admin_users_id_seq'::regclass)` |
| login | text | нет |  |
| password_hash | text | нет |  |
| name | text | нет |  |
| role | text | нет | `'admin'::text` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| last_login_at | timestamp with time zone | да |  |

### chat_requests

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 session_id | uuid | нет |  |
| 🔑 request_id | uuid | нет |  |
| response | jsonb | нет |  |
| created_at | timestamp with time zone | нет | `now()` |

### chat_sessions

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | uuid | нет |  |
| pending_query | jsonb | да |  |
| last_result_ids | jsonb | нет | `'[]'::jsonb` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| expires_at | timestamp with time zone | нет |  |

### chat_turns

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('chat_turns_id_seq'::regclass)` |
| session_id | uuid | да |  |
| chat_key | text | да |  |
| question | text | нет |  |
| answer | text | да |  |
| created_at | timestamp with time zone | нет | `now()` |
| selected | boolean | нет | `false` |

### cities

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('cities_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| name | text | нет |  |
| normalized_name | text | нет |  |
| slug | text | да |  |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### client_requests

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('client_requests_id_seq'::regclass)` |
| account_id | bigint | нет |  |
| title | text | нет | `''::text` |
| surface_id | bigint | да |  |
| payload | jsonb | нет | `'{}'::jsonb` |
| status | text | нет | `'new'::text` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### construction_imports

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('construction_imports_id_seq'::regclass)` |
| import_key | text | нет |  |
| status | text | нет |  |
| created_at | timestamp with time zone | нет | `now()` |
| finished_at | timestamp with time zone | да |  |

### construction_media

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('construction_media_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| surface_id | bigint | да |  |
| media_type | text | нет |  |
| original_url | text | да |  |
| original_name | text | да |  |
| mime_type | text | да |  |
| file_size | bigint | да |  |
| width | integer | да |  |
| height | integer | да |  |
| large_path | text | да |  |
| card_path | text | да |  |
| thumb_path | text | да |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| surface_hash | text | да |  |
| import_id | bigint | да |  |

### constructions

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('constructions_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| city_id | bigint | да |  |
| district | text | да |  |
| address | text | нет |  |
| name | text | да |  |
| location | USER-DEFINED | да |  |
| latitude | double precision | да |  |
| longitude | double precision | да |  |
| address_words | text | да |  |
| address_roots | text | да |  |
| address_numbers | text | да |  |
| street_root | text | да |  |
| house_number | text | да |  |
| address_key | text | да |  |
| street_names | text | да |  |
| street_roots | text | да |  |
| house_numbers | text | да |  |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_callback

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | integer | нет | `1` |
| title | text | нет |  |
| body | text | да |  |
| is_enabled | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_callback_fields

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_callback_fields_id_seq'::regclass)` |
| callback_id | integer | нет |  |
| field_name | text | нет |  |
| label | text | нет |  |
| field_type | text | нет |  |
| is_required | boolean | нет | `false` |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_callback_recipients

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_callback_recipients_id_seq'::regclass)` |
| callback_id | integer | нет |  |
| email | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |

### contact_departments

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_departments_id_seq'::regclass)` |
| external_key | text | да |  |
| name | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_emails

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_emails_id_seq'::regclass)` |
| email | text | нет |  |
| label | text | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |

### contact_employees

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_employees_id_seq'::regclass)` |
| external_key | text | да |  |
| department_id | bigint | нет |  |
| name | text | нет |  |
| position | text | да |  |
| phone | text | да |  |
| extension | text | да |  |
| email | text | да |  |
| media_id | bigint | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| subdivision | text | да |  |
| personal_phone | text | да |  |

### contact_office_emails

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_office_emails_id_seq'::regclass)` |
| office_id | bigint | нет |  |
| email | text | нет |  |
| sort_order | integer | нет | `0` |
| created_at | timestamp with time zone | нет | `now()` |

### contact_offices

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_offices_id_seq'::regclass)` |
| external_key | text | да |  |
| name | text | нет |  |
| address | text | нет |  |
| phone | text | да |  |
| email | text | да |  |
| schedule | text | да |  |
| latitude | double precision | да |  |
| longitude | double precision | да |  |
| media_id | bigint | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_settings

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | integer | нет | `1` |
| seo_title | text | да |  |
| seo_description | text | да |  |
| hero_eyebrow | text | да |  |
| hero_title | text | да |  |
| hero_text | text | да |  |
| phone | text | да |  |
| email | text | да |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### contact_socials

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('contact_socials_id_seq'::regclass)` |
| name | text | нет |  |
| url | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### home_geo_attraction_photos

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_geo_attraction_photos_id_seq'::regclass)` |
| attraction_id | bigint | нет |  |
| media_id | bigint | да |  |
| image_path | text | нет | `''::text` |
| alt_text | text | нет | `''::text` |
| source_name | text | нет | `''::text` |
| source_url | text | нет | `''::text` |
| license | text | нет | `''::text` |
| sort_order | integer | нет | `0` |
| is_cover | boolean | нет | `false` |
| created_at | timestamp with time zone | нет | `now()` |

### home_geo_attractions

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_geo_attractions_id_seq'::regclass)` |
| location_id | bigint | да |  |
| title | text | нет |  |
| description | text | нет | `''::text` |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### home_geo_locations

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_geo_locations_id_seq'::regclass)` |
| kind | text | нет |  |
| label | text | нет |  |
| map_value | text | нет | `''::text` |
| parent_city | text | нет | `''::text` |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| description | text | нет | `''::text` |
| cover_attraction_id | bigint | да |  |

### home_geo_settings

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | smallint | нет | `1` |
| is_active | boolean | нет | `true` |
| map_links_enabled | boolean | нет | `true` |
| updated_at | timestamp with time zone | нет | `now()` |
| deck_wheel_mode | text | нет | `'off'::text` |

### home_slide_buttons

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_slide_buttons_id_seq'::regclass)` |
| slide_id | bigint | нет |  |
| item_id | bigint | да |  |
| sort_order | integer | нет | `0` |
| label | text | нет | `''::text` |
| url | text | нет | `''::text` |
| variant | text | нет | `'primary'::text` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### home_slide_items

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_slide_items_id_seq'::regclass)` |
| slide_id | bigint | нет |  |
| sort_order | integer | нет | `0` |
| title | text | нет | `''::text` |
| text | text | нет | `''::text` |
| button_label | text | нет | `''::text` |
| button_url | text | нет | `''::text` |
| image_path | text | нет | `''::text` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| eyebrow | text | нет | `''::text` |
| slogan | text | нет | `''::text` |
| button2_label | text | нет | `''::text` |
| button2_url | text | нет | `''::text` |
| extra | text | нет | `''::text` |

### home_slides

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('home_slides_id_seq'::regclass)` |
| sort_order | integer | нет | `0` |
| is_hero | boolean | нет | `false` |
| title | text | нет | `''::text` |
| text | text | нет | `''::text` |
| button_label | text | нет | `''::text` |
| button_url | text | нет | `''::text` |
| image_path | text | нет | `''::text` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| kind | text | нет | `'text'::text` |

### info_tabs

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('info_tabs_id_seq'::regclass)` |
| title | text | нет | `''::text` |
| kind | text | нет | `'text'::text` |
| content | text | нет | `''::text` |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### media

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('media_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| original_name | text | нет |  |
| storage_path | text | нет |  |
| mime_type | text | нет |  |
| file_size | bigint | нет |  |
| width | integer | да |  |
| height | integer | да |  |
| alt | text | да |  |
| title | text | да |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| category_id | ARRAY | да |  |
| preview_path | text | да |  |

### media_categories

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('media_categories_id_seq'::regclass)` |
| name | text | нет |  |
| sort_order | integer | нет | `0` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### media_import_registry

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('media_import_registry_id_seq'::regclass)` |
| filename | text | нет |  |
| row_hash | text | нет |  |
| media_type | text | нет |  |
| original_link | text | да |  |
| address | text | да |  |
| side | text | да |  |
| status | text | нет |  |
| file_size | bigint | да |  |
| downloaded_at | timestamp with time zone | да |  |
| created_at | timestamp with time zone | нет | `now()` |

### media_variants

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('media_variants_id_seq'::regclass)` |
| media_id | bigint | нет |  |
| variant | text | нет |  |
| storage_path | text | нет |  |
| mime_type | text | нет |  |
| file_size | bigint | нет |  |
| width | integer | нет |  |
| height | integer | нет |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### news

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('news_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| slug | text | нет |  |
| title | text | нет |  |
| excerpt | text | да |  |
| content | text | нет |  |
| category_id | bigint | да |  |
| published_at | timestamp with time zone | да |  |
| is_published | boolean | нет | `false` |
| seo_title | text | да |  |
| seo_description | text | да |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| is_featured | boolean | нет | `false` |

### news_categories

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('news_categories_id_seq'::regclass)` |
| name | text | нет |  |
| slug | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### news_media

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('news_media_id_seq'::regclass)` |
| news_id | bigint | нет |  |
| media_id | bigint | нет |  |
| sort_order | integer | нет | `0` |
| is_cover | boolean | нет | `false` |
| created_at | timestamp with time zone | нет | `now()` |

### page_block_media

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('page_block_media_id_seq'::regclass)` |
| block_id | bigint | нет |  |
| media_id | bigint | нет |  |
| role | text | нет | `'image'::text` |
| sort_order | integer | нет | `0` |
| is_cover | boolean | нет | `false` |
| created_at | timestamp with time zone | нет | `now()` |

### page_blocks

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('page_blocks_id_seq'::regclass)` |
| page_id | bigint | нет |  |
| block_key | text | нет |  |
| block_type | text | нет |  |
| eyebrow | text | да |  |
| title | text | да |  |
| subtitle | text | да |  |
| body | text | да |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| content | jsonb | нет | `'{}'::jsonb` |

### page_stats

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('page_stats_id_seq'::regclass)` |
| page_id | bigint | нет |  |
| value | text | нет |  |
| label | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### page_visits

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('page_visits_id_seq'::regclass)` |
| created_at | timestamp with time zone | нет | `now()` |
| path | text | нет |  |
| referrer | text | да |  |
| country_code | text | да |  |
| country_name | text | да |  |
| is_bot | boolean | нет | `false` |
| device | text | да |  |
| browser | text | да |  |
| visitor_hash | text | нет |  |

### pages

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('pages_id_seq'::regclass)` |
| slug | text | нет |  |
| title | text | нет |  |
| seo_title | text | да |  |
| seo_description | text | да |  |
| is_published | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| page_type | text | нет | `'system'::text` |
| menu_title | text | да |  |
| show_in_menu | boolean | нет | `true` |
| menu_order | integer | нет | `0` |
| parent_id | bigint | да |  |
| template | text | нет | `'standard'::text` |

### settings_presets

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('settings_presets_id_seq'::regclass)` |
| name | text | нет |  |
| payload | jsonb | нет |  |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### site_feedback

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('site_feedback_id_seq'::regclass)` |
| name | text | нет | `''::text` |
| phone | text | нет | `''::text` |
| message | text | нет | `''::text` |
| created_at | timestamp with time zone | нет | `now()` |

### site_menu_items

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('site_menu_items_id_seq'::regclass)` |
| section | text | нет |  |
| key | text | нет |  |
| label | text | нет |  |
| url | text | нет |  |
| sort_order | integer | нет | `0` |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### site_settings

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('site_settings_id_seq'::regclass)` |
| key | text | нет |  |
| value | text | да |  |
| value_type | text | нет | `'text'::text` |
| description | text | да |  |
| updated_at | timestamp with time zone | нет | `now()` |

### spatial_ref_sys

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 srid | integer | нет |  |
| auth_name | character varying | да |  |
| auth_srid | integer | да |  |
| srtext | character varying | да |  |
| proj4text | character varying | да |  |

### surface_availability

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('surface_availability_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| surface_id | bigint | нет |  |
| year | integer | нет |  |
| month | integer | нет |  |
| raw_value | text | да |  |
| status | text | нет | `'FREE'::text` |
| load_percent | integer | да |  |
| price | text | да |  |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |

### surfaces

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('surfaces_id_seq'::regclass)` |
| uuid | uuid | нет | `gen_random_uuid()` |
| construction_id | bigint | нет |  |
| side | text | нет |  |
| name | text | да |  |
| external_number | text | да |  |
| temporary_identifier | text | да |  |
| type | text | да |  |
| size | text | да |  |
| price | text | да |  |
| photo | text | да |  |
| map | text | да |  |
| location | USER-DEFINED | да |  |
| latitude | double precision | да |  |
| longitude | double precision | да |  |
| light | text | да |  |
| material | text | да |  |
| media_type | text | да |  |
| legacy_surface_id | bigint | да |  |
| source_system | text | да |  |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| surface_hash | text | да |  |

### user_accounts

| Колонка | Тип | NULL | По умолчанию |
|---|---|---|---|
| 🔑 id | bigint | нет | `nextval('user_accounts_id_seq'::regclass)` |
| login | text | нет |  |
| password_hash | text | нет |  |
| role | text | нет | `'client'::text` |
| secret_phrase_hash | text | нет |  |
| is_active | boolean | нет | `true` |
| created_at | timestamp with time zone | нет | `now()` |
| updated_at | timestamp with time zone | нет | `now()` |
| requisites | jsonb | нет | `'{}'::jsonb` |

## Внешние ключи

- `about_activity_items.page_id` → `pages.id`
- `about_network_items.page_id` → `pages.id`
- `about_production_items.page_id` → `pages.id`
- `account_chats.account_id` → `user_accounts.id`
- `account_portfolios.account_id` → `user_accounts.id`
- `account_sessions.account_id` → `user_accounts.id`
- `admin_audit_log.user_id` → `admin_users.id`
- `admin_sessions.user_id` → `admin_users.id`
- `chat_requests.session_id` → `chat_sessions.id`
- `client_requests.account_id` → `user_accounts.id`
- `construction_media.import_id` → `construction_imports.id`
- `construction_media.surface_id` → `surfaces.id`
- `constructions.city_id` → `cities.id`
- `contact_callback_fields.callback_id` → `contact_callback.id`
- `contact_callback_recipients.callback_id` → `contact_callback.id`
- `contact_employees.department_id` → `contact_departments.id`
- `contact_employees.media_id` → `media.id`
- `contact_office_emails.office_id` → `contact_offices.id`
- `contact_offices.media_id` → `media.id`
- `home_geo_attraction_photos.attraction_id` → `home_geo_attractions.id`
- `home_geo_attraction_photos.media_id` → `media.id`
- `home_geo_attractions.location_id` → `home_geo_locations.id`
- `home_geo_locations.cover_attraction_id` → `home_geo_attractions.id`
- `home_slide_buttons.item_id` → `home_slide_items.id`
- `home_slide_buttons.slide_id` → `home_slides.id`
- `home_slide_items.slide_id` → `home_slides.id`
- `media_variants.media_id` → `media.id`
- `news.category_id` → `news_categories.id`
- `news_media.media_id` → `media.id`
- `news_media.news_id` → `news.id`
- `page_block_media.block_id` → `page_blocks.id`
- `page_block_media.media_id` → `media.id`
- `page_blocks.page_id` → `pages.id`
- `page_stats.page_id` → `pages.id`
- `pages.parent_id` → `pages.id`
- `surface_availability.surface_id` → `surfaces.id`
- `surfaces.construction_id` → `constructions.id`

## Представления

- `geography_columns`
- `geometry_columns`
