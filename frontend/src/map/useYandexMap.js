/*
 * Движок карты на Yandex Maps JS API 2.1.
 *
 * Публичный API полностью совпадает с Leaflet-версией (useMap.js),
 * чтобы MapView.vue не зависел от конкретного движка.
 *
 * ВАЖНО: перед createMap() нужно дождаться loadYandexMaps()
 * (см. src/map/yandexLoader.js).
 */

import { popupContent, popupLayout } from './popupContent'
import { MONTHS, groupByPoint } from '../utils/constructionGroups'
import { getAvailabilityState } from '../utils/availability'
import { mapDotColors, mapColorMode } from '../config/mapColors'
import { SEARCH_POINT_ICON, searchPointIconHref } from './searchPointIcon'
import { mapDebug } from './mapDebug'

const DEFAULT_CENTER = [47.2357, 39.7015]
const DEFAULT_ZOOM = 10

/* Тайминги анимации перелётов, мс. */
const FLY_DURATION = 400

/*
 * Предельные размеры внешнего кольца маски (градусы).
 *
 * Яндекс.Карты 2.1 не отрисовывают крупные контуры: проверено — кольцо
 * ~126° по долготе рисуется, ~148° уже отбрасывается (и маска
 * инвертируется). Держимся заведомо ниже порога.
 */
const MAX_RING_LNG = 140
const MAX_RING_LAT = 100

let ymaps = null
let map = null
let clusterer = null
let containerElement = null

/* Метки по ключу точки: позволяют переиспользовать их между отрисовками. */
let placemarkByKey = new Map()

let regionOutline = null
let maskPolygon = null

/* Внешние кольца области (для пересборки маски под текущий вид). */
let regionRings = []

/* rAF-троттлинг пересборки маски. */
let maskRefreshFrame = null

let searchPointPlacemark = null

/* Отложенные пересчёт размеров и ограничение зума (см. invalidateSize). */
let invalidateTimer = null
let fitZoomTimer = null

let searchPointHoverHandler = null
let searchPointClickHandler = null
let searchRadiusCircle = null

let centerChangeHandler = null

let constructions = []
let selectedMonths = []

let renderTimer = null
let resizeObserver = null

/* Кадр троттлинга boundschange (см. handleBoundsChange). */
let centerFrame = null

/* Контейнер карты: по его размеру понимаем, видима ли карта (v-show). */
let mapElement = null

/* Центр, отложенный до появления размера у контейнера (см. setMapCenter). */
let pendingCenter = null

/* =========================================================
   HELPERS
   ========================================================= */

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
 *   всё свободно          → зелёный;
 *   всё занято            → красный;
 *   иначе (есть резерв или смесь) → оранжевый.
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

  if (busyCount === 0 && reserveCount === 0) {
    return mapDotColors.value.free
  }

  if (freeCount === 0 && reserveCount === 0) {
    return mapDotColors.value.busy
  }

  return mapDotColors.value.mixed
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

  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
}

/* =========================================================
   MAP
   ========================================================= */

/*
 * boundschange приходит на каждый кадр панорамирования/зума, а страница
 * на нём делает getBoundingClientRect и реактивные записи. Считаем центр
 * не чаще одного раза за кадр.
 */
function handleBoundsChange() {
  if (!map || !centerChangeHandler || centerFrame !== null) {
    return
  }

  centerFrame = requestAnimationFrame(() => {
    centerFrame = null

    if (!map || !centerChangeHandler) {
      return
    }

    const center = map.getCenter()

    centerChangeHandler({
      lat: center[0],
      lng: center[1]
    })
  })
}

