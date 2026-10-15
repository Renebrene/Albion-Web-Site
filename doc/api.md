<!-- СГЕНЕРИРОВАНО: scripts/gen_api_doc.py. Не редактировать вручную — правьте генератор. -->

# API — справочник эндпоинтов

Сгенерировано из OpenAPI (`/openapi.json`). Версия приложения: `1.0.0`. Путей: 110, операций: 140.

Регенерация: `.venv/bin/python scripts/gen_api_doc.py`.

## Аутентификация

- Публичные эндпоинты (`/api/settings`, `/api/home`, `/api/constructions`,
  `/api/contacts`, `/api/about`, `/api/news`, `/api/pages/...`) — без токена.
- Админские (`/api/admin/*`) — заголовок `Authorization: Bearer <admin-token>`
  (получается через `POST /api/admin/login`).
- Личный кабинет (`/api/account/*`) — `Authorization: Bearer <account-token>`
  (`POST /api/account/login`).
- Вход и восстановление ограничены rate-limit (in-memory, см. `backend/main.py`).

## account

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/account/chats` | Account Get Chats |
| PUT | `/api/account/chats` | Account Save Chats |
| DELETE | `/api/account/chats` | Account Clear Chats |
| POST | `/api/account/login` | Account Login |
| POST | `/api/account/logout` | Account Logout |
| GET | `/api/account/me` | Account Me |
| GET | `/api/account/portfolio` | Account Get Portfolio |
| PUT | `/api/account/portfolio` | Account Save Portfolio |
| DELETE | `/api/account/portfolio` | Account Clear Portfolio |
| POST | `/api/account/recover` | Account Recover |
| POST | `/api/account/register` | Account Register |
| GET | `/api/account/requests` | Account Requests |
| POST | `/api/account/requests` | Account Create Request |
| PUT | `/api/account/requisites` | Account Save Requisites |

## admin-about

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/about` | Admin Get About |
| PUT | `/api/admin/about` | Admin Update About |

## admin-audit

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/audit` | Admin List Audit |

## admin-base

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/base/archives` | Archives |
| POST | `/api/admin/base/archives` | Archive Create |
| POST | `/api/admin/base/archives/{import_key}/restore` | Restore |
| GET | `/api/admin/base/restore-info` | Restore Info |
| GET | `/api/admin/base/site-backups` | Site Backups |
| POST | `/api/admin/base/site-backups` | Site Backup Create |
| POST | `/api/admin/base/site-backups/{name}/restore` | Site Backup Restore |
| POST | `/api/admin/base/update` | Update |
| GET | `/api/admin/base/update/log` | Update Log |
| GET | `/api/admin/base/update/logs` | Update Logs |
| GET | `/api/admin/base/update/logs/{name}` | Update Log Named |
| GET | `/api/admin/base/update/status` | Update Status |
| POST | `/api/admin/base/update/stop` | Update Stop |
| POST | `/api/admin/base/upload` | Upload |

## admin-cabinet-users

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/cabinet-users` | Admin List Cabinet Users |

## admin-chat-log

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/chat-log` | Chat Log |
| GET | `/api/admin/chat-log/export` | Chat Log Export |
| POST | `/api/admin/chat-log/selection` | Chat Log Selection |

## admin-construction-media

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/admin/constructions/media/fields` | Set Fields Override |
| DELETE | `/api/admin/constructions/media/fields` | Clear Fields Override |
| POST | `/api/admin/constructions/media/override` | Set Media Override |
| DELETE | `/api/admin/constructions/media/override` | Clear Media Override |
| GET | `/api/admin/constructions/media/overrides` | List Media Overrides |

## admin-contacts

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/contacts` | Admin Get Contacts |
| POST | `/api/admin/contacts/departments` | Admin Create Department |
| PUT | `/api/admin/contacts/departments/{department_id}` | Admin Update Department |
| DELETE | `/api/admin/contacts/departments/{department_id}` | Admin Delete Department |
| POST | `/api/admin/contacts/employees` | Admin Create Employee |
| PUT | `/api/admin/contacts/employees/{employee_id}` | Admin Update Employee |
| DELETE | `/api/admin/contacts/employees/{employee_id}` | Admin Delete Employee |
| POST | `/api/admin/contacts/offices` | Admin Create Office |
| PUT | `/api/admin/contacts/offices/{office_id}` | Admin Update Office |
| DELETE | `/api/admin/contacts/offices/{office_id}` | Admin Delete Office |
| PUT | `/api/admin/contacts/reorder` | Admin Reorder |
| PUT | `/api/admin/contacts/settings` | Admin Update Settings |

