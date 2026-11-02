# Оффлайн-карта PMTiles

Рабочий архив лежит вне Git, в `storage/map/rostov.pmtiles`:

```text
<проект>/storage/map/rostov.pmtiles
```

Путь по умолчанию — `/storage/map/rostov.pmtiles`. Его можно изменить в
админке: **Настройки → Карта → «URL PMTiles-файла»**.

Поддерживаются:

- **векторный PMTiles (MVT)** — рисуется через `protomaps-leaflet`:
  улицы, подписи городов и районов, поверх остаются маркеры Leaflet;
- **растровый PMTiles** (PNG / JPEG / WebP / AVIF) — рисуется собственным
  GridLayer.

Требования:

- сервер должен поддерживать HTTP Range-запросы (nginx и FastAPI/Starlette
  для `/storage/` это умеют);
- архив ограничен границей Ростовской области, карта выставляет `maxBounds`
  по заголовку архива;
- данные OpenStreetMap требуют атрибуции «© OpenStreetMap contributors».

Пример сборки архива из OSM-выгрузки:

```bash
# 1. Скачать актуальный PMTiles-экстракт Protomaps или собрать свой tilemaker.
# 2. Вырезать Ростовскую область по frontend/public/rostov-region.geojson:
pmtiles extract https://build.protomaps.com/YYYYMMDD.pmtiles \
  storage/map/rostov.pmtiles \
  --region=frontend/public/rostov-region.geojson \
  --maxzoom=15
```

В оффлайн-режиме геокодер недоступен: поиск по адресу отключается,
остаётся поиск по координатам и по адресам конструкций из базы.
