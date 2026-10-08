/*
 * Движок карты на Yandex Maps JS API 2.1.
 *
 * Публичный API полностью совпадает с Leaflet-версией (useMap.js),
 * чтобы MapView.vue не зависел от конкретного движка.
 *
 * ВАЖНО: перед createMap() нужно дождаться loadYandexMaps()
 * (см. src/map/yandexLoader.js).
 */

import { popupContent } from './popupContent'
import { groupByPoint } from '../utils/constructionGroups'
import { getAvailabilityState } from '../utils/availability'

const DEFAULT_CENTER = [47.2357, 39.7015]
const DEFAULT_ZOOM = 10

/* Тайминги анимации перелётов, мс. */
const FLY_DURATION = 400

const ALL_MONTHS = [
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь'
]

let ymaps = null
let map = null
let clusterer = null
let containerElement = null

let regionOutline = null
let maskPolygon = null

let searchPointPlacemark = null
let searchRadiusCircle = null

let centerChangeHandler = null

let constructions = []
let selectedMonths = []

let renderTimer = null
let resizeObserver = null

/* =========================================================
   HELPERS
   ========================================================= */

function normalizeItems(items) {
  return Array.isArray(items)
    ? items.filter(item => {
        const lat = Number(item?.lat)
        const lng = Number(item?.lng)

        return (
          Number.isFinite(lat) &&
          Number.isFinite(lng)
        )
      })
    : []
}

/*
 * Оставляем по одной записи на комбинацию СТОРОНА + ФОРМАТ.
 * Записи без стороны не отбрасываем (как в Leaflet-версии).
 */
function uniqueSides(items) {
  const result = []

  for (const item of items) {
    const side = String(item?.side || '')
      .trim()
      .toUpperCase()

    const type = String(item?.type || '')
      .trim()
      .toUpperCase()

    if (!side) {
      result.push(item)
      continue
    }

    const exists = result.some(existing => {
      const existingSide = String(existing?.side || '')
        .trim()
        .toUpperCase()

      const existingType = String(existing?.type || '')
        .trim()
        .toUpperCase()

      return (
        existingSide === side &&
        existingType === type
      )
    })

    if (!exists) {
      result.push(item)
    }
  }

  return result
}

/* =========================================================
   MARKER COLOR
   ========================================================= */

/*
 * Цвет точки — комбинация статусов её сторон (по выбранным месяцам):
 *   всё свободно          → зелёный;
 *   всё занято            → красный;
 *   иначе (есть резерв или смесь) → оранжевый.
 */
function markerColor(items) {
  const months =
    Array.isArray(selectedMonths) &&
    selectedMonths.length
      ? selectedMonths
      : ALL_MONTHS

  const sides = uniqueSides(items)

  if (!sides.length) {
    return '#2ea66d'
  }

  let freeCount = 0
  let reserveCount = 0
  let busyCount = 0

  for (const item of sides) {
    for (const month of months) {
      const state = getAvailabilityState(item, month)

      if (state === 'busy') {
        busyCount += 1
      } else if (state === 'reserve') {
        reserveCount += 1
      } else {
        freeCount += 1
      }
    }
  }

  if (busyCount === 0 && reserveCount === 0) {
    return '#2ea66d'
  }

  if (freeCount === 0 && reserveCount === 0) {
    return '#e24b42'
  }

  return '#e6a51c'
}

/*
 * Иконка-кружок как SVG data-URI: повторяет вид .albion-dot
 * (16×16, белая обводка 2px, лёгкая тень).
 */
function dotIconHref(color) {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" ' +
    'width="16" height="16" viewBox="0 0 16 16">' +
    '<defs>' +
    '<filter id="s" x="-50%" y="-50%" width="200%" height="200%">' +
    '<feDropShadow dx="0" dy="1" stdDeviation="1.1" ' +
    'flood-color="#000000" flood-opacity="0.45"/>' +
    '</filter>' +
    '</defs>' +
    `<circle cx="8" cy="8" r="6" fill="${color}" ` +
    'stroke="#ffffff" stroke-width="2" filter="url(#s)"/>' +
    '</svg>'

  return (
    'data:image/svg+xml;charset=utf-8,' +
    encodeURIComponent(svg)
  )
}

/* =========================================================
   MAP
   ========================================================= */

function handleBoundsChange() {
  if (!map || !centerChangeHandler) {
    return
  }

  const center = map.getCenter()

  centerChangeHandler({
    lat: center[0],
    lng: center[1]
  })
}