## admin-dashboard

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/dashboard` | Admin Get Dashboard Layout |
| PUT | `/api/admin/dashboard` | Admin Save Dashboard Layout |

## admin-home

| Метод | Путь | Описание |
|---|---|---|
| PATCH | `/api/admin/home/buttons/{button_id}` | Button Update |
| DELETE | `/api/admin/home/buttons/{button_id}` | Button Delete |
| GET | `/api/admin/home/feedback` | Feedback List |
| DELETE | `/api/admin/home/feedback/{feedback_id}` | Feedback Delete |
| GET | `/api/admin/home/geo` | Geo Content |
| POST | `/api/admin/home/geo/attractions` | Geo Attraction Create |
| PATCH | `/api/admin/home/geo/attractions/{attraction_id}` | Geo Attraction Update |
| DELETE | `/api/admin/home/geo/attractions/{attraction_id}` | Geo Attraction Delete |
| POST | `/api/admin/home/geo/attractions/{attraction_id}/photos` | Geo Photo Create |
| POST | `/api/admin/home/geo/locations` | Geo Location Create |
| PATCH | `/api/admin/home/geo/locations/{location_id}` | Geo Location Update |
| DELETE | `/api/admin/home/geo/locations/{location_id}` | Geo Location Delete |
| DELETE | `/api/admin/home/geo/photos/{photo_id}` | Geo Photo Delete |
| PATCH | `/api/admin/home/geo/settings` | Geo Settings |
| PATCH | `/api/admin/home/items/{item_id}` | Item Update |
| DELETE | `/api/admin/home/items/{item_id}` | Item Delete |
| POST | `/api/admin/home/items/{item_id}/buttons` | Item Button Create |
| GET | `/api/admin/home/slides` | Slides |
| POST | `/api/admin/home/slides` | Slide Create |
| PATCH | `/api/admin/home/slides/{slide_id}` | Slide Update |
| DELETE | `/api/admin/home/slides/{slide_id}` | Slide Delete |
| POST | `/api/admin/home/slides/{slide_id}/buttons` | Slide Button Create |
| POST | `/api/admin/home/slides/{slide_id}/items` | Item Create |

## admin-info

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/info/tabs` | Admin Get Tabs |
| PUT | `/api/admin/info/tabs` | Admin Save Tabs |

## admin-news

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/news` | Admin Get News |
| POST | `/api/admin/news` | Admin Create News |
| POST | `/api/admin/news/categories` | Admin Create Category |
| PUT | `/api/admin/news/{news_id}` | Admin Update News |
| DELETE | `/api/admin/news/{news_id}` | Admin Delete News |

## admin-requests

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/requests` | Admin List Requests |

## admin-seo

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/seo` | Admin Get Seo |
| PUT | `/api/admin/seo` | Admin Save Seo |
| POST | `/api/admin/seo/reset` | Admin Reset Seo |

## admin-settings

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/settings` | Admin Get Settings |
| PUT | `/api/admin/settings` | Admin Save Settings |
| POST | `/api/admin/settings/presets` | Admin Create Preset |
| DELETE | `/api/admin/settings/presets/{preset_id}` | Admin Delete Preset |
| POST | `/api/admin/settings/presets/{preset_id}/apply` | Admin Apply Preset |
| POST | `/api/admin/settings/reset` | Admin Reset Settings |

## admin-site

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/site/menu` | Admin Get Menu |
| PUT | `/api/admin/site/menu` | Admin Update Menu |

## admin-statistics

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/statistics/countries` | Admin Statistics Countries |
| GET | `/api/admin/statistics/daily` | Admin Statistics Daily |
| GET | `/api/admin/statistics/pages` | Admin Statistics Pages |
| GET | `/api/admin/statistics/summary` | Admin Statistics Summary |
| GET | `/api/admin/statistics/visits` | Admin Statistics Visits |

## admin-users

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/admin/users` | Admin List Users |
| POST | `/api/admin/users` | Admin Create User |
| PATCH | `/api/admin/users/{user_id}` | Admin Update User |
| POST | `/api/admin/users/{user_id}/password` | Admin Change Password |

## chat

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/chat` | Create Chat |
| POST | `/api/chat/message` | Send Message |
| POST | `/api/chat/reset` | Reset Chat |
| POST | `/api/chat/{session_id}/message` | Send Session Message |

## info

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/info` | Public Info |

## portfolio

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/portfolio/export` | Export Portfolio |

## requests

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/requests` | Create Public Request |

## seo

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/seo` | Public Get Seo |
| GET | `/robots.txt` | Robots |
| GET | `/sitemap.xml` | Sitemap |

## settings

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/settings` | Public Get Settings |

## tracking

| Метод | Путь | Описание |
|---|---|---|
| POST | `/api/track` | Track Visit |

## Прочее (без тега)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/about` | About |
| GET | `/api/admin/constructions/stats` | Admin Constructions Stats |
| POST | `/api/admin/login` | Admin Login |
| POST | `/api/admin/logout` | Admin Logout |
| GET | `/api/admin/me` | Admin Me |
| GET | `/api/admin/media` | Admin List Media |
| POST | `/api/admin/media` | Admin Upload Media |
| GET | `/api/admin/media/categories` | Admin List Media Categories |
| POST | `/api/admin/media/categories` | Admin Create Media Category |
| GET | `/api/admin/media/stats` | Admin Media Stats |
| PATCH | `/api/admin/media/{media_id}` | Admin Update Media |
| DELETE | `/api/admin/media/{media_id}` | Admin Delete Media |
| GET | `/api/constructions` | Constructions |
| GET | `/api/constructions/stats` | Constructions Stats |
| GET | `/api/contacts` | Contacts |
| POST | `/api/feedback` | Feedback Submit |
| GET | `/api/health` | Health |
| GET | `/api/home` | Home Content |
| GET | `/api/news` | News |
| GET | `/api/news/{slug}` | News Item |
| GET | `/api/pages/{slug}` | Page |
| POST | `/api/search` | Search |
| GET | `/api/site-menu` | Site Menu |
