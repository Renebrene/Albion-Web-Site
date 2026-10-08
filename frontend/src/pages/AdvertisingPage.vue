<template>
  <q-page class="advertising-page">


    <div class="app">

      <FiltersSidebar
        v-if="workspaceMode !== 'point'"
        v-model:selected-months="selectedMonths"
        v-model:month-logic="monthLogic"
        v-model:selected-types="selectedTypes"
        v-model:selected-cities="selectedCities"
        :months="months"
        :types="types"
        :cities="cities"
        @focus-city="focusCity"
      />

      <PointSearchPanel
        v-else
        class="workspace-point-panel"
        :active="true"
        city=""
        district=""
        :count="pointFilteredConstructions.length"
        :radius="pointRadius"
        :available-formats="[]"
        :selected-formats="[]"
        :coordinates="pointCoordinates"
        :address="pointAddress"
        point-label="Центр поиска"
        @update:radius="pointRadius = $event"
        @update:coordinates="pointCoordinates = $event"
        @update:address="pointAddress = $event"
        @search="executePointSearch"
        @search-address="executeAddressSearch"
      />

      <main class="workspace">

        <!-- Плавающий блок: переключатель (слева) + поиск (справа) -->
        <div class="workspace-float">
          <div class="workspace-mode-switch">
            <button
              type="button"
              :class="{ active: workspaceMode === 'map' }"
              @click="workspaceMode = 'map'"
            >
              Интерактивная карта
            </button>
            <button
              type="button"
              :class="{ active: workspaceMode === 'point' }"
              @click="workspaceMode = 'point'"
            >
              Поиск по точке и адресу
            </button>
            <button
              type="button"
              :class="{ active: workspaceMode === 'list' }"
              @click="workspaceMode = 'list'"
            >
              Список
            </button>
          </div>

          <MapSearch
            v-if="workspaceMode !== 'point'"
            v-model="searchQuery"
            :count="filteredConstructions.length"
            @search="onMapSearch"
          />
        </div>

        <!-- КАРТА -->

        <div
          v-if="workspaceMode === 'map'"
          class="map-wrap"
        >
          <MapView
            ref="mapViewRef"
            :constructions="filteredConstructions"
            :all-constructions="constructions"
            :selected-months="selectedMonths"
          />
        </div>

        <!-- ПОИСК ПО ТОЧКЕ И АДРЕСУ -->

        <div
          v-else-if="workspaceMode === 'point'"
          class="map-wrap"
        >
          <MapView
            ref="mapViewRef"
            :constructions="pointFilteredConstructions"
            :all-constructions="constructions"
            :selected-months="selectedMonths"
            :search-point="fixedSearchPoint"
            :search-radius="pointRadius"
            @map-center="updatePointCoordinatesFromMap"
          />



          <div
            v-if="pointSelectionState !== 'fixed'"
            class="point-map-crosshair"
            :class="{
              dragging: isDraggingPointTarget,
              pending: pointSelectionState === 'pending'
            }"
            :style="
              pointTargetPosition.x || pointTargetPosition.y
                ? {
                    left: `${pointTargetPosition.x}px`,
                    top: `${pointTargetPosition.y}px`
                  }
                : {}
            "
            role="button"
            tabindex="0"
            aria-label="Перетащить точку поиска"
            @pointerdown="startPointTargetDrag"
            @pointermove="movePointTarget"
            @pointerup="finishPointTargetDrag"
            @pointercancel="cancelPointTargetDrag"
          >
            <span></span>
          </div>

          <div
            v-if="pointSelectionState === 'pending'"
            class="point-confirmation"
          >
            <div class="point-confirmation-title">
              Зафиксировать эту точку?
            </div>

            <div class="point-confirmation-coordinates">
              {{ pointCoordinates }}
            </div>

            <div class="point-confirmation-actions">
              <button
                type="button"
                class="point-confirm-button"
                @click="fixSelectedPoint"
              >
                ЗАФИКСИРОВАТЬ
              </button>

              <button
                type="button"
                class="point-change-button"
                @click="changeSelectedPoint"
              >
                ИЗМЕНИТЬ
              </button>
            </div>
          </div>

          <div
            v-if="pointSelectionState === 'fixed'"
            class="point-fixed-badge"
          >
            <span>ТОЧКА ЗАФИКСИРОВАНА</span>

            <button
              type="button"
              @click="changeSelectedPoint"
            >
              ИЗМЕНИТЬ ТОЧКУ
            </button>
          </div>
        </div>

        <!-- СПИСОК -->

        <div
          v-else-if="workspaceMode === 'list'"
          class="list-view"
        >
          <div class="list-header">
            <div>
              <div class="list-kicker">
                РЕКЛАМНЫЕ ВОЗМОЖНОСТИ
              </div>

              <h1>
                {{ filteredConstructions.length }}
                конструкций
              </h1>
            </div>
          </div>

          <div
            v-if="listPoints.length"
            class="construction-list"
          >

            <article
              v-for="point in listPoints"
              :key="point.key"
              class="construction-card"
            >

              <div class="card-content">

                <div class="card-address-main">
                  {{ point.address }}
                </div>

                <div class="card-place">
                  {{ point.city }}
                </div>

                <div class="card-blocks">

                  <div
                    v-for="(block, blockIndex) in point.blocks"
                    :key="`${block.type}-${block.parent}-${blockIndex}`"
                    class="card-block"
                    :class="`card-block--${block.kind}`"
                  >

                    <div class="card-topline">

                      <div class="card-type">

                        <strong>
                          {{ blockType(block) }}
                        </strong>

                        <span
                          v-if="blockSize(block)"
                          class="card-size"
                        >
                          {{ blockSize(block) }}
                        </span>

                      </div>

                      <div
                        v-if="hasPrice(blockPrimary(block))"
                        class="card-price-inline"
                      >
                        <span
                          v-if="blockPrimary(block).price"
                          class="price-value"
                          :class="{ 'is-old': promoPriceOf(blockPrimary(block)) }"
                        >
                          {{ blockPrimary(block).price }}
                        </span>

                        <span
                          v-if="blockPrimary(block).price"
                          class="price-currency"
                        >
                          ₽
                        </span>

                        <span
                          v-if="blockPrimary(block).price"
                          class="price-period"
                        >
                          / мес.
                        </span>

                        <div
                          v-if="promoPriceOf(blockPrimary(block))"
                          class="card-promo-price"
                        >
                          <span class="promo-price-value">
                            {{ promoPriceOf(blockPrimary(block)) }}
                          </span>
                          <span class="promo-price-currency">
                            ₽
                          </span>
                          <span class="promo-price-note">
                            акционная цена
                          </span>
                        </div>
                      </div>

                    </div>

                    <div
                      v-if="blockSide(block)"
                      class="card-side-line"
                    >
                      СТОРОНА <b>{{ blockSide(block) }}</b>
                    </div>

                    <div class="card-photo card-photo--block">

                      <img
                        v-if="blockPrimary(block).photo"
                        :src="blockPrimary(block).photo"
                        :alt="point.address"
                        loading="lazy"
                      >

                      <div
                        v-else
                        class="no-photo"
                      >
                        ALBION
                      </div>

                    </div>

                    <!-- Динамика: строки A(1)/A(2)… с месяцами -->
                    <div
                      v-if="block.kind === 'dynamic'"
                      class="card-dynamic-rows"
                    >
                      <div
                        v-for="row in block.items"
                        :key="sideLabel(row)"
                        class="card-dynamic-row"
                      >
                        <span class="card-dynamic-side">
                          {{ sideLabel(row) }}
                        </span>

                        <div class="card-months card-months--inline">

                          <div
                            v-for="month in MONTHS"
                            :key="month.full"
                            class="card-month"
                            :class="getCardMonthState(row, month.full)"
                            :title="getMonthStatusLabel(row, month.full)"
                          >
                            {{ month.short }}
                          </div>

                        </div>
                      </div>
                    </div>

                    <!-- Статика и видеоэкран: одна строка месяцев -->
                    <div
                      v-else
                      class="card-months"
                    >

                      <div
                        v-for="month in MONTHS"
                        :key="month.full"
                        class="card-month"
                        :class="getCardMonthState(blockPrimary(block), month.full)"
                        :title="getMonthStatusLabel(blockPrimary(block), month.full)"
                      >
                        {{ month.short }}
                      </div>

                    </div>

                    <div class="card-features">
                      <span
                        class="card-feature"
                        :title="hasLight(blockPrimary(block)) ? 'Подсветка есть' : 'Без подсветки'"
                      >
                        <span
                          class="feature-picto lightbulb"
                          :class="hasLight(blockPrimary(block)) ? 'on' : 'off'"
                        >💡</span>
                        <span class="feature-label">подсветка</span>
                      </span>

                      <span class="card-feature" title="статика/динамика">
                        <span class="feature-picto feature-placeholder"></span>
                        <span class="feature-label">статика/динамика</span>
                      </span>
                    </div>

                  </div>

                </div>

              </div>

            </article>

          </div>

          <div
            v-else
            class="empty-state"
          >
            <div class="empty-icon">
              0
            </div>

            <h2>
              Ничего не найдено
            </h2>

            <p>
              Измените параметры фильтра или очистите поиск.
            </p>

            <button
              type="button"
              @click="resetFilters"
            >
              Сбросить фильтры
            </button>
          </div>

        </div>

        <div class="map-tools">

          <button
            class="tool"
            title="Сбросить фильтры"
            @click="resetFilters"
          >
            ↺
          </button>

        </div>

      </main>

    </div>

  </q-page>
