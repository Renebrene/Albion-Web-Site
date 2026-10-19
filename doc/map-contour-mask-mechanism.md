# Механизм создания контура и маски карты

Документ описывает реализацию контура Ростовской области и затемнения карты за пределами региона. Исходная реализация поддерживает два картографических движка:

- Leaflet / OpenStreetMap — `frontend/src/map/useMap.js`;
- Yandex Maps JS API 2.1 — `frontend/src/map/useYandexMap.js`.

Исходные координаты региона находятся в `frontend/public/rostov-region.geojson`.

## 1. Общая схема

Механизм состоит из двух слоёв:

```text
maskLayer / maskPolygon
    затемняет территорию за пределами региона

regionLayer / regionOutline
    рисует видимую границу региона
```

Маска строится как полигон с внешним кольцом и кольцом региона:

```text
внешнее кольцо
      минус
контур региона
      =
затемнённый фон вокруг региона
```

Для вырезания региона используется правило заполнения `even-odd`:

```js
fillRule: 'evenodd' // Leaflet
fillRule: 'evenOdd' // Yandex Maps
```

## 2. Загрузка GeoJSON

Регион загружается из публичного файла:

```js
const response = await fetch('/rostov-region.geojson')

if (!response.ok) {
  throw new Error(`GeoJSON error: ${response.status}`)
}

const geojson = await response.json()
```

Вызов выполняется после инициализации карты в `frontend/src/map/MapView.vue`:

```js
api.setConstructions(props.constructions, props.selectedMonths)
await api.loadRegion()
```

Если компонент был размонтирован во время загрузки, результат не применяется к уничтоженной карте.

## 3. Извлечение контуров из GeoJSON

GeoJSON хранит координаты в формате:

```text
[longitude, latitude]
[долгота, широта]
```

Картографические библиотеки проекта используют формат:

```text
[latitude, longitude]
[широта, долгота]
```

Функция `geojsonOuterRings()` поддерживает `FeatureCollection`, одиночный `Feature`, `Polygon` и `MultiPolygon`:

```js
function geojsonOuterRings(geojson) {
  const features =
    geojson?.type === 'FeatureCollection'
      ? geojson.features || []
      : geojson?.type === 'Feature'
        ? [geojson]
        : geojson?.geometry
          ? [{ geometry: geojson.geometry }]
          : []

  const rings = []

  for (const feature of features) {
    const geometry = feature?.geometry

    if (!geometry) {
      continue
    }

    if (geometry.type === 'Polygon') {
      rings.push(geometry.coordinates[0])
    } else if (geometry.type === 'MultiPolygon') {
      for (const polygon of geometry.coordinates) {
        if (polygon[0]) {
          rings.push(polygon[0])
        }
      }
    }
  }

  return rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
}
```

### Важная особенность

В текущей реализации используется только внешнее кольцо:

```js
geometry.coordinates[0]
```

Внутренние кольца-проёмы (`coordinates[1]`, `coordinates[2]` и т. д.) не извлекаются.

## 4. Реализация Leaflet

Исходный код: `frontend/src/map/useMap.js:694-814`.

### 4.1. Внешнее мировое кольцо

Для Leaflet используется прямоугольник всего мира:

```js
const worldRing = [
  [90, -180],
  [90, 180],
  [-90, 180],
  [-90, -180],
  [90, -180]
]
```

### 4.2. Создание маски

```js
const rings = geojsonOuterRings(geojson)

maskLayer = L.polygon([worldRing, ...rings], {
  stroke: false,
  fill: true,
  fillColor: '#2f383f',
  fillOpacity: 0.82,
  fillRule: 'evenodd',
  interactive: false
})

maskLayer.addTo(current)
maskLayer.bringToBack()
```

`worldRing` образует затемнённую область, а `rings` вырезают регион за счёт `evenodd`.

### 4.3. Отображение границы

Граница создаётся отдельным GeoJSON-слоем:

```js
regionLayer = L.geoJSON(geojson, {
  style: {
    color: '#5b6670',
    weight: 1.5,
    opacity: 0.9,
    fill: false,
    fillOpacity: 0
  },
  interactive: false
})

regionLayer.addTo(current)
```

Параметры:

- `fill: false` — регион не заливается отдельным цветом;
- `color` — цвет линии контура;
- `weight` — толщина линии;
- `interactive: false` — слой не перехватывает клики.

## 5. Реализация Yandex Maps

Исходный код: `frontend/src/map/useYandexMap.js:634-865`.

### 5.1. Почему не используется мировой прямоугольник

Yandex Maps JS API 2.1 может отбросить слишком большой контур. При этом из геометрии маски исчезает внешнее кольцо, и маска становится инвертированной: затемняется сам регион, а не фон вокруг него.

Поэтому внешнее кольцо строится по текущему viewport карты с запасом.

Ограничения движка:

```js
const MAX_RING_LNG = 140
const MAX_RING_LAT = 100
```

### 5.2. Создание внешнего кольца viewport

```js
function viewportMaskRing(padFactor = 0.5) {
  if (!map) {
    return null
  }

  const bounds = map.getBounds()

  if (!bounds || !bounds.length) {
    return null
  }

  const [[south, west], [north, east]] = bounds

  const padLat = Math.max((north - south) * padFactor, 1)
  const padLng = Math.max((east - west) * padFactor, 1)

  let s = Math.max(-85, south - padLat)
  let n = Math.min(85, north + padLat)
  let w = west - padLng
  let e = east + padLng

  if (n - s > MAX_RING_LAT) {
    const center = (s + n) / 2
    s = center - MAX_RING_LAT / 2
    n = center + MAX_RING_LAT / 2
  }

  if (e - w > MAX_RING_LNG) {
    const center = (w + e) / 2
    w = center - MAX_RING_LNG / 2
    e = center + MAX_RING_LNG / 2
  }

  return [
    [s, w],
    [s, e],
    [n, e],
    [n, w],
    [s, w]
  ]
}
```