function createMap(element) {
  if (!element) {
    throw new Error('Map element not found')
  }

  /* Контейнер запоминаем: по его размеру понимаем, видима ли карта. */
  mapElement = element

  if (map) {
    return map
  }

  if (typeof window === 'undefined' || !window.ymaps || !window.ymaps.Map) {
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

  /* actionend дублировал финальное boundschange — оставляем одно событие. */
  map.events.add('boundschange', handleBoundsChange)

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

/*
 * Ширины балуна подогнаны под разметку попапа
 * (см. CSS [class*='balloon__content'] .popup-double/-triple):
 * одиночный — 300 px, двойной — 540, тройной — 580. Тройному нужен
 * балун шире двойного, иначе третья карточка обрезается (как это было
 * и в Leaflet). На узких экранах не даём балуну выйти за пределы вьюпорта.
 */
function balloonWidths(layout, narrow) {
  if (narrow) {
    return { balloonMaxWidth: 320, balloonMinWidth: 260 }
  }

  if (layout === 'triple') {
    return { balloonMaxWidth: 620, balloonMinWidth: 560 }
  }

  if (layout === 'double') {
    return { balloonMaxWidth: 560, balloonMinWidth: 500 }
  }

  return { balloonMaxWidth: 340, balloonMinWidth: 280 }
}

/* Опции, которые зависят от цвета и раскладки и меняются на лету. */
function applyPlacemarkOptions(entry) {
  entry.placemark.options.set({
    iconImageHref: dotIconHref(entry.color),
    ...balloonWidths(entry.layout, entry.narrow)
  })
}

/*
 * Содержимое балуна — всегда собирается заранее.
 *
 * ВАЖНО: настройка «ленивые попапы» (`map_lazy_popups`) к Яндекс-движку
 * НЕ применяется. Яндекс 2.1 молча не открывает балун, если
 * `balloonContentBody` пустой: клик по метке проходит (событие `click`
 * у метки срабатывает), но балун не появляется. Обходной путь —
 * заглушка и подмена разметки на `balloonopen` — даёт мигание чужого
 * содержимого, а выигрыш уже снят диффом меток: разметка собирается
 * только для новых точек, а не при каждой перерисовке.
 *
 * Функцию в качестве значения Яндекс тоже не поддерживает — рендерит её
 * исходный текст, а не результат вызова.
 */
function syncBalloon(entry) {
  const html = popupContent(entry.items)

  if (entry.html !== html) {
    entry.html = html
    entry.placemark.properties.set('balloonContentBody', html)
  }
}

/*
 * Создаёт метку для группы сторон. Возвращает запись для placemarkByKey.
 * Цвет, раскладка и ширина вьюпорта посчитаны вызывающим — те же значения
 * потом сравниваются при обновлении существующих меток.
 */
/*
 * Состав группы в виде строки: массив items пересобирается на каждой
 * отрисовке, поэтому сравнение по ссылке всегда давало «изменилось»
 * и пересобирало балуны всех меток при любом изменении фильтра.
 */
function itemsKeyOf(items) {
  return items.map(item => String(item?.id ?? '')).join(',')
}

function buildPlacemark({ items, lat, lng, color, layout, narrow }) {
  const first = items[0]

  const placemark = new ymaps.Placemark(
    [lat, lng],
    {
      /* Разметку кладёт syncBalloon() ниже. */
      balloonContentBody: '',

      hintContent: first.address || first.name || 'Рекламная конструкция'
    },
    {
      /*
       * Явно указываем image-раскладку: без неё Яндекс 2.1 (векторный
       * движок) игнорирует iconImageHref и рисует дефолтный «пин»,
       * а не нашу цветную точку.
       */
      iconLayout: 'default#image',
      iconImageHref: dotIconHref(color),
      iconImageSize: [16, 16],
      iconImageOffset: [-8, -8],

      /* Кликабельная область — кружок вокруг центра иконки. */
      iconShape: {
        type: 'Circle',
        coordinates: [0, 0],
        radius: 9
      },

      ...balloonWidths(layout, narrow),

      balloonAutoPan: true,

      hasBalloon: true,
      hasHint: true
    }
  )

  const entry = {
    placemark,
    items,
    /* Состав группы: по нему решаем, нужно ли пересобирать балун. */
    itemsKey: itemsKeyOf(items),
    html: '',
    layout,
    narrow,
    color,
    lat,
    lng
  }

  syncBalloon(entry)

  return entry
}

function renderMarkers() {
  if (!map || !clusterer) {
    return
  }

  const normalized = normalizeItems(constructions)
  const groups = groupByPoint(normalized)

  const nextKeys = new Set()
  const added = []

  for (const group of groups) {
    const items = uniqueSides(group.items)

    if (!items.length) {
      continue
    }

    const lat = Number(items[0].lat)
    const lng = Number(items[0].lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      continue
    }

    const key = group.key

    nextKeys.add(key)

    const color = markerColor(items)
    const layout = popupLayout(items)
    const narrow = typeof window !== 'undefined' && window.innerWidth < 600

    let entry = placemarkByKey.get(key)

    // Новая точка — создаём и добавляем.
    if (!entry) {
      entry = buildPlacemark({ items, lat, lng, color, layout, narrow })

      placemarkByKey.set(key, entry)
      added.push(entry.placemark)

      continue
    }

    /* Сравнение по составу, а не по ссылке (см. itemsKeyOf). */
    const itemsKey = itemsKeyOf(items)
    const itemsChanged = entry.itemsKey !== itemsKey

    entry.itemsKey = itemsKey
    entry.items = items

    // Точка уже на карте — правим только то, что изменилось.
    if (entry.lat !== lat || entry.lng !== lng) {
      entry.lat = lat
      entry.lng = lng
      entry.placemark.geometry.setCoordinates([lat, lng])
    }

    if (
      entry.color !== color ||
      entry.layout !== layout ||
      entry.narrow !== narrow
    ) {
      entry.color = color
      entry.layout = layout
      entry.narrow = narrow
      applyPlacemarkOptions(entry)
    }

    if (itemsChanged) {
      syncBalloon(entry)
    }
  }

  // Точки, которые больше не проходят фильтр, убираем с карты.
  for (const [key, entry] of placemarkByKey) {
    if (!nextKeys.has(key)) {
      clusterer.remove(entry.placemark)
      placemarkByKey.delete(key)
    }
  }

  if (added.length) {
    clusterer.add(added)
  }

  mapDebug(
    `Albion map (Yandex): ${normalized.length} visible / ${constructions.length} filtered`
  )

  mapDebug(
    `Albion map (Yandex): ${groups.length} physical constructions / ${placemarkByKey.size} markers`
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
  constructions = Array.isArray(items) ? items : []

  selectedMonths = Array.isArray(months) ? months : []

  /*
   * В отличие от Leaflet, перерисовка маркеров не сдвигает
   * карту — центр и зум сохраняются сами.
   */
  scheduleRender()
}

function setCenterChangeHandler(handler) {
  centerChangeHandler = typeof handler === 'function' ? handler : null

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
  if (typeof map.convertScreenToGlobalPixel === 'function') {
    globalPoint = map.convertScreenToGlobalPixel([x, y])
  } else if (typeof map.convertScreenToGlobal === 'function') {
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

  const geoPoint = projection.fromGlobalPixels(globalPoint, zoom)

  return {
    lat: geoPoint[0],
    lng: geoPoint[1]
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

  const element =
    containerElement ||
    (map.container && map.container.getElement
      ? map.container.getElement()
      : null)

  if (!element) {
    return null
  }

  const projection = map.options.get('projection')

  if (!projection || !projection.toGlobalPixels) {
    return null
  }

  const rect = element.getBoundingClientRect()

  const globalPoint = projection.toGlobalPixels(
    [latitude, longitude],
    map.getZoom()
  )

  let point = null

  if (typeof map.convertGlobalPixelToScreen === 'function') {
    point = map.convertGlobalPixelToScreen(globalPoint)
  } else if (typeof map.convertGlobalToScreen === 'function') {
    point = map.convertGlobalToScreen(globalPoint)
  } else {
    /* Фоллбэк — от глобального пиксельного центра, как в обратном методе. */
    const center = map.getGlobalPixelCenter()

    point = [
      rect.width / 2 + (globalPoint[0] - center[0]),
      rect.height / 2 + (globalPoint[1] - center[1])
    ]
  }

  if (!point) {
    return null
  }

  return {
    x: rect.left + point[0],
    y: rect.top + point[1]
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

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return
  }

  const position = [latitude, longitude]

  if (!searchPointPlacemark) {
    searchPointPlacemark = new ymaps.Placemark(
      position,
      {},
      {
        /* Тот же пин-домик, что и перетаскиваемая метка: остриё в точке. */
        iconLayout: 'default#image',
        iconImageHref: searchPointIconHref(),
        iconImageSize: [SEARCH_POINT_ICON.width, SEARCH_POINT_ICON.height],
        iconImageOffset: [
          -SEARCH_POINT_ICON.width / 2,
          -SEARCH_POINT_ICON.height
        ],

        /*
         * Метка только сообщает наружу о наведении и клике: чип «Убрать
         * точку» рисует страница, клик переводит в закладку «Поиск по
         * точке». Сама метка ничего не убирает.
         */
        hasBalloon: false,
        hasHint: false
      }
    )

    searchPointPlacemark.events.add('mouseenter', () => {
      if (typeof searchPointHoverHandler === 'function') {
        searchPointHoverHandler(true)
      }
    })

    searchPointPlacemark.events.add('mouseleave', () => {
      if (typeof searchPointHoverHandler === 'function') {
        searchPointHoverHandler(false)
      }
    })

    searchPointPlacemark.events.add('click', () => {
      if (typeof searchPointClickHandler === 'function') {
        searchPointClickHandler()
      }
    })

    map.geoObjects.add(searchPointPlacemark)
  } else {
    searchPointPlacemark.geometry.setCoordinates(position)
  }
}

/* Наведение на метку поиска: колбэк задаёт страница (чип «Убрать точку»). */
function setSearchPointHoverHandler(handler) {
  searchPointHoverHandler = typeof handler === 'function' ? handler : null
}

/*
 * Клик по метке поиска: страница переходит в закладку «Поиск по точке».
 * Метку при этом не убираем.
 */
function setSearchPointClickHandler(handler) {
  searchPointClickHandler = typeof handler === 'function' ? handler : null
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
        fillOpacity: 0.1,
        strokeColor: '#e12a1f',
        strokeOpacity: 0.85,
        strokeWidth: 2,
        interactivityModel: 'default#silent'
      }
    )

    map.geoObjects.add(searchRadiusCircle)
  } else {
    searchRadiusCircle.geometry.setCoordinates(geometry)
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

/* Карта получила размер (вкладка «Карта» видима)? */
function hasMapSize() {
  return Boolean(
    mapElement && mapElement.clientWidth > 0 && mapElement.clientHeight > 0
  )
}

/* Применяет отложенный центр, когда карта стала видимой. */
function applyPendingCenter() {
  if (!pendingCenter || !map || !hasMapSize()) {
    return
  }

  const { lat, lng, zoom } = pendingCenter

  pendingCenter = null

  map.setCenter([lat, lng], zoom, {
    duration: FLY_DURATION
  })
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

  /* Скрытая карта («Список»): центрируем, когда появится размер. */
  if (!hasMapSize()) {
    pendingCenter = { lat: latitude, lng: longitude, zoom }
    invalidateSize()
    return
  }

  pendingCenter = null

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

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return false
    }

    return lat >= minLat && lat <= maxLat && lng >= minLng && lng <= maxLng
  })
}

/* =========================================================
   REGION (маска области + граница)
   ========================================================= */

/*
 * «Внешнее» кольцо маски строим ПО РАЗМЕРУ ТЕКУЩЕГО ВИДА карты.
 *
 * Почему не мировой прямоугольник: векторный движок Яндекс.Карт 2.1 не
 * рисует очень большие контуры (проверено: ~148° по долготе и мировой
 * прямоугольник ±90/±180 отбрасываются, ~126° рисуется). Если внешнее
 * кольцо отброшено, из геометрии [рамка, ...область] остаётся только
 * контур области — и маска получается ИНВЕРТИРОВАННОЙ (тёмная область
 * вместо тёмного фона).
 *
 * Поэтому берём прямоугольник текущего вида с запасом — он всегда мельче
 * порога и всегда перекрывает экран (его края уходят за пределы вида).
 */
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

  /*
   * Жёсткие пределы: контуры крупнее этих размеров Яндекс отбрасывает.
   * Если рамка с запасом вышла больше — сжимаем её до предела, сохраняя
   * центр. На обычных зумах края всё равно за экраном; на самом мелком
   * масштабе возможен незатемнённый кант.
   */
  if (n - s > MAX_RING_LAT) {
    const mc = (s + n) / 2
    s = mc - MAX_RING_LAT / 2
    n = mc + MAX_RING_LAT / 2
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

/* Пересобрать геометрию маски под текущий вид (дешёвая операция). */
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

/* Обновление маски не чаще кадра — boundschange срабатывает часто. */
function scheduleMaskRefresh() {
  if (maskRefreshFrame) {
    return
  }

  maskRefreshFrame = requestAnimationFrame(() => {
    maskRefreshFrame = null
    refreshMaskGeometry()
  })
}

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

  return rings.map(ring => ring.map(([lng, lat]) => [lat, lng]))
}

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

    // Карту могли уничтожить, пока грузился GeoJSON.
    if (map !== current) {
      return
    }

    removeRegionLayers()

    const rings = geojsonOuterRings(geojson)

    regionRings = rings

    const maskRing = viewportMaskRing()

    /*
     * Маска: всё ВНЕ Ростовской области затемняем серым.
     * Прямоугольник текущего вида с «дыркой» по контуру области
     * (fillRule: evenOdd). Внешнее кольцо пересобирается при
     * перемещении/зуме — см. viewportMaskRing() и refreshMaskGeometry().
     */
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

    /* Держим рамку маски по размеру текущего вида. */
    current.events.add('boundschange', scheduleMaskRefresh)

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

    current.geoObjects.add(regionOutline)

    mapDebug('Albion Map (Yandex): Ростовская область и маска загружены')
  } catch (error) {
    console.error('Albion Map (Yandex): ошибка загрузки GeoJSON', error)
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

  /* Один таймер на пачку событий ресайза, снимается в destroyMap. */
  if (invalidateTimer) {
    clearTimeout(invalidateTimer)
  }

  invalidateTimer = setTimeout(() => {
    invalidateTimer = null

    /*
     * Экземпляр захватываем: иначе таймер от уничтоженной карты мог
     * выстрелить уже в новую (после смены движка или retryInit).
     */
    if (map === current && current.container) {
      current.container.fitToViewport()

      /* Размер появился — можно применить отложенный центр. */
      applyPendingCenter()
    }
  }, 100)
}