</template>

<script setup>
import {
  getAvailabilityState,
  getMonthStatusLabel
} from '../utils/availability'
import {
  MONTHS,
  sideLabel,
  parentSide,
  dedupeSides,
  familyOf,
  maxBlocksFor,
  groupSides,
  groupByPoint
} from '../utils/constructionGroups'
import { computed, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FiltersSidebar from '../components/filters/FiltersSidebar.vue'
import MapSearch from '../components/workspace/MapSearch.vue'
import PointSearchPanel from '../components/workspace/PointSearchPanel.vue'
import MapView from '../map/MapView.vue'

import { getConstructions } from '../services/api'

import {
  useConstructionsFilter
} from '../composables/useConstructionsFilter'


/* Акционная цена из отдельной колонки 1С (пока в данных отсутствует). */
function promoPriceOf(item) {
  return String(
    item?.promoPrice ??
    item?.promo_price ??
    ''
  ).trim()
}

function getCardMonthState(item, month) {
  return getAvailabilityState(item, month)
}

/* Первая (ведущая) сторона блока — как и в попапе карты. */
function blockPrimary(block) {
  return block?.items?.[0] || {}
}

function blockType(block) {
  return String(blockPrimary(block).type || 'Конструкция').trim()
}

function blockSize(block) {
  return String(blockPrimary(block).size || '').trim()
}

/* Подпись стороны блока: динамика — родительская сторона, иначе своя. */
function blockSide(block) {
  const side = sideLabel(blockPrimary(block))
  return block.kind === 'dynamic' ? parentSide(side) : side
}

function hasPrice(item) {
  return Boolean(item?.price || promoPriceOf(item))
}

function hasLight(item) {
  return [
    'да',
    'yes',
    'true',
    '1'
  ].includes(String(item?.light || '').trim().toLowerCase())
}

const route = useRoute()
const router = useRouter()
const constructions = ref([])
const mapViewRef = ref(null)
const pointSearchOpen = ref(false)

function focusCity(city) {
  mapViewRef.value?.focusCity(city)
}

const workspaceMode = ref('map')

function onMapSearch() {
  // Фильтр по searchQuery реактивный (v-model в MapSearch).
  // Enter/иконка подтверждают запрос — при необходимости можно
  // дополнительно сфокусировать карту на результатах.
}

const pointCoordinates = ref('47.2357, 39.7015')
const pointAddress = ref('')
const pointRadius = ref(3000)

// Точка, подтверждённая пользователем.
// После фиксации не зависит от перемещения или масштаба карты.
const fixedSearchPoint = ref(null)

// Состояние выбора точки:
// idle    — мишень свободна и готова к перемещению
// pending — пользователь отпустил мишень, ждём подтверждения
// fixed   — точка зафиксирована
const pointSelectionState = ref('idle')
const pointTargetPosition = ref({ x: 0, y: 0 })
const isDraggingPointTarget = ref(false)
const pointTargetPointerOffset = ref({ x: 0, y: 0 })

function updatePointCoordinatesFromMap(center) {
  if (workspaceMode.value !== 'point') {
    return
  }

  const lat = Number(center?.lat)
  const lng = Number(center?.lng)

  if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
    return
  }

  pointCoordinates.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`
}

function startPointTargetDrag(event) {
  if (
    workspaceMode.value !== 'point' ||
    pointSelectionState.value === 'fixed'
  ) {
    return
  }

  const target = event.currentTarget
  const mapWrap = target.parentElement

  if (!mapWrap) {
    return
  }

  const targetRect = target.getBoundingClientRect()

  pointTargetPointerOffset.value = {
    x: event.clientX - (targetRect.left + targetRect.width / 2),
    y: event.clientY - (targetRect.top + targetRect.height / 2)
  }

  isDraggingPointTarget.value = true

  mapViewRef.value?.setMapDraggingEnabled(false)

  target.setPointerCapture?.(event.pointerId)

  event.preventDefault()
  event.stopPropagation()
}

function movePointTarget(event) {
  if (!isDraggingPointTarget.value) {
    return
  }

  const target = event.currentTarget
  const mapWrap = target.parentElement

  if (!mapWrap) {
    return
  }

  const rect = mapWrap.getBoundingClientRect()

  const x = Math.max(
    0,
    Math.min(
      rect.width,
      event.clientX - rect.left - pointTargetPointerOffset.value.x
    )
  )

  const y = Math.max(
    0,
    Math.min(
      rect.height,
      event.clientY - rect.top - pointTargetPointerOffset.value.y
    )
  )

  pointTargetPosition.value = {
    x,
    y
  }

  const coordinates =
    mapViewRef.value?.getCoordinatesAtScreenPoint(
      event.clientX,
      event.clientY
    )

  if (!coordinates) {
    return
  }

  pointCoordinates.value =
    `${coordinates.lat.toFixed(6)}, ${coordinates.lng.toFixed(6)}`
}

function finishPointTargetDrag(event) {
  if (!isDraggingPointTarget.value) {
    return
  }

  movePointTarget(event)

  isDraggingPointTarget.value = false

  mapViewRef.value?.setMapDraggingEnabled(true)

  targetReleasePoint()

  event.preventDefault()
  event.stopPropagation()
}

function cancelPointTargetDrag(event) {
  if (!isDraggingPointTarget.value) {
    return
  }

  isDraggingPointTarget.value = false

  mapViewRef.value?.setMapDraggingEnabled(true)

  event.preventDefault()
  event.stopPropagation()
}

function targetReleasePoint() {
  pointSelectionState.value = 'pending'
}

function fixSelectedPoint() {
  const parts = String(pointCoordinates.value || '')
    .split(',')
    .map(value => Number(value.trim()))

  if (
    parts.length !== 2 ||
    !Number.isFinite(parts[0]) ||
    !Number.isFinite(parts[1])
  ) {
    return
  }

  fixedSearchPoint.value = {
    lat: parts[0],
    lng: parts[1]
  }

  pointSelectionState.value = 'fixed'
}

function changeSelectedPoint() {
  fixedSearchPoint.value = null
  pointSelectionState.value = 'idle'
}

function distanceInMeters(lat1, lng1, lat2, lng2) {
  const earthRadius = 6371000

  const toRadians = value => value * Math.PI / 180

  const dLat = toRadians(lat2 - lat1)
  const dLng = toRadians(lng2 - lng1)

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) *
    Math.cos(toRadians(lat2)) *
    Math.sin(dLng / 2) ** 2

  return 2 * earthRadius * Math.atan2(
    Math.sqrt(a),
    Math.sqrt(1 - a)
  )
}

const pointFilteredConstructions = computed(() => {
  if (workspaceMode.value !== 'point') {
    return filteredConstructions.value
  }

  const centerLat = Number(fixedSearchPoint.value?.lat)
  const centerLng = Number(fixedSearchPoint.value?.lng)
  const radius = Number(pointRadius.value) || 0

  if (
    !Number.isFinite(centerLat) ||
    !Number.isFinite(centerLng) ||
    radius <= 0
  ) {
    return []
  }

  return filteredConstructions.value.filter(item => {
    const lat = Number(item?.lat)
    const lng = Number(item?.lng)

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lng)
    ) {
      return false
    }

    return distanceInMeters(
      centerLat,
      centerLng,
      lat,
      lng
    ) <= radius
  })
})


function executePointSearch() {
  const parts = String(pointCoordinates.value || '')
    .split(',')
    .map(value => Number(value.trim()))

  if (
    parts.length !== 2 ||
    !Number.isFinite(parts[0]) ||
    !Number.isFinite(parts[1])
  ) {
    console.warn('Albion point search: некорректные координаты')
    return
  }

  const [lat, lng] = parts

  if (
    lat < -90 ||
    lat > 90 ||
    lng < -180 ||
    lng > 180
  ) {
    console.warn('Albion point search: координаты вне допустимого диапазона')
    return
  }

  pointCoordinates.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`

  fixedSearchPoint.value = {
    lat,
    lng
  }

  mapViewRef.value?.setMapCenter(lat, lng, 14)
}

