<template>
  <div class="map-shell">
    <div ref="mapElement" class="map"></div>

    <div v-if="initError" class="map-error" role="alert">
      <p>{{ initError }}</p>
      <button type="button" @click="retryInit">Повторить</button>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  shallowRef,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick
} from 'vue'

import { mapEngine } from '../config/mapConfig'
import { availableMode } from '../config/availableMode'
import { showDynCount } from '../config/dynCount'
import { lazyPopups } from '../config/lazyPopups'
import { ensureSiteSettings } from '../boot/settings'
import { loadYandexMaps } from './yandexLoader'

const props = defineProps({
  constructions: {
    type: Array,
    default: () => []
  },

  selectedMonths: {
    type: Array,
    default: () => []
  },

  allConstructions: {
    type: Array,
    default: () => []
  },

  searchPoint: {
    type: Object,
    default: null
  },

  searchRadius: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'select',
  'map-center',
  'search-point-hover',
  'search-point-open'
])

const mapElement = ref(null)

/*
 * Активный движок: объект с тем же публичным API, что у useMap().
 * Выбирается один раз при монтировании.
 */
const mapApi = shallowRef(null)
const activeEngine = ref('')

/* Компонент размонтирован: асинхронная инициализация не должна продолжать
   работу с уже удалённым DOM/картой. */
let disposed = false

/*
 * Готовность карты: движок создан и регион загружен. Нужна, чтобы
 * центровка по городу/району (из ссылки на карточке) выполнялась
 * ПОСЛЕ инициализации карты, а не молча терялась.
 */
const isReady = ref(false)
let readyResolve = null
let readyPromise = createReadyPromise()

/* Текст ошибки инициализации: вместо пустого контейнера показываем
   сообщение и кнопку повторной попытки. */
const initError = ref('')

function createReadyPromise() {
  return new Promise(resolve => {
    readyResolve = resolve
  })
}

function resolveReady() {
  if (readyResolve) {
    readyResolve()
    readyResolve = null
  }
}

function whenReady() {
  return isReady.value ? Promise.resolve() : readyPromise
}

/* CSS Leaflet грузим только если реально используется Leaflet-движок. */
async function loadLeafletCss() {
  await import('leaflet/dist/leaflet.css')
  await import('leaflet.markercluster/dist/MarkerCluster.css')
  await import('leaflet.markercluster/dist/MarkerCluster.Default.css')
}

/*
 * Выбор движка по оператору из админ-настроек ('osm' | 'yandex').
 * Для Yandex сначала догружаем API; при любой ошибке
 * молча откатываемся на Leaflet.
 *
 * Модули движков грузим ДИНАМИЧЕСКИ: тяжелый Leaflet (+ markercluster)
 * не попадает в чанк страницы и подгружается только когда карта реально
 * использует Leaflet-движок.
 */
/* Загрузка API движка (без создания карты). */
async function loadEngineApi(engine) {
  if (engine === 'yandex') {
    await loadYandexMaps()

    const { useYandexMap } = await import('./useYandexMap')

    return useYandexMap()
  }

  await loadLeafletCss()

  const { useMap } = await import('./useMap')

  return useMap()
}

/*
 * Инициализация карты: сначала настроенный движок, при ЛЮБОЙ ошибке
 * (загрузка API или создание карты) — откат на Leaflet. Раньше ошибка
 * createMap() не приводила к фолбэку и карта оставалась пустой.
 */
async function initMap() {
  await ensureSiteSettings()

  if (mapEngine.value === 'yandex') {
    let yandexApi = null

    try {
      yandexApi = await loadEngineApi('yandex')
      yandexApi.createMap(mapElement.value)
      activeEngine.value = 'yandex'

      return yandexApi
    } catch (error) {
      console.warn(
        'Albion map: Yandex Maps недоступны, откат на Leaflet.',
        error
      )

      /*
       * createMap мог успеть создать карту и упасть дальше (кластер,
       * geoObjects): тогда экземпляр и его подписки остаются на элементе.
       */
      try {
        yandexApi?.destroyMap?.()
      } catch {
        /* карта могла не создаться вовсе */
      }
    }
  }

  const api = await loadEngineApi('leaflet')
  api.createMap(mapElement.value)
  activeEngine.value = 'leaflet'
  return api
}

function syncSearchPoint() {
  const api = mapApi.value

  if (!api) {
    return
  }

  const point = props.searchPoint

  const lat = Number(point?.lat)
  const lng = Number(point?.lng)
  const radius = Number(props.searchRadius)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    api.clearSearchPoint()
    api.clearSearchRadius()
    return
  }

  api.setSearchPoint(lat, lng)

  if (Number.isFinite(radius) && radius > 0) {
    api.setSearchRadius(lat, lng, radius)
  } else {
    api.clearSearchRadius()
  }
}