function createMap(element) {
  if (!element) {
    throw new Error('Map element not found')
  }

  if (map) {
    return map
  }

  if (
    typeof window === 'undefined' ||
    !window.ymaps ||
    !window.ymaps.Map
  ) {
    throw new Error(
      'Yandex Maps API не загружен. Дождитесь loadYandexMaps() перед createMap().'
    )
  }

  ymaps = window.ymaps
  containerElement = element

  map = new ymaps.Map(
    element,
    {
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      controls: ['zoomControl'],
      behaviors: ['default']
    },
    {
      minZoom: 3,
      maxZoom: 19,

      /* Прячем блок «Открыть в Яндекс.Картах». */
      suppressMapOpenBlock: true
    }
  )

  map.events.add('boundschange', handleBoundsChange)
  map.events.add('actionend', handleBoundsChange)

  clusterer = new ymaps.Clusterer({
    gridSize: 60,
    maxZoom: 19,
    disableClusteringAtZoom: 15,
    clusterDisableClickZoom: false,
    clusterOpenBalloonOnClick: false,
    hasBalloon: false
  })

  map.geoObjects.add(clusterer)

  resizeObserver = new ResizeObserver(() => {
    invalidateSize()
  })

  resizeObserver.observe(element)

  return map
}

/* =========================================================
   MARKERS
   ========================================================= */

function createPlacemark(group) {
  const items = uniqueSides(group.items)

  if (!items.length) {
    return null
  }

  const first = items[0]

  const lat = Number(first.lat)
  const lng = Number(first.lng)

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng)
  ) {
    return null
  }

  const color = markerColor(items)

  const isDoublePopup = items.length >= 2

  return new ymaps.Placemark(
    [lat, lng],
    {
      /*
       * balloonContentBody — HTML-попап из общего модуля,
       * тот же, что использует Leaflet-движок.
       */
      balloonContentBody: popupContent(items),

      hintContent:
        first.address ||
        first.name ||
        'Рекламная конструкция'
    },
    {
      iconImageHref: dotIconHref(color),
      iconImageSize: [16, 16],
      iconImageOffset: [-8, -8],

      /* Кликабельная область — кружок вокруг центра иконки. */
      iconShape: {
        type: 'Circle',
        coordinates: [8, 8],
        radius: 9
      },

      balloonMaxWidth: isDoublePopup ? 780 : 360,
      balloonMinWidth: isDoublePopup ? 700 : 300,
      balloonAutoPan: true,

      hasBalloon: true,
      hasHint: true
    }
  )
}

function renderMarkers() {
  if (!map || !clusterer) {
    return
  }

  clusterer.removeAll()

  const normalized = normalizeItems(constructions)
  const groups = groupByPoint(normalized)

  const placemarks = []

  for (const group of groups) {
    const placemark = createPlacemark(group)

    if (placemark) {
      placemarks.push(placemark)
    }
  }

  if (placemarks.length) {
    clusterer.add(placemarks)
  }

  console.log(
    `Albion map (Yandex): ${normalized.length} visible / ${constructions.length} filtered`
  )

  console.log(
    `Albion map (Yandex): ${groups.length} physical constructions / ${placemarks.length} markers`
  )
}

function scheduleRender() {
  if (renderTimer) {
    clearTimeout(renderTimer)
  }

  renderTimer = setTimeout(() => {
    renderTimer = null
    renderMarkers()
  }, 0)
}

/* =========================================================
   PUBLIC DATA API
   ========================================================= */

function setConstructions(items, months = []) {
  constructions = Array.isArray(items)
    ? items
    : []

  selectedMonths = Array.isArray(months)
    ? months
    : []

  /*
   * В отличие от Leaflet, перерисовка маркеров не сдвигает
   * карту — центр и зум сохраняются сами.
   */
  scheduleRender()
}

function setCenterChangeHandler(handler) {
  centerChangeHandler =
    typeof handler === 'function'
      ? handler
      : null

  if (map && centerChangeHandler) {
    const center = map.getCenter()

    centerChangeHandler({
      lat: center[0],
      lng: center[1]
    })
  }
}