function executeAddressSearch() {
  const address = String(pointAddress.value || '').trim()

  if (!address) {
    return
  }

  console.log(
    'Albion address search:',
    address
  )
}

const {
  months,
  types,
  cities,

  selectedMonths,
  monthLogic,
  selectedTypes,
  selectedCities,

  searchQuery,

  filteredConstructions,

  resetFilters
} = useConstructionsFilter(constructions)

/*
 * Список: одна карточка на точку/адрес, внутри — блоки по формату
 * стороны (те же правила, что и в попапе интерактивной карты).
 */
const listPoints = computed(() =>
  groupByPoint(filteredConstructions.value).map(point => {
    const deduped = dedupeSides(point.items)
    const blocks = groupSides(deduped)
      .slice(0, maxBlocksFor(familyOf(deduped)))

    const first = point.items[0] || {}

    return {
      key: point.key,
      address: String(first.address || first.name || 'Адрес не указан').trim(),
      city: String(first.city || '').trim() || '—',
      blocks
    }
  })
)

/*
 * Синхронизация города из URL с фильтром.
 *
 * useConstructionsFilter сначала выбирает все города
 * после загрузки данных. Поэтому город из URL применяем
 * после того, как список cities уже сформирован.
 */


watch(
  [cities, types],
  ([cityValues, typeValues]) => {
    const cityFromUrl = String(route.query.city || '').trim()
    const typeFromUrl = String(route.query.type || '').trim()
    const addressFromUrl = String(route.query.address || '').trim()

    if (cityFromUrl && cityValues.length) {
      const actualCity = cityValues.find(
        city => city === cityFromUrl
      )

      if (actualCity) {
        selectedCities.value = [actualCity]
      }
    }

    if (typeFromUrl && typeValues.length) {
      const actualType = typeValues.find(
        type => type === typeFromUrl
      )

      if (actualType) {
        selectedTypes.value = [actualType]
      }
    }

    if (addressFromUrl) {
      searchQuery.value = addressFromUrl
    }
  },
  { immediate: true }
)

