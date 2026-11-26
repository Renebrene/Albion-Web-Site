# Roadrunner API — Справочник для AI-агентов

## Обзор

Roadrunner — модуль программной дороги для 3D-баннера «Светофорные объекты» на главной странице Альбион.

## Структура

```
backend/roadrunner/
├── api/
│   ├── schema.json          # JSON Schema для сценариев
│   ├── events.json          # Словарь событий (22 действия)
│   ├── scenarios/           # Готовые сценарии (JSON)
│   │   └── rostov-evening-rain.json
│   ├── API.md               # Этот документ
│   └── roadrunner-api.html  # HTML-документация (PDF рендерится из неё)
├── config/                  # Конфигурация (city, weather, traffic, holidays, provider)
├── scenario/
│   └── engine.py            # Движок сценариев
├── services/
│   ├── weather.py           # Погода (Open-Meteo/Яндекс) и пробки (Яндекс/модель)
│   └── llm_agent.py         # AI-агент и SYSTEM_PROMPT для генерации
└── tools/generate_pdf.py    # Локальная сборка PDF (weasyprint/wkhtmltopdf/Chrome)

backend/api/roadrunner.py    # FastAPI роутер /api/roadrunner/*
backend/templates/road_banner.html  # Исходный HTML 3D-баннера
```

Актуальный баннер хранится в БД (`home_slides.code`, слайд `kind='road-banner'`),
а не в `scene/` или `ui/`. Настройки и сценарии — в таблицах
`roadrunner_settings` (ключ `roadrunner`) и `roadrunner_scenarios`.

## API Endpoints

### Публичные (без авторизации)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/roadrunner/weather` | Текущая погода (Open-Meteo → Яндекс → модель) |
| GET | `/api/roadrunner/weather-proxy` | Погода для баннера (Open-Meteo-совместимый формат, CORS `*`) |
| GET | `/api/roadrunner/traffic` | Текущие пробки (Яндекс → модель, CORS `*`) |
| GET | `/api/roadrunner/api-documentation.html` | HTML-документация |
| GET | `/api/roadrunner/api-documentation.pdf` | PDF-документация |

### Админские (требуют `require_admin`)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/roadrunner/scenarios` | Список всех сценариев |
| GET | `/api/roadrunner/scenarios/ready` | Готовые сценарии: чат + файловые пресеты + сохранённые в БД |
| GET | `/api/roadrunner/scenarios/{id_or_slug}` | Сценарий: числовой id — из БД, строка — файловый slug |
| POST | `/api/roadrunner/scenarios` | Создать сценарий (в ответе `db_id`) |
| DELETE | `/api/roadrunner/scenarios/{id_or_slug}` | Удалить сценарий **только из БД** (файловые — через репозиторий) |
| POST | `/api/roadrunner/generate` | Сгенерировать сценарий через LLM |
| POST | `/api/roadrunner/upload-scenario` | Загрузить сценарий из файла |
| GET | `/api/roadrunner/settings` | Настройки Roadrunner |
| PUT | `/api/roadrunner/settings` | Обновить настройки |
| GET | `/api/roadrunner/camera-presets` | Пресеты камеры и сцены |
| POST | `/api/roadrunner/camera-presets` | Сохранить пресет камеры |
| DELETE | `/api/roadrunner/camera-presets/{name}` | Удалить пресет камеры |
| GET | `/api/roadrunner/scene-presets` | Пресеты сцены и снимок «Дефолт» |
| POST | `/api/roadrunner/scene-presets/default` | Сохранить текущее состояние как «Дефолт» |
| POST | `/api/roadrunner/scene-presets` | Сохранить пресет сцены |
| DELETE | `/api/roadrunner/scene-presets/{name}` | Удалить пресет сцены |
| GET | `/api/roadrunner/code-default` | Код-основа «Дефолт» для AI-редактора |
| POST | `/api/roadrunner/code-default` | Сохранить код как «Дефолт» |
| POST | `/api/roadrunner/code-default/from-banner` | Сохранить текущий код баннера как «Дефолт» |
| POST | `/api/roadrunner/edit-code` | Изменить HTML-код баннера нейросетью |
| POST | `/api/roadrunner/apply-code` | Применить код к баннеру (`home_slides.code`) |
| POST | `/api/roadrunner/code-default/restore` | Восстановить баннер из «Дефолта» |
| GET | `/api/roadrunner/code-presets` | Именованные версии кода |
| POST | `/api/roadrunner/code-presets` | Сохранить новую версию кода под названием |
| DELETE | `/api/roadrunner/code-presets/{name}` | Удалить версию кода |

