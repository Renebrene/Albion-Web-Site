<template>
  <div ref="mapElement" class="map"></div>
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

const emit = defineEmits(['select', 'map-center'])

const mapElement = ref(null)

/*
 * Активный движок: объект с тем же публичным API, что у useMap().
 * Выбирается один раз при монтировании.
 */
const mapApi = shallowRef(null)
const activeEngine = ref('')

/*
 * Готовность карты: движок создан и регион загружен. Нужна, чтобы
 * центровка по городу/району (из ссылки на карточке) выполнялась
 * ПОСЛЕ инициализации карты, а не молча терялась.
 */
const isReady = ref(false)
let readyResolve = null
const readyPromise = new Promise(resolve => {
  readyResolve = resolve
})

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
async function resolveEngine() {
  await ensureSiteSettings()

  if (mapEngine.value === 'yandex') {
    try {
      await loadYandexMaps()

      const { useYandexMap } = await import('./useYandexMap')

      activeEngine.value = 'yandex'
      return useYandexMap()
    } catch (error) {
      console.warn(
        'Albion map: Yandex Maps недоступны, откат на Leaflet.',
        error
      )
    }
  }

  activeEngine.value = 'leaflet'
  await loadLeafletCss()

  const { useMap } = await import('./useMap')

  return useMap()
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

onMounted(async () => {
  const api = await resolveEngine()
  mapApi.value = api

  api.createMap(mapElement.value)

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

  await nextTick()

  api.invalidateSize()

  isReady.value = true

  if (readyResolve) {
    readyResolve()
    readyResolve = null
  }
})

watch(
  [() => props.constructions, () => props.selectedMonths],
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

function setMapDraggingEnabled(enabled) {
  mapApi.value?.setMapDraggingEnabled(enabled)
}

defineExpose({
  focusCity,
  setMapCenter: moveToCoordinates,
  getCoordinatesAtScreenPoint,
  setMapDraggingEnabled,
  whenReady,

  /* Текущий активный движок — полезно для отладки/UI. */
  activeEngine
})

onBeforeUnmount(() => {
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
.map {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>

<style>
.leaflet-control-attribution a:first-child {
  background-image: none !important;
  padding-left: 0 !important;
}
</style>