watch(
  selectedCities,
  values => {
    if (values.length !== 1) {
      return
    }

    const cityFromUrl = String(route.query.city || '').trim()

    if (values[0] !== cityFromUrl) {
      return
    }

    requestAnimationFrame(() => {
      mapViewRef.value?.focusCity(values[0])
    })
  },
  { flush: 'post' }
)

watch(
  [cities, types],
  ([cityValues, typeValues]) => {
    const cityFromUrl = String(route.query.city || '').trim()
    const typeFromUrl = String(route.query.type || '').trim()
    const addressFromUrl = String(route.query.address || '').trim()

    if (cityFromUrl && cityValues.length) {
      const actualCity = cityValues.find(
        city => city === cityFromUrl
      )

      if (actualCity) {
        selectedCities.value = [actualCity]
      }
    }

    if (typeFromUrl && typeValues.length) {
      const actualType = typeValues.find(
        type => type === typeFromUrl
      )

      if (actualType) {
        selectedTypes.value = [actualType]
      }
    }

    if (addressFromUrl) {
      searchQuery.value = addressFromUrl
    }
  },
  { immediate: true }
)

watch(
  selectedCities,
  values => {
    if (values.length !== 1) {
      return
    }

    const cityFromUrl = String(route.query.city || '').trim()

    if (values[0] !== cityFromUrl) {
      return
    }

    requestAnimationFrame(() => {
      mapViewRef.value?.focusCity(values[0])
    })
  },
  { flush: 'post' }
)


