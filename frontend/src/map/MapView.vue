<template>
  <div ref="mapElement" class="map"></div>
</template>

<script setup>
import { ref, shallowRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

import { MAP_ENGINE } from '../config/mapConfig'
import { useMap } from './useMap'
import { useYandexMap } from './useYandexMap'
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
const activeEngine = ref(MAP_ENGINE)

/* CSS Leaflet грузим только если реально используется Leaflet-движок. */
async function loadLeafletCss() {
  await import('leaflet/dist/leaflet.css')
  await import('leaflet.markercluster/dist/MarkerCluster.css')
  await import('leaflet.markercluster/dist/MarkerCluster.Default.css')
}

/*
 * Выбор движка по флагу MAP_ENGINE.
 * Для Yandex сначала догружаем API; при любой ошибке
 * молча откатываемся на Leaflet.
 */
async function resolveEngine() {
  if (MAP_ENGINE === 'yandex') {
    try {
      await loadYandexMaps()
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

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng)
  ) {
    api.clearSearchPoint()
    api.clearSearchRadius()
    return
  }

  api.setSearchPoint(lat, lng)

  if (
    Number.isFinite(radius) &&
    radius > 0
  ) {
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

  await api.loadRegion()

  await nextTick()

  api.invalidateSize()
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
  return (
    mapApi.value?.getCoordinatesAtScreenPoint(clientX, clientY) ??
    null
  )
}

function setMapDraggingEnabled(enabled) {
  mapApi.value?.setMapDraggingEnabled(enabled)
}

defineExpose({
  focusCity,
  setMapCenter: moveToCoordinates,
  getCoordinatesAtScreenPoint,
  setMapDraggingEnabled,

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