function destroyMap() {
  searchPointHoverHandler = null
  searchPointClickHandler = null

  mapElement = null
  pendingCenter = null

  if (invalidateTimer) {
    clearTimeout(invalidateTimer)
    invalidateTimer = null
  }

  if (fitZoomTimer) {
    clearTimeout(fitZoomTimer)
    fitZoomTimer = null
  }

  clearSearchPoint()
  clearSearchRadius()

  if (renderTimer) {
    clearTimeout(renderTimer)
    renderTimer = null
  }

  if (centerFrame !== null) {
    cancelAnimationFrame(centerFrame)
    centerFrame = null
  }

  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (map) {
    map.events.remove('boundschange', handleBoundsChange)

    map.events.remove('boundschange', scheduleMaskRefresh)
  }

  if (maskRefreshFrame) {
    cancelAnimationFrame(maskRefreshFrame)
    maskRefreshFrame = null
  }

  regionOutline = null
  maskPolygon = null
  regionRings = []

  if (clusterer) {
    clusterer.removeAll()
  }

  clusterer = null
  placemarkByKey = new Map()

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

  /*
   * setBounds не принимает maxZoom — ограничиваем зум после. Экземпляр
   * захватываем и id помним: если карту успели пересоздать, старое
   * намерение к ней не применяем.
   */
  const target = map

  if (fitZoomTimer) {
    clearTimeout(fitZoomTimer)
  }

  fitZoomTimer = setTimeout(() => {
    fitZoomTimer = null

    if (map !== target || !target) {
      return
    }

    if (target.getZoom() > fitOptions.maxZoom) {
      target.setZoom(fitOptions.maxZoom, {
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

  const points = normalized.map(item => [Number(item.lat), Number(item.lng)])

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