Генератор сценариев и AI-редактор кода используют одну и ту же модель из
настроек АИ: `llm_provider`, `llm_model`, `llm_url`, `llm_api_key`. Отдельных
«сценовых» настроек нет. Лимит `max_tokens` (512–8192; для Ollama до 4096)
применяется к обоим.

## JSON Schema для сценариев

```json
{
  "id": "string (uuid-like, lowercase)",
  "name": "string (1-100 chars)",
  "description": "string (0-500 chars)",
  "duration": "integer (30-3600 секунд)",
  "version": "string (default: '1.0')",
  "created_at": "ISO-8601 datetime",
  "author": "string (1-100 chars)",
  "tags": ["string"],
  "events": [
    {
      "t": "number (>= 0, секунды от начала)",
      "do": "string (event name)",
      "params": "object"
    }
  ]
}
```

## Словарь событий (`api/events.json`)

| Событие | Параметры | Описание |
|---|---|---|
| `start_traffic` | — | Начать движение транспорта |
| `stop_traffic` | — | Остановить движение |
| `change_traffic_density` | `density: 0.1-3.0` | Изменить плотность |
| `add_car` | `color`, `type` (sedan/suv/truck) | Добавить машину |
| `remove_car` | `id` | Убрать машину |
| `change_speed` | `factor: 0.1-3.0` | Изменить скорость |
| `add_bus` | `route`, `number` | Добавить автобус |
| `remove_bus` | `id` | Убрать автобус |
| `add_pedestrian` | `direction` (left/right/cross) | Добавить пешехода |
| `remove_pedestrian` | `id` | Убрать пешехода |
| `change_traffic_light_phase` | `phase` (green/yellow/red), `intersection` (0-1) | Сменить фазу светофора |
| `change_weather` | `condition` (clear/cloudy/rain/snow/fog) | Сменить погоду |
| `add_holiday_decor` | `type` (trees/snowman/snow/flowers/flags/balloons/confetti/stars) | Добавить праздник |
| `remove_holiday_decor` | `type` | Убрать праздник |
| `start_rain` | `intensity: 0-1` | Начать дождь |
| `stop_rain` | — | Остановить дождь |
| `start_snow` | `intensity: 0-1` | Начать снег |
| `stop_snow` | — | Остановить снег |
| `change_time_of_day` | `phase` (morning/day/evening/night) | Сменить время суток |
| `add_vehicle` | `type`, `color` | Добавить транспорт |
| `remove_vehicle` | `id` | Убрать транспорт |
| `end` | — | Конец сценария |

## Промпт для LLM (`services/llm_agent.py`, константа `SYSTEM_PROMPT`)

```
Ты — генератор сценариев для 3D-анимации программной дороги «АЛЬБИОН».

Твоя задача — генерировать JSON-сценарии на основе описания пользователя.

Формат сценария:
{
  "id": "unique-id",
  "name": "Название сценария",
  "description": "Описание",
  "duration": 120,
  "version": "1.0",
  "created_at": "ISO-8601",
  "author": "user",
  "tags": ["tags"],
  "events": [
    {"t": 0, "do": "event_name", "params": {...}},
    ...
  ]
}

Доступные события (do):
- start_traffic, stop_traffic
- change_traffic_density (density: 0.1-3.0)
- change_speed (factor: 0.1-3.0)
- add_car, remove_car (color, type)
- add_bus, remove_bus (route, number)
- add_pedestrian, remove_pedestrian (direction: left/right/cross)
- change_traffic_light_phase (phase: green/yellow/red, intersection: 0-1)
- change_weather (condition: clear/cloudy/rain/snow/fog)
- start_rain, stop_rain (intensity: 0-1)
- start_snow, stop_snow (intensity: 0-1)
- change_time_of_day (phase: morning/day/evening/night)
- add_holiday_decor, remove_holiday_decor (type: trees/snowman/snow/flowers/flags/balloons/confetti/stars)
- end

Правила:
1. Сценарий должен быть логичным и последовательным.
2. Длительность — 30-300 секунд.
3. События должны быть упорядочены по времени.
4. Используй осмысленные id для машин/автобусов/пешеходов.
5. Возвращай ТОЛЬКО JSON, без markdown-обёртки.
```