function getCoordinatesAtScreenPoint(clientX, clientY) {
  if (!map) {
    return null
  }

  const element =
    containerElement ||
    (map.container && map.container.getElement
      ? map.container.getElement()
      : null)

  if (!element) {
    return null
  }

  const rect = element.getBoundingClientRect()

  const x = clientX - rect.left
  const y = clientY - rect.top

  const zoom = map.getZoom()

  let globalPoint = null

  /*
   * API 2.1: convertScreenToGlobalPixel([x, y]).
   * Фоллбэк — пересчёт от глобального пиксельного центра.
   */
  if (
    typeof map.convertScreenToGlobalPixel ===
    'function'
  ) {
    globalPoint = map.convertScreenToGlobalPixel([x, y])
  } else if (
    typeof map.convertScreenToGlobal === 'function'
  ) {
    globalPoint = map.convertScreenToGlobal([x, y])
  } else {
    const center = map.getGlobalPixelCenter()

    globalPoint = [
      center[0] + (x - rect.width / 2),
      center[1] + (y - rect.height / 2)
    ]
  }

  if (!globalPoint) {
    return null
  }

  const projection = map.options.get('projection')

  if (!projection || !projection.fromGlobalPixels) {
    return null
  }

  const geoPoint = projection.fromGlobalPixels(
    globalPoint,
    zoom
  )

  return {
    lat: geoPoint[0],
    lng: geoPoint[1]
  }
}

function setMapDraggingEnabled(enabled) {
  if (!map) {
    return
  }

  try {
    if (enabled) {
      map.behaviors.enable('drag')
    } else {
      map.behaviors.disable('drag')
    }
  } catch (error) {
    console.warn(
      'Albion map (Yandex): не удалось изменить режим перетаскивания',
      error
    )
  }
}

function setSearchPoint(lat, lng) {
  if (!map) {
    return
  }

  const latitude = Number(lat)
  const longitude = Number(lng)

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude)
  ) {
    return
  }

  const position = [latitude, longitude]

  if (!searchPointPlacemark) {
    searchPointPlacemark = new ymaps.Placemark(
      position,
      {},
      {
        preset: 'islands#redIcon',
        interactivityModel: 'default#silent',
        hasBalloon: false,
        hasHint: false
      }
    )

    map.geoObjects.add(searchPointPlacemark)
  } else {
    searchPointPlacemark.geometry.setCoordinates(
      position
    )
  }
}

function clearSearchPoint() {
  if (!searchPointPlacemark) {
    return
  }

  if (map) {
    map.geoObjects.remove(searchPointPlacemark)
  }

  searchPointPlacemark = null
}

function setSearchRadius(lat, lng, radius) {
  if (!map) {
    return
  }

  const latitude = Number(lat)
  const longitude = Number(lng)
  const distance = Number(radius)

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    !Number.isFinite(distance) ||
    distance <= 0
  ) {
    return
  }

  const geometry = [[latitude, longitude], distance]

  if (!searchRadiusCircle) {
    searchRadiusCircle = new ymaps.Circle(
      geometry,
      {},
      {
        fillColor: '#e12a1f',
        fillOpacity: 0.10,
        strokeColor: '#e12a1f',
        strokeOpacity: 0.85,
        strokeWidth: 2,
        interactivityModel: 'default#silent'
      }
    )

    map.geoObjects.add(searchRadiusCircle)
  } else {
    searchRadiusCircle.geometry.setCoordinates(
      geometry
    )
  }
}

function clearSearchRadius() {
  if (!searchRadiusCircle) {
    return
  }

  if (map) {
    map.geoObjects.remove(searchRadiusCircle)
  }

  searchRadiusCircle = null
}

function setMapCenter(lat, lng, zoom = 14) {
  if (!map) {
    return
  }

  const latitude = Number(lat)
  const longitude = Number(lng)

  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude)
  ) {
    return
  }

  map.setCenter([latitude, longitude], zoom, {
    duration: FLY_DURATION
  })
}

function getVisibleConstructions() {
  if (!map) {
    return []
  }

  const bounds = map.getBounds()

  if (!bounds || !bounds.length) {
    return []
  }

  const [[minLat, minLng], [maxLat, maxLng]] = bounds

  return constructions.filter(item => {
    const lat = Number(item?.lat)
    const lng = Number(item?.lng)

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lng)
    ) {
      return false
    }

    return (
      lat >= minLat &&
      lat <= maxLat &&
      lng >= minLng &&
      lng <= maxLng
    )
  })
}

/* =========================================================
   REGION (маска области + граница)
   ========================================================= */

/* Внешние кольца области из GeoJSON в формате [lat, lng]. */
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

  return rings.map(ring =>
    ring.map(([lng, lat]) => [lat, lng])
  )
}

function removeRegionLayers() {
  if (!map) {
    return
  }

  if (regionOutline) {
    map.geoObjects.remove(regionOutline)
    regionOutline = null
  }

  if (maskPolygon) {
    map.geoObjects.remove(maskPolygon)
    maskPolygon = null
  }
}

