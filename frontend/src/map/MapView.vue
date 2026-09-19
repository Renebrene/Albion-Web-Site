<template>
  <div ref="mapElement" class="map"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'

import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'

import { useMap } from './useMap'

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

const {
  createMap,
  setConstructions,
  loadRegion,
  invalidateSize,
  focusToItems,
  setCenterChangeHandler,
  setMapCenter,
  getCoordinatesAtScreenPoint,
  setMapDraggingEnabled,
  setSearchPoint,
  clearSearchPoint,
  setSearchRadius,
  clearSearchRadius,
  destroyMap
} = useMap()

function syncSearchPoint() {
  const point = props.searchPoint

  const lat = Number(point?.lat)
  const lng = Number(point?.lng)
  const radius = Number(props.searchRadius)

  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lng)
  ) {
    clearSearchPoint()
    clearSearchRadius()
    return
  }

  setSearchPoint(lat, lng)

  if (
    Number.isFinite(radius) &&
    radius > 0
  ) {
    setSearchRadius(lat, lng, radius)
  } else {
    clearSearchRadius()
  }
}

onMounted(async () => {
  createMap(mapElement.value)

  syncSearchPoint()

  setCenterChangeHandler(center => {
    emit('map-center', center)
  })

  setConstructions(props.constructions, props.selectedMonths)

  await loadRegion()

  await nextTick()

  invalidateSize()
})

watch(
  [() => props.constructions, () => props.selectedMonths],
  ([items, months]) => {
    setConstructions(items, months)
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
  focusToItems(
    props.allConstructions,
    item => String(item?.city || '').trim() === String(city || '').trim()
  )
}

function moveToCoordinates(lat, lng, zoom = 14) {
  setMapCenter(lat, lng, zoom)
}

defineExpose({
  focusCity,
  setMapCenter: moveToCoordinates,
  getCoordinatesAtScreenPoint,
  setMapDraggingEnabled
})

onBeforeUnmount(() => {
  setCenterChangeHandler(null)
  destroyMap()
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