// URL ← фильтры
watch(
  [selectedCities, selectedTypes, searchQuery],
  ([cityValues, typeValues, addressValue]) => {
    const query = {}

    if (cityValues.length === 1) {
      query.city = cityValues[0]
    }

    if (typeValues.length === 1) {
      query.type = typeValues[0]
    }

    const address = String(addressValue || '').trim()

    if (address) {
      query.address = address
    }

    const currentQuery = {
      city: route.query.city,
      type: route.query.type,
      address: route.query.address
    }

    const nextQuery = {
      city: query.city,
      type: query.type,
      address: query.address
    }

    if (
      currentQuery.city === nextQuery.city &&
      currentQuery.type === nextQuery.type &&
      currentQuery.address === nextQuery.address
    ) {
      return
    }

    router.replace({
      path: '/vozmozhnosti',
      query
    })
  },
  { deep: true }
)
// Конец URL ← фильтры

onMounted(async () => {
  try {
    const data = await getConstructions()
    constructions.value = Array.isArray(data) ? data : []

    console.log(
      'Albion page: загружено',
      constructions.value.length
    )
  } catch (error) {
    console.error(
      'Albion page: ошибка загрузки конструкций:',
      error
    )
  }
})
</script>

<style scoped>
.advertising-page {
  height: 100%;
  overflow: hidden;
  background: #f3f5f6;
}

