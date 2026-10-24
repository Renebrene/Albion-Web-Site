import L from 'leaflet'
import 'leaflet.markercluster'

import { popupContent, popupLayout } from './popupContent'
import { getAvailabilityState } from '../utils/availability'
import { MONTHS } from '../utils/constructionGroups'
import { mapDotColors, mapColorMode } from '../config/mapColors'
import { SEARCH_POINT_ICON, searchPointIconHref } from './searchPointIcon'
import { lazyPopups } from '../config/lazyPopups'
import { mapDebug } from './mapDebug'

const DEFAULT_CENTER = [47.2357, 39.7015]
const DEFAULT_ZOOM = 10

let map = null
let clusterGroup = null
let regionLayer = null
let maskLayer = null
let centerChangeHandler = null

// Точка поиска и визуальный радиус.
let searchPointMarker = null
let searchPointHoverHandler = null
let searchPointClickHandler = null
let searchRadiusCircle = null

let constructions = []
let selectedMonths = []

let renderTimer = null
let resizeObserver = null

/* =========================================================
   HELPERS
   ========================================================= */

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

/*
 * Точка на карте = КООРДИНАТА (округление ~1 м).
 *
 * Подпись адреса и номер конструкции в ключ НЕ входят: у одной точки
 * они могут отличаться (варианты написания адреса, разные номера у
 * щита и экрана) — это всё равно одна общая точка.
 *
 * Без координат — откат на адрес, чтобы не слить разные объекты.
 */
function constructionKey(item) {
  const lat = Number(item?.lat)
  const lng = Number(item?.lng)

  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    return `${lat.toFixed(5)}|${lng.toFixed(5)}`
  }

  const city = String(item?.city || '').trim()
  const address = String(item?.address || item?.name || '').trim()

  return `noc|${city}|${address}`.toLowerCase()
}

function normalizeItems(items) {
  return Array.isArray(items)
    ? items.filter(item => {
        const lat = Number(item?.lat)
        const lng = Number(item?.lng)

        return Number.isFinite(lat) && Number.isFinite(lng)
      })
    : []
}

/*
 * Группируем только уже отфильтрованные записи.
 *
 * Это принципиально:
 *
 * A прошла + B не прошла
 * → в группе будет только A
 *
 * A прошла + B прошла
 * → в группе A + B
 */
function groupConstructions(items) {
  const groups = new Map()

  for (const item of items) {
    const key = constructionKey(item)

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        items: []
      })
    }

    groups.get(key).items.push(item)
  }

  return Array.from(groups.values())
}