async function initialize() {
  let api

  try {
    api = await initMap()
  } catch (error) {
    console.error('Albion map: не удалось инициализировать карту.', error)

    initError.value =
      'Не удалось загрузить карту. Проверьте соединение и повторите попытку.'

    /*
     * Будим всех, кто ждёт whenReady(): иначе focusCityWhenReady и
     * другие ожидания зависнут навсегда.
     */
    isReady.value = true
    resolveReady()
    return
  }

  // Успели размонтироваться, пока грузился движок — сворачиваемся.
  if (disposed) {
    try {
      api.destroyMap()
    } catch (error) {
      /* карта могла не успеть создаться */
    }
    return
  }

  mapApi.value = api

  /*
   * Метка поиска сообщает наружу: наведение — для чипа «Убрать точку»,
   * клик — переход в закладку «Поиск по точке».
   */
  api.setSearchPointHoverHandler?.(hovered =>
    emit('search-point-hover', hovered)
  )
  api.setSearchPointClickHandler?.(() => emit('search-point-open'))

  syncSearchPoint()

  api.setCenterChangeHandler(center => {
    emit('map-center', center)
  })

  api.setConstructions(props.constructions, props.selectedMonths)

  try {
    await api.loadRegion()
  } catch (error) {
    /* Регион не критичен для центровки по городу — не блокируем готовность. */
    console.warn('Albion map: не удалось загрузить регион.', error)
  }

  if (disposed) {
    return
  }

  await nextTick()

  if (disposed) {
    return
  }

  api.invalidateSize()

  isReady.value = true
  resolveReady()
}

async function retryInit() {
  if (disposed) {
    return
  }

  if (mapApi.value) {
    try {
      mapApi.value.destroyMap()
    } catch (error) {
      /* карта могла быть уже уничтожена */
    }
  }

  mapApi.value = null
  activeEngine.value = ''
  initError.value = ''
  isReady.value = false
  readyPromise = createReadyPromise()

  await initialize()
}

onMounted(async () => {
  disposed = false
  await initialize()
})

watch(
  [
    () => props.constructions,
    () => props.selectedMonths,
    availableMode,
    showDynCount,
    lazyPopups
  ],
  ([items, months]) => {
    mapApi.value?.setConstructions(items, months)
  }
)

watch(
  [() => props.searchPoint, () => props.searchRadius],
  () => {
    syncSearchPoint()
  },
  {
    deep: true
  }
)

function focusCity(city) {
  mapApi.value?.focusToItems(
    props.allConstructions,
    item => String(item?.city || '').trim() === String(city || '').trim()
  )
}

function moveToCoordinates(lat, lng, zoom = 14) {
  mapApi.value?.setMapCenter(lat, lng, zoom)
}

function getCoordinatesAtScreenPoint(clientX, clientY) {
  return mapApi.value?.getCoordinatesAtScreenPoint(clientX, clientY) ?? null
}

function getScreenPointAtCoordinates(lat, lng) {
  return mapApi.value?.getScreenPointAtCoordinates(lat, lng) ?? null
}

function setMapDraggingEnabled(enabled) {
  mapApi.value?.setMapDraggingEnabled(enabled)
}

defineExpose({
  focusCity,
  setMapCenter: moveToCoordinates,
  getCoordinatesAtScreenPoint,
  getScreenPointAtCoordinates,
  setMapDraggingEnabled,
  whenReady,
  retryInit,

  /* Текущий активный движок и ошибка инициализации — для отладки/UI. */
  activeEngine,
  initError
})

onBeforeUnmount(() => {
  disposed = true

  const api = mapApi.value

  if (!api) {
    return
  }

  api.setCenterChangeHandler(null)
  api.destroyMap()
  mapApi.value = null
})
</script>

<style scoped>
.map-shell {
  position: relative;
  width: 100%;
  height: 100%;
}

.map {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.map-error {
  position: absolute;
  inset: 0;
  z-index: 1200;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  gap: 14px;
  padding: 24px;

  background: rgba(233, 237, 239, 0.94);
  color: #17212b;

  text-align: center;
  font-size: 14px;
}

.map-error p {
  margin: 0;
}

.map-error button {
  padding: 8px 16px;

  border: 0;
  border-radius: 9px;

  background: var(--albion-accent);
  color: #fff;

  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}
</style>

<style>
.leaflet-control-attribution a:first-child {
  background-image: none !important;
  padding-left: 0 !important;
}
</style>