.app {
  height: calc(100vh - 115px);

  display: grid;
  grid-template-columns: 310px 1fr;

  overflow: hidden;
}

.workspace {
  position: relative;
  min-width: 0;

  background: #e9edef;
}

/* Переключатель режимов */

.workspace-float {
  position: absolute;
  top: 18px;
  left: 18px;
  z-index: 1500;

  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;

  max-width: calc(100% - 36px);
}

.workspace-mode-switch {
  display: flex;
  align-items: center;
  gap: 3px;

  padding: 5px;

  flex-shrink: 0;

  background: rgba(255, 255, 255, .96);
  border: 1px solid #e1e6e9;
  border-radius: 13px;

  box-shadow: 0 8px 28px rgba(23, 33, 43, .14);
  backdrop-filter: blur(12px);
}

.workspace-mode-switch button {
  height: 34px;
  padding: 0 14px;
  white-space: nowrap;

  border: 0;
  border-radius: 9px;

  background: transparent;
  color: #71808c;

  font-size: 11px;
  font-weight: 800;
  letter-spacing: .02em;

  cursor: pointer;

  transition:
    background .18s ease,
    color .18s ease;
}

.workspace-mode-switch button.active {
  background: #17212b;
  color: #fff;
}

.workspace-mode-switch button:hover:not(.active) {
  background: #f0f3f4;
  color: #17212b;
}



.map-wrap {
  position: absolute;
  inset: 0;
}

.list-view {
  position: absolute;
  inset: 0;

  overflow-y: auto;

  padding: 122px 28px 40px;

  background: #f4f6f7;
}

.list-header {
  margin-bottom: 22px;
}

.list-kicker {
  color: #e12a1f;

  font-size: 10px;
  font-weight: 800;

  letter-spacing: 1.4px;
}

.list-header h1 {
  margin: 5px 0 0;

  color: #17212b;

  font-size: 28px;
  line-height: 1.1;
}

.construction-list {
  display: grid;

  grid-template-columns:
    repeat(
      auto-fill,
      minmax(300px, 1fr)
    );

  gap: 18px;
}

.construction-card {
  overflow: hidden;

  display: flex;
  flex-direction: column;

  height: 100%;

  background: #fff;

  border: 1px solid #e5e9eb;

  border-radius: 18px;

  box-shadow:
    0 8px 30px rgba(25,35,45,.06);

  transition:
    transform .15s ease,
    box-shadow .15s ease;
}

.construction-card:hover {
  transform: translateY(-2px);

  box-shadow:
    0 14px 40px rgba(25,35,45,.1);
}

.card-photo {
  position: relative;

  aspect-ratio: 16 / 9;

  overflow: hidden;

  background: #e9edef;
}

.card-photo img {
  width: 100%;
  height: 100%;

  object-fit: cover;

  display: block;
}

.no-photo {
  height: 100%;

  display: flex;
  align-items: center;
  justify-content: center;

  color: #b5bec4;

  font-size: 24px;
  font-weight: 900;
  letter-spacing: 2px;
}

.card-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  margin-bottom: 10px;

  min-width: 0;
}

.card-type {
  position: static;

  flex: 1 1 auto;
  min-width: 0;

  padding: 0;

  background: transparent;

  color: #17212b;

  font-size: 12px;
  line-height: 1.1;

  font-weight: 900;

  text-transform: uppercase;
  letter-spacing: .25px;
}

/* формат жирный, размер обычным — в одну строку */
.card-size {
  margin-left: 6px;
  font-weight: 500;
  letter-spacing: 0;
  color: #52606a;
}

.card-price-inline {
  flex: 0 0 auto;

  display: flex;
  flex-wrap: wrap;
  align-items: baseline;

  gap: 4px;

  white-space: nowrap;
}

.card-price-inline .price-value {
  color: #17212b;

  font-size: 20px;
  line-height: 1;

  font-weight: 900;

  letter-spacing: -.5px;
}

/* основная цена бледная и зачёркнутая при наличии акционной */
.card-price-inline .price-value.is-old {
  color: #9aa5ac;
  text-decoration: line-through;
  font-weight: 700;
  letter-spacing: 0;
}

.card-price-inline .price-currency {
  color: #17212b;

  font-size: 13px;
  line-height: 1;

  font-weight: 900;
}

.card-price-inline .price-period {
  color: #71808c;

  font-size: 9px;
  line-height: 1;

  font-weight: 700;
}

.card-promo-price {
  display: flex;
  flex-basis: 100%;
  align-items: baseline;
  gap: 3px;
}