## Настройки (JSON block в коде баннера)

Блок `<script type="application/json" id="banner-settings">` содержит:

```json
{
  "tilt": { "value": 32, "label": "Наклон камеры", "min": 5, "max": 85, "step": 1, "unit": "°" },
  "rotation": { "value": 38, "label": "Поворот камеры", "min": -180, "max": 180, "step": 1, "unit": "°" },
  "scale": { "value": 1, "label": "Масштаб", "min": 0.5, "max": 2, "step": 0.05, "unit": "×" },
  "dayNightPeriod": { "value": 48, "label": "Цикл день/ночь", "min": 10, "max": 180, "step": 1, "unit": "с" },
  "speedWave": { "value": 0.35, "label": "Амплитуда скорости", "min": 0, "max": 0.8, "step": 0.05, "unit": "×" },
  "speedWavePeriod": { "value": 19.6, "label": "Период волны скорости", "min": 4, "max": 60, "step": 0.5, "unit": "с" },
  "trafficMin": { "value": 0.55, "label": "Плотность трафика, мин", "min": 0.2, "max": 1, "step": 0.05, "unit": "×" },
  "trafficMax": { "value": 1.9, "label": "Плотность трафика, макс", "min": 1, "max": 3, "step": 0.05, "unit": "×" },
  "trafficChangeMin": { "value": 5, "label": "Смена плотности, мин", "min": 1, "max": 60, "step": 1, "unit": "с" },
  "trafficChangeMax": { "value": 12, "label": "Смена плотности, макс", "min": 2, "max": 120, "step": 1, "unit": "с" },
  "carMin": { "value": 6, "label": "Машин, мин", "min": 1, "max": 14, "step": 1 },
  "carMax": { "value": 13, "label": "Машин, макс", "min": 1, "max": 14, "step": 1 },
  "pedMin": { "value": 1, "label": "Пешеходов, мин", "min": 0, "max": 8, "step": 1 },
  "pedMax": { "value": 5, "label": "Пешеходов, макс", "min": 0, "max": 8, "step": 1 },
  "countChangeMin": { "value": 6, "label": "Смена количества, мин", "min": 1, "max": 60, "step": 1, "unit": "с" },
  "countChangeMax": { "value": 14, "label": "Смена количества, макс", "min": 2, "max": 120, "step": 1, "unit": "с" },
  "buses": { "value": true, "label": "Автобусы", "type": "boolean" },
  "quality": { "value": "eco", "label": "Качество", "type": "select", "options": [
    { "value": "eco", "label": "Эко" },
    { "value": "balanced", "label": "Баланс" },
    { "value": "max", "label": "Макс" }
  ] }
}
```

## БД таблицы

```sql
roadrunner_scenarios (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  scenario_data JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  author TEXT NOT NULL DEFAULT 'system'
)

roadrunner_settings (
  key TEXT PRIMARY KEY,
  settings JSONB NOT NULL
)
```

## Конфигурация (config/*.json)

- `city.json` — координаты, зоны пробок, главная дорога
- `holidays.json` — праздники и их декор
- `weather.json` — провайдеры погоды (Open-Meteo, Яндекс)
- `traffic.json` — провайдеры пробок (Яндекс, модель)
- `provider.json` — LLM провайдеры (Ollama, YandexGPT, OpenAI)