function uniqueSides(items) {
  const result = []

  for (const item of items) {
    const side = String(item?.side || '')
      .trim()
      .toUpperCase()

    const type = String(item?.type || '')
      .trim()
      .toUpperCase()

    /*
     * Если сторона не указана — всё равно показываем запись.
     */
    if (!side) {
      result.push(item)
      continue
    }

    /*
     * Одинаковая буква стороны у РАЗНЫХ форматов (например, B
     * у щита и B у видеоэкрана) — это разные блоки, поэтому
     * ключ дедупликации включает ещё и формат.
     */
    const exists = result.some(existing => {
      const existingSide = String(existing?.side || '')
        .trim()
        .toUpperCase()

      const existingType = String(existing?.type || '')
        .trim()
        .toUpperCase()

      return existingSide === side && existingType === type
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
 *   всё свободно                  → mapDotColors.free;
 *   всё занято                    → mapDotColors.busy;
 *   иначе (есть резерв или смесь) → mapDotColors.mixed.
 * Сами цвета задаются в админ-настройках (см. config/mapColors.js).
 */
function markerColor(items) {
  const months =
    Array.isArray(selectedMonths) && selectedMonths.length
      ? selectedMonths
      : MONTHS.map(month => month.full)

  const sides = uniqueSides(items)

  if (!sides.length) {
    return mapDotColors.value.free
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

  /*
   * Двухцветная логика: зелёный, если есть хотя бы одна свободная
   * поверхность; иначе красный (всё занято/резерв/утверждение).
   * Оранжевый в этом режиме не используется.
   */
  if (mapColorMode.value === 'two') {
    return freeCount > 0 ? mapDotColors.value.free : mapDotColors.value.busy
  }

  // Всё свободно → «свободный» цвет.
  if (busyCount === 0 && reserveCount === 0) {
    return mapDotColors.value.free
  }

  // Всё занято → «занятый» цвет.
  if (freeCount === 0 && reserveCount === 0) {
    return mapDotColors.value.busy
  }

  // Есть резерв или смесь → «смешанный» цвет.
  return mapDotColors.value.mixed
}

function markerIconFor(color) {
  return L.divIcon({
    className: 'albion-dot-wrapper',

    html: `
      <div
        class="albion-dot"
        style="
          background:${escapeHtml(color)};
        "
      ></div>
    `,

    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -9]
  })
}

/* =========================================================
   MAP
   ========================================================= */

function createMap(element) {
  if (!element) {
    throw new Error('Map element not found')
  }

  if (map) {
    return map
  }

  map = L.map(element, {
    center: DEFAULT_CENTER,
    zoom: DEFAULT_ZOOM,

    zoomControl: true,

    preferCanvas: true,

    attributionControl: true,
    attributionControlOptions: {
      prefix: false
    }
  })

  // Убираем стандартный логотип и надпись Leaflet,
  // оставляя атрибуцию OpenStreetMap.
  map.attributionControl.setPrefix(false)

  map.on('move', () => {
    if (!map || !centerChangeHandler) {
      return
    }

    const center = map.getCenter()

    centerChangeHandler({
      lat: center.lat,
      lng: center.lng
    })
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,

    attribution: '&copy; OpenStreetMap contributors',

    crossOrigin: true
  }).addTo(map)

  clusterGroup = L.markerClusterGroup({
    chunkedLoading: true,

    chunkInterval: 100,

    chunkDelay: 20,

    removeOutsideVisibleBounds: true,

    maxClusterRadius: 60,

    disableClusteringAtZoom: 15,

    spiderfyOnMaxZoom: true,

    showCoverageOnHover: false,

    zoomToBoundsOnClick: true
  })

  map.addLayer(clusterGroup)

  resizeObserver = new ResizeObserver(() => {
    invalidateSize()
  })

  resizeObserver.observe(element)

  return map
}

/* =========================================================
   MARKERS
   ========================================================= */

/*
 * Параметры попапа зависят от числа ВИДИМЫХ КАРТОЧЕК (popupLayout), а не от
 * сырого числа сторон: иначе призматрон A(1)+A(2)+A(3) (3 стороны → одна
 * карточка) получал широкую обёртку при узком контенте.
 */
function popupOptions(isDouble) {
  return {
    className: isDouble
      ? 'albion-popup albion-popup-double'
      : 'albion-popup albion-popup-single',

    maxWidth: isDouble ? 580 : 340,

    minWidth: isDouble ? 540 : 300,

    closeButton: true,

    autoPan: true,

    autoPanPadding: isDouble ? [40, 40] : [30, 30]
  }
}

/*
 * Карта уже нарисованных маркеров: ключ точки → запись.
 *
 * Нужна, чтобы при смене фильтра переиспользовать существующие маркеры,
 * а не сносить и пересоздавать все (см. renderMarkers).
 */
const markerByKey = new Map()

/* Ленивый попап: разметка собирается при открытии и читает свежие items. */
function bindLazyPopup(entry, isDouble) {
  entry.marker.bindPopup(() => {
    entry.html = popupContent(entry.items)

    return entry.html
  }, popupOptions(isDouble))
}

/*
 * Создаёт маркер для группы сторон. Возвращает запись для markerByKey
 * либо null, если координат нет.
 */
function buildMarker(items, isDouble, lazy) {
  /*
   * Координаты берём из первой прошедшей стороны.
   * Обычно A и B физически имеют одинаковые координаты.
   */
  const first = items[0]

  const lat = Number(first.lat)
  const lng = Number(first.lng)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return null
  }

  const color = markerColor(items)

  const marker = L.marker([lat, lng], {
    icon: markerIconFor(color),

    keyboard: true,

    riseOnHover: true,

    title: first.address || first.name || 'Рекламная конструкция'
  })

  const entry = {
    marker,
    items,
    html: '',
    isDouble,
    lazy,
    color,
    lat,
    lng
  }

  if (lazy) {
    bindLazyPopup(entry, isDouble)
  } else {
    entry.html = popupContent(items)
    marker.bindPopup(entry.html, popupOptions(isDouble))
  }

  return entry
}

/*
 * Дифф-обновление маркеров вместо полного пересоздания.
 *
 * Перебираем группы физических точек и для каждой:
 *   - новую точку добавляем;
 *   - существующую переиспользуем: меняем координаты/цвет/попап только если
 *     они реально изменились (сравнение с прошлым состоянием в markerByKey);
 *   - исчезнувшие точки удаляем.
 *
 * Это убирает «мигание» и лишнюю работу при каждом изменении фильтра.
 */
function renderMarkers() {
  if (!map || !clusterGroup) {
    return
  }

  const normalized = normalizeItems(constructions)

  const groups = groupConstructions(normalized)

  const nextKeys = new Set()

  for (const group of groups) {
    const items = uniqueSides(group.items)

    if (!items.length) {
      continue
    }

    const first = items[0]

    const lat = Number(first.lat)
    const lng = Number(first.lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      continue
    }

    const key = group.key

    nextKeys.add(key)

    const isDouble = popupLayout(items) !== 'single'

    const color = markerColor(items)

    const lazy = lazyPopups.value

    let entry = markerByKey.get(key)

    // Новая точка — создаём и добавляем.
    if (!entry) {
      entry = buildMarker(items, isDouble, lazy)

      if (!entry) {
        continue
      }

      clusterGroup.addLayer(entry.marker)

      markerByKey.set(key, entry)

      continue
    }

    const itemsChanged = entry.items !== items

    entry.items = items

    // Точка уже на карте — правим только то, что изменилось.
    if (entry.lat !== lat || entry.lng !== lng) {
      entry.marker.setLatLng([lat, lng])
      entry.lat = lat
      entry.lng = lng
    }

    if (entry.color !== color) {
      entry.marker.setIcon(markerIconFor(color))
      entry.color = color
    }

    if (entry.lazy !== lazy || entry.isDouble !== isDouble) {
      // Смена режима или компоновки — нужна повторная привязка попапа.
      entry.lazy = lazy
      entry.isDouble = isDouble

      if (lazy) {
        bindLazyPopup(entry, isDouble)
      } else {
        entry.html = popupContent(items)
        entry.marker.bindPopup(entry.html, popupOptions(isDouble))
      }
    } else if (lazy) {
      /* Открытый попап обновляем только если данные метки сменились. */
      if (itemsChanged && entry.marker.isPopupOpen()) {
        entry.marker.setPopupContent(popupContent(items))
      }
    } else {
      const html = popupContent(items)

      if (entry.html !== html) {
        entry.marker.setPopupContent(html)
        entry.html = html
      }
    }
  }

  // Точки, которые больше не проходят фильтр, убираем с карты.
  for (const [key, entry] of markerByKey) {
    if (!nextKeys.has(key)) {
      clusterGroup.removeLayer(entry.marker)
      markerByKey.delete(key)
    }
  }

  mapDebug(
    `Albion map: ${normalized.length} visible / ${constructions.length} filtered`
  )

  mapDebug(
    `Albion map: ${groups.length} physical constructions / ${markerByKey.size} markers`
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
  /*
   * Фильтрация меняет только набор маркеров. Центр и масштаб не трогаем:
   * setView на каждое изменение отменял flyTo к городу и генерировал
   * лишние события move.
   */
  constructions = Array.isArray(items) ? items : []

  selectedMonths = Array.isArray(months) ? months : []

  scheduleRender()
}

function setCenterChangeHandler(handler) {
  centerChangeHandler = typeof handler === 'function' ? handler : null

  if (map && centerChangeHandler) {
    const center = map.getCenter()

    centerChangeHandler({
      lat: center.lat,
      lng: center.lng
    })
  }
}

function getCoordinatesAtScreenPoint(clientX, clientY) {
  if (!map) {
    return null
  }

  const rect = map.getContainer().getBoundingClientRect()

  const x = clientX - rect.left
  const y = clientY - rect.top

  const point = map.containerPointToLatLng([x, y])

  return {
    lat: point.lat,
    lng: point.lng
  }
}

/*
 * Обратное к getCoordinatesAtScreenPoint: координаты → точка на экране
 * (в клиентских пикселях). Нужно, чтобы вернуть перетаскиваемую метку
 * на место зафиксированной точки после сдвига/зума карты.
 */
function getScreenPointAtCoordinates(lat, lng) {
  if (!map) {
    return null
  }

  const latitude = Number(lat)
  const longitude = Number(lng)

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null
  }

  const rect = map.getContainer().getBoundingClientRect()

  const point = map.latLngToContainerPoint([latitude, longitude])

  return {
    x: rect.left + point.x,
    y: rect.top + point.y
  }
}

function setMapDraggingEnabled(enabled) {
  if (!map) {
    return
  }

  if (enabled) {
    map.dragging.enable()
  } else {
    map.dragging.disable()
  }
}

function setSearchPoint(lat, lng) {
  if (!map) {
    return
  }

  const latitude = Number(lat)
  const longitude = Number(lng)

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return
  }

  const position = [latitude, longitude]

  if (!searchPointMarker) {
    searchPointMarker = L.marker(position, {
      /* Тот же пин-домик, что и перетаскиваемая метка: остриё в точке. */
      icon: L.icon({
        iconUrl: searchPointIconHref(),
        iconSize: [SEARCH_POINT_ICON.width, SEARCH_POINT_ICON.height],
        iconAnchor: [SEARCH_POINT_ICON.width / 2, SEARCH_POINT_ICON.height]
      }),

      /*
       * Метка только сообщает о наведении: чип «Убрать точку» рисует
       * страница — одинаково для обоих движков и без подсказок Leaflet,
       * которые закрываются, как только курсор уходит с метки. Клик по
       * метке ничего не делает.
       */
      interactive: true,
      keyboard: false,
      zIndexOffset: 1000
    }).addTo(map)

    searchPointMarker.on('mouseover', () => {
      if (typeof searchPointHoverHandler === 'function') {
        searchPointHoverHandler(true)
      }
    })

    searchPointMarker.on('mouseout', () => {
      if (typeof searchPointHoverHandler === 'function') {
        searchPointHoverHandler(false)
      }
    })

    searchPointMarker.on('click', () => {
      if (typeof searchPointClickHandler === 'function') {
        searchPointClickHandler()
      }
    })
  } else {
    searchPointMarker.setLatLng(position)
  }
}

/* Наведение на метку поиска: колбэк задаёт страница (чип «Убрать точку»). */
function setSearchPointHoverHandler(handler) {
  searchPointHoverHandler = typeof handler === 'function' ? handler : null
}

/*
 * Клик по метке поиска: страница переходит в закладку «Поиск по точке»
 * (там радиус, сброс и правка точки). Метку при этом не убираем.
 */
function setSearchPointClickHandler(handler) {
  searchPointClickHandler = typeof handler === 'function' ? handler : null
}

function clearSearchPoint() {
  if (!searchPointMarker) {
    return
  }

  searchPointMarker.remove()
  searchPointMarker = null
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

  const position = [latitude, longitude]

  if (!searchRadiusCircle) {
    searchRadiusCircle = L.circle(position, {
      radius: distance,
      color: '#e12a1f',
      weight: 2,
      opacity: 0.85,
      fillColor: '#e12a1f',
      fillOpacity: 0.1,
      interactive: false
    }).addTo(map)

    if (searchRadiusCircle.bringToBack) {
      searchRadiusCircle.bringToBack()
    }
  } else {
    searchRadiusCircle.setLatLng(position)
    searchRadiusCircle.setRadius(distance)
  }
}

function clearSearchRadius() {
  if (!searchRadiusCircle) {
    return
  }

  searchRadiusCircle.remove()
  searchRadiusCircle = null
}

function setMapCenter(lat, lng, zoom = 14) {
  if (!map) {
    return
  }

  const latitude = Number(lat)
  const longitude = Number(lng)

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return
  }

  map.flyTo([latitude, longitude], zoom, {
    duration: 0.8
  })
}

function getVisibleConstructions() {
  if (!map) {
    return []
  }

  const bounds = map.getBounds()

  return constructions.filter(item => {
    const lat = Number(item?.lat)
    const lng = Number(item?.lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return false
    }

    return bounds.contains([lat, lng])
  })
}

/* =========================================================
   REGION
   ========================================================= */

/* Внешние кольца области из GeoJSON в формате Leaflet [lat, lng]. */
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

async function loadRegion() {
  const current = map

  if (!current) {
    return
  }

  try {
    const response = await fetch('/rostov-region.geojson')

    if (!response.ok) {
      throw new Error(`GeoJSON error: ${response.status}`)
    }

    const geojson = await response.json()

    // Карту могли уничтожить, пока грузился GeoJSON — тогда map уже null,
    // и обращение к нему бросало бы TypeError.
    if (map !== current) {
      return
    }

    if (regionLayer) {
      current.removeLayer(regionLayer)
      regionLayer = null
    }

    if (maskLayer) {
      current.removeLayer(maskLayer)
      maskLayer = null
    }

    /*
     * Маска: всё ВНЕ Ростовской области затемняем серым.
     * Полигон мира с «дыркой» по области (fillRule: evenodd).
     */
    const rings = geojsonOuterRings(geojson)

    const worldRing = [
      [90, -180],
      [90, 180],
      [-90, 180],
      [-90, -180],
      [90, -180]
    ]

    maskLayer = L.polygon([worldRing, ...rings], {
      stroke: false,
      fill: true,
      fillColor: '#2f383f',
      fillOpacity: 0.82,
      fillRule: 'evenodd',
      interactive: false
    })

    maskLayer.addTo(current)

    if (maskLayer.bringToBack) {
      maskLayer.bringToBack()
    }

    /* Граница области — поверх маски. */
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

    mapDebug('Albion Map: Ростовская область и маска загружены')
  } catch (error) {
    console.error('Albion Map: ошибка загрузки GeoJSON', error)
  }
}

/* =========================================================
   UTILS
   ========================================================= */

function invalidateSize() {
  const current = map

  if (!current) {
    return
  }

  setTimeout(() => {
    /*
     * За время ожидания карту могли уничтожить (уход со страницы) —
     * тогда map уже null, и обращение к нему бросало TypeError.
     */
    if (map === current) {
      current.invalidateSize()
    }
  }, 100)
}

function destroyMap() {
  searchPointHoverHandler = null
  searchPointClickHandler = null

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

  if (regionLayer && map) {
    map.removeLayer(regionLayer)
  }

  regionLayer = null

  if (maskLayer && map) {
    map.removeLayer(maskLayer)
  }

  maskLayer = null

  if (clusterGroup) {
    clusterGroup.clearLayers()
  }

  clusterGroup = null

  markerByKey.clear()

  if (map) {
    map.remove()
  }

  map = null
  centerChangeHandler = null
  constructions = []
  selectedMonths = []
}

function fitToConstructions(items = constructions) {
  if (!map) {
    return
  }

  const normalized = normalizeItems(items)

  if (!normalized.length) {
    return
  }

  const bounds = L.latLngBounds(
    normalized.map(item => [Number(item.lat), Number(item.lng)])
  )

  if (bounds.isValid()) {
    map.fitBounds(bounds, {
      padding: [30, 30],
      maxZoom: 13
    })
  }
}

function focusToItems(items, predicate) {
  if (!map) {
    return
  }

  const source = Array.isArray(items) ? items : []

  const matched = source.filter(item => {
    try {
      return typeof predicate === 'function' ? predicate(item) : true
    } catch {
      return false
    }
  })

  const normalized = normalizeItems(matched)

  if (!normalized.length) {
    return
  }

  const points = normalized.map(item => [Number(item.lat), Number(item.lng)])

  /*
   * Одна точка:
   * плавно переходим непосредственно к конструкции.
   */
  if (points.length === 1) {
    map.flyTo(points[0], 14, {
      duration: 0.8
    })
    return
  }

  /*
   * Несколько конструкций:
   * показываем весь город/район.
   */
  const bounds = L.latLngBounds(points)

  if (bounds.isValid()) {
    map.flyToBounds(bounds, {
      padding: [60, 60],
      maxZoom: 14,
      duration: 0.8
    })
  }
}

/* =========================================================
   EXPORT
   ========================================================= */

export function useMap() {
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
    setSearchPointHoverHandler,
    setSearchPointClickHandler,

    getCoordinatesAtScreenPoint,
    getScreenPointAtCoordinates,
    setMapDraggingEnabled,

    setSearchRadius,
    clearSearchRadius,

    destroyMap
  }
}