.card-promo-price .promo-price-value {
  color: #e12a1f;
  font-size: 20px;
  line-height: 1;
  font-weight: 950;
}

.card-promo-price .promo-price-currency {
  color: #e12a1f;
  font-weight: 900;
}

.card-promo-price .promo-price-note {
  color: #8a959c;
  font-size: 9px;
  font-weight: 600;
}

.card-content {
  flex: 1;

  display: flex;
  flex-direction: column;

  padding: 14px 16px 15px;
}
.card-content h2 {
  margin: 0 0 3px;

  color: #17212b;

  font-size: 17px;
  line-height: 1.15;
}

.card-address-main {
  min-height: 0;

  color: #17212b;

  font-size: 17px;
  line-height: 1.15;

  margin-bottom: 3px;
}

.card-address {
  min-height: 0;

  color: #65727b;

  font-size: 12px;
  line-height: 1.3;
}

.card-place {
  min-height: 0;

  color: #65727b;

  font-size: 12px;
  line-height: 1.3;
}

.card-side-line {
  margin-top: 2px;

  color: #8a959c;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
}

.card-side-line b {
  color: #52606a;
  font-weight: 900;
}

/* Блоки внутри карточки точки — по одному на формат стороны */

.card-blocks {
  display: flex;
  flex-direction: column;
  gap: 14px;

  margin-top: 10px;
}

.card-block {
  padding-top: 12px;

  border-top: 1px solid #edf0f2;
}

.card-block:first-child {
  padding-top: 0;

  border-top: 0;
}

.card-block .card-side-line {
  margin-top: 6px;
}

.card-photo--block {
  aspect-ratio: 16 / 10;

  margin-top: 8px;

  border-radius: 12px;
}

.card-block .card-months {
  margin-top: 10px;
  padding-top: 9px;
}

/* Месяцы в строке динамической стороны — без верхней границы */
.card-months--inline {
  flex: 1;

  margin-top: 0;
  padding-top: 0;

  border-top: 0;
}

.card-months--inline .card-month {
  width: 30px;
  height: 20px;

  font-size: 7px;
}

.card-dynamic-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;

  margin-top: 10px;
  padding-top: 9px;

  border-top: 1px solid #edf0f2;
}

.card-dynamic-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-dynamic-side {
  flex: 0 0 auto;

  min-width: 34px;

  color: #17212b;

  font-size: 10px;
  font-weight: 900;
  letter-spacing: .04em;
}

/* месяцы и прочее прижаты к нижнему краю — единое выравнивание */
.card-months {
  margin-top: auto;
  padding-top: 9px;
}

.card-meta {
  display: flex;
  gap: 20px;

  margin-top: 9px;

  padding-top: 8px;

  border-top: 1px solid #edf0f2;
}

.card-meta div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.card-meta span {
  color: #8a959c;

  font-size: 9px;
  text-transform: uppercase;
}

.card-meta strong {
  color: #34414a;

  font-size: 11px;
  font-weight: 800;
}

.card-price {
  margin-top: 16px;
  padding: 15px 17px 14px;

  border-radius: 11px;

  background: #f1f3f4;

  color: #17212b;
}

.card-price .price-label {
  display: block;

  margin-bottom: 5px;

  color: #8a959c;

  font-size: 9px;
  line-height: 1;

  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .8px;
}

.card-price .price-main {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.card-price .price-value {
  color: #17212b;

  font-size: 32px;
  line-height: .95;

  font-weight: 950;
  letter-spacing: -1.2px;
}

.card-price .price-currency {
  color: #17212b;

  font-size: 19px;
  line-height: 1;

  font-weight: 900;
}

.card-price .price-period {
  display: block;

  margin-top: 5px;

  color: #71808c;

  font-size: 10px;
  line-height: 1;

  font-weight: 700;
}

.card-meta .size-value {
  color: #34414a;
  font-weight: 600;
}

.empty-state {
  min-height: 50vh;

  display: flex;
  align-items: center;
  justify-content: center;

  flex-direction: column;

  text-align: center;
}

.empty-icon {
  width: 54px;
  height: 54px;

  display: grid;
  place-items: center;

  border-radius: 16px;

  background: #e9edef;

  color: #71808c;

  font-weight: 800;
}

.empty-state h2 {
  margin: 14px 0 5px;

  color: #17212b;

  font-size: 20px;
}

.empty-state p {
  margin: 0 0 18px;

  color: #71808c;

  font-size: 12px;
}

.empty-state button {
  padding: 10px 16px;

  border: 0;

  border-radius: 9px;

  background: #e12a1f;

  color: #fff;

  cursor: pointer;

  font-size: 11px;
  font-weight: 800;
}

.map-tools {
  position: absolute;

  z-index: 600;

  right: 24px;
  bottom: 24px;
}

.tool {
  width: 42px;
  height: 42px;

  border: 0;

  border-radius: 13px;

  background: #fff;

  cursor: pointer;

  font-size: 20px;

  box-shadow:
    0 10px 30px rgba(25,35,45,.14);
}

@media (max-width: 760px) {
  .app {
    grid-template-columns: 1fr;
  }

  .list-view {
    padding: 30px 16px;
  }

  .construction-list {
    grid-template-columns: 1fr;
  }
}

.point-search-trigger {
  position: absolute;
  top: 18px;
  right: 18px;
  z-index: 1200;

  display: inline-flex;
  align-items: center;
  gap: 9px;

  height: 44px;
  padding: 0 17px;

  border: 0;
  border-radius: 12px;

  background: #17212b;
  color: #ffffff;

  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;

  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);

  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    background 0.18s ease;
}