Алгоритм:

1. Получить текущие границы карты через `map.getBounds()`.
2. Добавить запас `50%` по широте и долготе.
3. Ограничить широту значениями `-85..85`.
4. Ограничить размер контура пределами `MAX_RING_LAT` и `MAX_RING_LNG`.
5. Вернуть замкнутый прямоугольник.

Запас за пределами viewport нужен, чтобы край маски не был виден при панорамировании.

### 5.3. Создание полигона-маски

```js
const rings = geojsonOuterRings(geojson)
const maskRing = viewportMaskRing()

maskPolygon = new ymaps.Polygon(
  maskRing ? [maskRing, ...rings] : rings,
  {},
  {
    fill: true,
    fillColor: '#2f383f',
    fillOpacity: 0.82,
    stroke: false,
    fillRule: 'evenOdd',
    interactivityModel: 'default#silent'
  }
)

current.geoObjects.add(maskPolygon)
```

Геометрия имеет вид:

```js
[
  внешнийПрямоугольникViewport,
  контурРегиона1,
  контурРегиона2
]
```

`evenOdd` оставляет регион прозрачным, а всё остальное пространство затемняет.

### 5.4. Отображение границы

```js
regionOutline = new ymaps.Polyline(
  rings,
  {},
  {
    strokeColor: '#5b6670',
    strokeWidth: 1.5,
    strokeOpacity: 0.9,
    fill: false,
    interactivityModel: 'default#silent'
  }
)

current.geoObjects.add(regionOutline)
```

`Polyline` используется только для линии границы, без заливки.

## 6. Обновление маски при перемещении и масштабировании

Для Yandex Maps внешний прямоугольник зависит от текущего viewport. При изменении границ карты геометрия маски обновляется.

```js
function refreshMaskGeometry() {
  if (!map || !maskPolygon || !regionRings.length) {
    return
  }

  const ring = viewportMaskRing()

  if (!ring) {
    return
  }

  try {
    maskPolygon.geometry.setCoordinates([ring, ...regionRings])
  } catch (error) {
    console.warn('Albion Map (Yandex): не удалось обновить маску', error)
  }
}
```

Событие `boundschange` может срабатывать часто, поэтому обновление ограничивается одним кадром браузера:

```js
function scheduleMaskRefresh() {
  if (maskRefreshFrame) {
    return
  }

  maskRefreshFrame = requestAnimationFrame(() => {
    maskRefreshFrame = null
    refreshMaskGeometry()
  })
}
```

Подписка выполняется после создания маски:

```js
current.events.add('boundschange', scheduleMaskRefresh)
```

Итоговая цепочка:

```text
панорамирование или zoom
        ↓
событие boundschange
        ↓
requestAnimationFrame
        ↓
viewportMaskRing()
        ↓
maskPolygon.geometry.setCoordinates(...)
```

## 7. Удаление слоёв и очистка ресурсов

Перед повторной загрузкой региона старые слои удаляются.

### Leaflet

```js
if (regionLayer) {
  current.removeLayer(regionLayer)
  regionLayer = null
}

if (maskLayer) {
  current.removeLayer(maskLayer)
  maskLayer = null
}
```

### Yandex Maps

```js
function removeRegionLayers() {
  if (!map) {
    return
  }

  map.events.remove('boundschange', scheduleMaskRefresh)

  if (maskRefreshFrame) {
    cancelAnimationFrame(maskRefreshFrame)
    maskRefreshFrame = null
  }

  if (regionOutline) {
    map.geoObjects.remove(regionOutline)
    regionOutline = null
  }

  if (maskPolygon) {
    map.geoObjects.remove(maskPolygon)
    maskPolygon = null
  }

  regionRings = []
}
```

Очистка предотвращает:

- дублирование масок;
- наложение старых контуров;
- утечки обработчиков `boundschange`;
- выполнение `requestAnimationFrame` после уничтожения карты.

## 8. Минимальный перенос в другой проект

Для переноса механизма нужны:

1. GeoJSON региона.
2. Загрузка JSON.
3. Извлечение внешних колец.
4. Преобразование координат `[lng, lat]` в `[lat, lng]`, если этого требует движок.
5. Создание внешнего кольца мира или viewport.
6. Создание полигона с правилом `even-odd`.
7. Отдельная линия границы.
8. Обновление внешнего кольца при `move` / `zoom`.
9. Очистка слоёв и обработчиков при уничтожении карты.

Общий псевдокод:

```js
const regionRings = extractOuterRings(geojson)
const outerRing = getViewportRing() // или мировой прямоугольник

const mask = createPolygon(
  [outerRing, ...regionRings],
  {
    fillColor: '#2f383f',
    fillOpacity: 0.82,
    fillRule: 'evenodd'
  }
)

const outline = createPolyline(regionRings, {
  color: '#5b6670',
  width: 1.5
})

map.add(mask)
map.add(outline)
```

Для Leaflet допустим мировой прямоугольник:

```js
const outerRing = [
  [90, -180],
  [90, 180],
  [-90, 180],
  [-90, -180],
  [90, -180]
]
```

Для Yandex Maps предпочтителен динамический прямоугольник текущего viewport с ограничением максимального размера.

## 9. Исходные файлы проекта

```text
frontend/public/rostov-region.geojson
frontend/src/map/useMap.js:698-810
frontend/src/map/useYandexMap.js:638-865
frontend/src/map/MapView.vue:197-204
```