async function loadRegion() {
  if (!map) {
    return
  }

  try {
    const response = await fetch('/rostov-region.geojson')

    if (!response.ok) {
      throw new Error(`GeoJSON error: ${response.status}`)
    }

    const geojson = await response.json()

    removeRegionLayers()

    const rings = geojsonOuterRings(geojson)

    const worldRing = [
      [90, -180],
      [90, 180],
      [-90, 180],
      [-90, -180],
      [90, -180]
    ]

    /*
     * Маска: всё ВНЕ Ростовской области затемняем серым.
     * Полигон мира с «дыркой» по области (fillRule: evenOdd).
     */
    maskPolygon = new ymaps.Polygon(
      [worldRing, ...rings],
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

    map.geoObjects.add(maskPolygon)

    /* Граница области — поверх маски. */
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

    map.geoObjects.add(regionOutline)

    console.log(
      'Albion Map (Yandex): Ростовская область и маска загружены'
    )
  } catch (error) {
    console.error(
      'Albion Map (Yandex): ошибка загрузки GeoJSON',
      error
    )
  }
}

/* =========================================================
   UTILS
   ========================================================= */

function invalidateSize() {
  if (!map) {
    return
  }

  setTimeout(() => {
    if (map && map.container) {
      map.container.fitToViewport()
    }
  }, 100)
}

function destroyMap() {
  clearSearchPoint()
  clearSearchRadius()

  if (renderTimer) {
    clearTimeout(renderTimer)
    renderTimer = null
  }

  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (map) {
    map.events.remove(
      'boundschange',
      handleBoundsChange
    )

    map.events.remove(
      'actionend',
      handleBoundsChange
    )
  }

  regionOutline = null
  maskPolygon = null

  if (clusterer) {
    clusterer.removeAll()
  }

  clusterer = null

  if (map) {
    map.destroy()
  }

  map = null
  ymaps = null
  containerElement = null
  centerChangeHandler = null
  constructions = []
  selectedMonths = []
}

/* Общая обработка набора точек: один → перелёт, много → bounds. */
function flyToPoints(points, fitOptions) {
  if (points.length === 1) {
    map.setCenter(points[0], fitOptions.maxZoom, {
      duration: FLY_DURATION
    })
    return
  }

  let minLat = Infinity
  let minLng = Infinity
  let maxLat = -Infinity
  let maxLng = -Infinity

  for (const [lat, lng] of points) {
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
    if (lng < minLng) minLng = lng
    if (lng > maxLng) maxLng = lng
  }

  const bounds = [
    [minLat, minLng],
    [maxLat, maxLng]
  ]

  map.setBounds(bounds, {
    checkZoomRange: true,
    zoomMargin: fitOptions.margin,
    duration: FLY_DURATION
  })

  /* setBounds не принимает maxZoom — ограничиваем зум после. */
  setTimeout(() => {
    if (map && map.getZoom() > fitOptions.maxZoom) {
      map.setZoom(fitOptions.maxZoom, {
        duration: FLY_DURATION
      })
    }
  }, FLY_DURATION + 50)
}

function fitToConstructions(items = constructions) {
  if (!map) {
    return
  }

  const normalized = normalizeItems(items)

  if (!normalized.length) {
    return
  }

  const points = normalized.map(item => [
    Number(item.lat),
    Number(item.lng)
  ])

  flyToPoints(points, {
    margin: 30,
    maxZoom: 13
  })
}

function focusToItems(items, predicate) {
  if (!map) {
    return
  }

  const source = Array.isArray(items) ? items : []

  const matched = source.filter(item => {
    try {
      return typeof predicate === 'function'
        ? predicate(item)
        : true
    } catch {
      return false
    }
  })

  const normalized = normalizeItems(matched)

  if (!normalized.length) {
    return
  }

  const points = normalized.map(item => [
    Number(item.lat),
    Number(item.lng)
  ])

  flyToPoints(points, {
    margin: 60,
    maxZoom: 14
  })
}

/* =========================================================
   EXPORT
   ========================================================= */

export function useYandexMap() {
  return {
    createMap,

    setConstructions,

    getVisibleConstructions,

    loadRegion,

    invalidateSize,

    fitToConstructions,
    focusToItems,
    setCenterChangeHandler,
    setMapCenter,

    setSearchPoint,
    clearSearchPoint,

    getCoordinatesAtScreenPoint,
    setMapDraggingEnabled,

    setSearchRadius,
    clearSearchRadius,

    destroyMap
  }
}