.point-search-trigger:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.22);
}

.point-search-trigger:active {
  transform: translateY(0);
}

.point-search-trigger-icon {
  font-size: 19px;
  line-height: 1;
}



.point-map-crosshair {
  position: absolute;

  left: 50%;
  top: 50%;

  width: 38px;
  height: 38px;

  transform: translate(-50%, -50%);

  z-index: 900;

  cursor: grab;
  touch-action: none;
  user-select: none;
}

.point-map-crosshair.dragging {
  cursor: grabbing;
  transform: translate(-50%, -50%) scale(1.08);
}

.point-map-crosshair.pending {
  cursor: default;
}

.point-confirmation {
  position: absolute;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  z-index: 950;

  min-width: 290px;
  padding: 16px 18px;

  background: rgba(255, 255, 255, .97);
  border: 1px solid #dfe4e7;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(23, 33, 43, .18);

  text-align: center;
}

.point-confirmation-title {
  font-size: 14px;
  font-weight: 700;
  color: #17212b;
}

.point-confirmation-coordinates {
  margin-top: 5px;
  font-size: 12px;
  color: #6b747c;
  font-variant-numeric: tabular-nums;
}

.point-confirmation-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.point-confirm-button,
.point-change-button {
  flex: 1;
  min-height: 36px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
}

.point-confirm-button {
  border: 0;
  background: #17212b;
  color: #fff;
}

.point-change-button {
  border: 1px solid #d5dade;
  background: #fff;
  color: #17212b;
}

.point-fixed-badge {
  position: absolute;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  z-index: 950;

  display: flex;
  align-items: center;
  gap: 12px;

  padding: 8px 10px 8px 14px;

  background: rgba(255, 255, 255, .96);
  border: 1px solid #dfe4e7;
  border-radius: 7px;
  box-shadow: 0 6px 20px rgba(23, 33, 43, .14);

  font-size: 11px;
  font-weight: 700;
  color: #17212b;
}

.point-fixed-badge button {
  border: 0;
  border-radius: 5px;
  padding: 7px 10px;

  background: #17212b;
  color: #fff;

  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
}

.point-map-crosshair::before,
.point-map-crosshair::after,
.point-map-crosshair span::before,
.point-map-crosshair span::after {
  content: '';

  position: absolute;

  background: #17212b;

  opacity: .75;

  border-radius: 2px;
}

.point-map-crosshair::before {
  left: 18px;
  top: 0;

  width: 2px;
  height: 11px;
}

.point-map-crosshair::after {
  left: 18px;
  bottom: 0;

  width: 2px;
  height: 11px;
}

.point-map-crosshair span::before {
  left: 0;
  top: 18px;

  width: 11px;
  height: 2px;
}

.point-map-crosshair span::after {
  right: 0;
  top: 18px;

  width: 11px;
  height: 2px;
}

.point-map-crosshair span {
  position: absolute;

  left: 50%;
  top: 50%;

  width: 7px;
  height: 7px;

  transform: translate(-50%, -50%);

  border: 2px solid #17212b;
  border-radius: 50%;

  background: rgba(255,255,255,.9);
}

</style>

<style>
/* Сжательная планка зума Leaflet — слева внизу карты. */
.workspace .leaflet-top.leaflet-left,
.map-wrap .leaflet-top.leaflet-left {
  top: auto;
  bottom: 18px;
  left: 18px;
}
</style>
