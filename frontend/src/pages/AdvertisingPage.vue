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
        v-model:selected-months="selectedMonths"
        v-model:month-logic="monthLogic"
        v-model:selected-types="selectedTypes"
        :months="months"
        :types="types"
        :count="pointFilteredConstructions.length"
        :results="pointFilteredConstructions"
        :coordinates="pointCoordinates"
        :address="pointAddress"
        @update:coordinates="pointCoordinates = $event"
        @update:address="pointAddress = $event"
        @search="executePointSearch"
        @search-address="executeAddressSearch"
        @open-list="openListFromPoint"
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
            v-model="topSearchValue"
            :count="displayedConstructions.length"
            :show-mode="workspaceMode === 'point'"
            :mode="topSearchMode"
            @update:mode="topSearchMode = $event"
            @search="onTopSearch"
          />
        </div>

        <!-- КАРТА -->

        <div
          v-if="workspaceMode === 'map'"
          class="map-wrap"
        >
          <MapView
            ref="mapViewRef"
            :constructions="displayedConstructions"
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

          <!-- Плавающий слайдер радиуса — под плашкой точки -->
          <div class="point-radius-float">
            <div class="point-radius-head">
              <span>РАДИУС ПОИСКА</span>
              <strong>{{ formatRadius(pointRadius) }}</strong>
            </div>

            <input
              class="point-radius-range"
              type="range"
              :min="0"
              :max="RADIUS_STEPS.length - 1"
              step="1"
              :value="pointRadiusIndex"
              @input="onPointRadiusInput"
            >

            <div class="point-radius-marks">
              <span
                v-for="(value, index) in RADIUS_STEPS"
                :key="value"
                :class="{ active: index === pointRadiusIndex }"
              >
                {{ formatRadius(value) }}
              </span>
            </div>
          </div>
        </div>

        <!-- СПИСОК -->

        <div
          v-else-if="workspaceMode === 'list'"
          ref="listViewRef"
          class="list-view"
        >
          <!--
            Виртуальный скролл строками: в DOM рендерятся только видимые
            строки сетки (плюс буфер), а не весь список целиком.
          -->
          <q-virtual-scroll
            v-if="listPoints.length"
            class="construction-list"
            :items="listRows"
            :virtual-scroll-item-size="820"
          >
            <!-- Шапка списка — слот «before» q-virtual-scroll: прокручивается
                 вместе с карточками, и её высота учитывается в расчёте. -->
            <template #before>
              <div class="list-header">
                <div>
                  <div class="list-kicker">
                    РЕКЛАМНЫЕ ВОЗМОЖНОСТИ
                  </div>

                  <h1>
                    {{ displayedConstructions.length }}
                    конструкций
                  </h1>
                </div>
              </div>
            </template>

            <template #default="{ item: row }">

            <!-- Строка сетки: columns колонок, повторяет прежний auto-fill. -->
            <div
              :key="row.key"
              class="construction-row"
              :style="{ gridTemplateColumns: `repeat(${listColumns}, 1fr)` }"
            >

            <article
              v-for="point in row.items"
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
                    :class="[
                      `card-block--${block.kind}`,
                      { 'pf-mode': isBlockActive(block) }
                    ]"
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
                        v-if="photoCard(blockPrimary(block))"
                        :src="photoThumb(blockPrimary(block))"
                        :srcset="photoSrcset(blockPrimary(block))"
                        sizes="(max-width: 760px) 100vw, (max-width: 1200px) 70vw, 900px"
                        :alt="point.address"
                        loading="lazy"
                        decoding="async"
                        width="1000"
                        height="625"
                        class="card-photo-clickable"
                        title="Открыть фото"
                        @click.stop="openBlockPhoto(point, block)"
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
                            :class="[
                              getCardMonthState(row, month.full),
                              { 'is-selected': surfaceIdOf(row) !== null && isMonthSelected(row.id, month.full) }
                            ]"
                            :title="getMonthStatusLabel(row, month.full)"
                            @click="onCardMonthClick(block, row, month)"
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
                        :class="[
                          getCardMonthState(blockPrimary(block), month.full),
                          { 'is-selected': surfaceIdOf(blockPrimary(block)) !== null && isMonthSelected(blockPrimary(block).id, month.full) }
                        ]"
                        :title="getMonthStatusLabel(blockPrimary(block), month.full)"
                        @click="onCardMonthClick(block, blockPrimary(block), month)"
                      >
                        {{ month.short }}
                      </div>

                    </div>

                    <!-- Портфель: кнопка (два состояния) + кликабельные месяцы -->
                    <div class="card-portfolio">
                      <button
                        type="button"
                        class="card-pf-toggle"
                        :class="{ 'is-active': isBlockActive(block) }"
                        :title="isBlockActive(block)
                          ? 'Убрать из портфеля'
                          : 'Добавить в портфель'"
                        @click="toggleBlockPfMode(block)"
                      >
                        <q-icon name="work_outline" size="16px" />
                        <span>Портфель</span>
                      </button>
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
                        <span class="feature-dyn">
                          <span
                            class="dyn-word"
                            :class="{ 'is-active': block.kind === 'static' }"
                          >статика</span>

                          <span class="dyn-sep">/</span>

                          <span
                            class="dyn-word"
                            :class="{ 'is-active': block.kind !== 'static' }"
                          >динамика</span>
                        </span>
                      </span>
                    </div>

                  </div>

                </div>

                <div class="card-request">
                  <button
                    type="button"
                    class="card-request-btn"
                    :disabled="requestStatus(point.key) === 'sending'"
                    @click="submitRequest(point)"
                  >
                    {{ requestStatus(point.key) === 'sending'
                      ? 'ОТПРАВЛЯЕМ…'
                      : 'ОСТАВИТЬ ЗАЯВКУ' }}
                  </button>

                  <div
                    v-if="requestStatus(point.key) === 'success'"
                    class="card-request-note card-request-note--ok"
                  >
                    Заявка отправлена. Посмотреть можно в личном кабинете.
                  </div>

                  <div
                    v-else-if="requestStatus(point.key) === 'error'"
                    class="card-request-note card-request-note--err"
                  >
                    {{ requestError(point.key) }}
                  </div>
                </div>

              </div>

            </article>

            </div>

            </template>
          </q-virtual-scroll>

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
  groupSides,
  groupByPoint
} from '../utils/constructionGroups'
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FiltersSidebar from '../components/filters/FiltersSidebar.vue'
import MapSearch from '../components/workspace/MapSearch.vue'
import PointSearchPanel from '../components/workspace/PointSearchPanel.vue'
import MapView from '../map/MapView.vue'

import { getConstructions } from '../services/api'

import {
  useConstructionsFilter
} from '../composables/useConstructionsFilter'

import { useAccount } from '../composables/useAccount'

import { usePortfolio } from '../composables/usePortfolio'
import {
  photoLabel,
  sanitizeFileName,
  usePhotoViewer
} from '../composables/usePhotoViewer'


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

/* Подпись стороны блока: динамика — сторона блока, иначе своя подпись. */
function blockSide(block) {
  const item = blockPrimary(block)
  const side = sideLabel(item)
  return block.kind === 'dynamic' ? parentSide(side, item.type) : side
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

/* ------------------------------------------------- фото (адаптивные) */

/*
 * API отдаёт варианты одного фото: photo (card, 1000px),
 * photo_thumb (400px) и photo_large (2400px). Любой из них может
 * отсутствовать — тогда подставляем photo (фолбэк), поэтому код
 * остаётся рабочим до и после правки бэкенда.
 */
function photoThumb(item) {
  return item?.photo_thumb || item?.photo || ''
}

function photoCard(item) {
  return item?.photo || item?.photo_thumb || ''
}

function photoSrcset(item) {
  const parts = []

  const thumb = item?.photo_thumb
  if (thumb) {
    parts.push(`${thumb} 400w`)
  }

  const card = item?.photo
  if (card) {
    parts.push(`${card} 1000w`)
  }

  const large = item?.photo_large
  if (large) {
    parts.push(`${large} 2400w`)
  }

  return parts.join(', ')
}

/* ---------------------------------------------------------- портфель */

/*
 * Портфель — общий стор приложения. На карточке: кнопка-переключатель
 * режима выбора месяца + кликабельные месяцы в этом режиме.
 */
const {
  isInPortfolio,
  isMonthSelected,
  isSelectionMode,
  toggleSelectionMode,
  toggleMonth,
  removeSurface,
  syncWithConstructions
} = usePortfolio()

/* ------------------------------------------------- фото: общее окно */

const { openPhoto } = usePhotoViewer()

/*
 * Клик по фото карточки: открываем общее окно просмотра.
 * Название и имя файла — «город, адрес · Сторона X».
 */
function openBlockPhoto(point, block) {
  const item = blockPrimary(block)
  const src = item?.photo_large || item?.photo || item?.photo_thumb || ''

  if (!src) {
    return
  }

  const label = photoLabel({
    city: point?.city,
    address: point?.address,
    side: blockSide(block)
  })

  openPhoto({
    url: src,
    title: label,
    filename: sanitizeFileName(label, src)
  })
}

/* id поверхности (в портфеле может быть и число, и строка). */
function surfaceIdOf(item) {
  const id = item?.id

  return id === undefined || id === null || id === '' ? null : id
}

/*
 * Блок активен (розовая кнопка, кликабельные месяцы), если ведущая
 * поверхность уже в портфеле или для неё включён режим выбора.
 */
function isBlockActive(block) {
  const id = surfaceIdOf(blockPrimary(block))

  return id !== null && (isInPortfolio(id) || isSelectionMode(id))
}

/*
 * Клик по кнопке-переключателю (детерминированно, без «слепого» toggle):
 *   неактивна -> включаем режим выбора;
 *   активна   -> сбрасываем: removeSurface убирает и месяцы, и режим.
 */
function toggleBlockPfMode(block) {
  const id = surfaceIdOf(blockPrimary(block))

  if (id === null) {
    return
  }

  if (isBlockActive(block)) {
    removeSurface(id)
  } else {
    toggleSelectionMode(id)
  }
}

/* Клик по месяцу — только у активного блока. */
function onCardMonthClick(block, surface, month) {
  if (!isBlockActive(block)) {
    return
  }

  const id = surfaceIdOf(surface)

  if (id === null) {
    return
  }

  toggleMonth(
    surface,
    month.full,
    surface.month_prices?.[month.full]
  )
}

const route = useRoute()
const router = useRouter()
const constructions = ref([])

/* Личный кабинет: авторизация и создание заявок. */
const { isAuthenticated, createRequest } = useAccount()

/*
 * Статус кнопки «Оставить заявку» по карточкам (ключ карточки):
 * 'idle' | 'sending' | 'success' | 'error'.
 */
const requestStates = ref({})
const requestErrors = ref({})

function requestStatus(key) {
  return requestStates.value[key] || 'idle'
}

function requestError(key) {
  return requestErrors.value[key] || 'Не удалось отправить заявку'
}

function setRequestState(key, state) {
  requestStates.value = { ...requestStates.value, [key]: state }
}

/*
 * Кнопка «Оставить заявку» в карточке.
 *
 * Авторизован — создаём заявку (title = «формат · адрес»,
 * surface_id = id ведущей поверхности блока). Иначе — на /account.
 */
async function submitRequest(card) {
  if (!isAuthenticated.value) {
    router.push('/account')
    return
  }

  const key = card.key
  const block = card.blocks?.[0] || {}
  const surfaceId = blockPrimary(block).id

  setRequestState(key, 'sending')
  requestErrors.value = { ...requestErrors.value, [key]: '' }

  try {
    await createRequest({
      title: `${blockType(block)} · ${card.address}`,
      surface_id: surfaceId ?? null
    })

    setRequestState(key, 'success')
  } catch (error) {
    setRequestState(key, 'error')
    requestErrors.value = {
      ...requestErrors.value,
      [key]: (error && error.message) || 'Не удалось отправить заявку'
    }
  }
}
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
const pointRadius = ref(1000)

/* Шаги радиуса поиска (метры). */
const RADIUS_STEPS = [50, 100, 200, 300, 500, 800, 1000, 1500, 2000, 3000]

/* Ближайший шаг к текущему радиусу. */
const pointRadiusIndex = computed(() => {
  const value = Number(pointRadius.value) || 0

  let best = 0

  for (let index = 0; index < RADIUS_STEPS.length; index += 1) {
    if (
      Math.abs(RADIUS_STEPS[index] - value) <
      Math.abs(RADIUS_STEPS[best] - value)
    ) {
      best = index
    }
  }

  return best
})

function onPointRadiusInput(event) {
  pointRadius.value = RADIUS_STEPS[Number(event.target.value)]
}

function formatRadius(value) {
  return value < 1000 ? `${value} м` : `${value / 1000} км`
}

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

/*
 * Конструкции в радиусе зафиксированной точки.
 * Не зависит от активной закладки: пока точка зафиксирована,
 * результаты видны и в «Списке», и на «Интерактивной карте».
 */
const pointFilteredConstructions = computed(() => {
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

/*
 * Результаты для закладок «Список» и «Интерактивная карта»:
 * если точка зафиксирована — показываем результаты поиска по точке.
 */
const displayedConstructions = computed(() =>
  pointSelectionState.value === 'fixed'
    ? pointFilteredConstructions.value
    : filteredConstructions.value
)

/* Из панели точки: открыть закладку «Список» с найденными результатами. */
function openListFromPoint() {
  workspaceMode.value = 'list'
}

/*
 * Поиск в верхней плавающей строке.
 * В режиме точки — координаты/адрес (переключатель на краю поля),
 * в остальных режимах — обычный поиск по адресу/городу/номеру.
 */
const topSearchMode = ref('coords')

const topSearchValue = computed({
  get() {
    if (workspaceMode.value === 'point') {
      return topSearchMode.value === 'coords'
        ? pointCoordinates.value
        : pointAddress.value
    }

    return searchQuery.value
  },

  set(value) {
    if (workspaceMode.value === 'point') {
      if (topSearchMode.value === 'coords') {
        pointCoordinates.value = value
      } else {
        pointAddress.value = value
      }
    } else {
      searchQuery.value = value
    }
  }
})

function onTopSearch() {
  if (workspaceMode.value === 'point') {
    if (topSearchMode.value === 'coords') {
      executePointSearch()
    } else {
      executeAddressSearch()
    }

    return
  }

  onMapSearch()
}


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
 * Список: ОТДЕЛЬНАЯ карточка на сторону конструкции.
 *
 * Каждая сторона (A, B, C) — своя карточка. Если у стороны есть
 * подповерхности (A(1), A(2)…), в карточке показываем фото первой
 * поверхности и список «занято/свободно» строками — как в попапе карты.
 */
const listPoints = computed(() => {
  const cards = []

  for (const point of groupByPoint(displayedConstructions.value)) {
    const deduped = dedupeSides(point.items)

    const first = point.items[0] || {}
    const address = String(first.address || first.name || 'Адрес не указан').trim()
    const city = String(first.city || '').trim() || '—'

    for (const block of groupSides(deduped)) {
      cards.push({
        key: `${point.key}|${block.type}|${block.parent}`,
        address,
        city,
        blocks: [block]
      })
    }
  }

  return cards
})

/*
 * Виртуализация списка строками: q-virtual-scroll одномерный, поэтому
 * виртуализируем не отдельные карточки, а строки сетки. Число колонок
 * повторяет прежний auto-fill minmax(300px, 1fr) с gap 18px и зависит
 * от реальной ширины области списка (ResizeObserver ниже).
 */
const listViewRef = ref(null)
const listColumns = ref(3)
let listResizeObserver = null

function computeListColumns(width) {
  if (!width) {
    return 1
  }

  // auto-fill minmax(300px, 1fr) + gap 18px: сколько колонок влезает.
  return Math.max(
    1,
    Math.floor((width + 18) / (300 + 18))
  )
}

/* listPoints режем на строки по listColumns (последняя может быть короче). */
const listRows = computed(() => {
  const columns = Math.max(1, listColumns.value)
  const points = listPoints.value
  const rows = []

  for (let i = 0; i < points.length; i += columns) {
    const items = points.slice(i, i + columns)

    // Ключ строки — по первому элементу: стабилен, пока не меняется
    // состав/порядок, и корректно пересобирается при смене колонок.
    rows.push({
      key: `${items[0]?.key ?? 'row'}|${i}`,
      items
    })
  }

  return rows
})

/*
 * Область списка появляется только в режиме «Список» (v-if), поэтому
 * вешаем ResizeObserver на изменение самой ref, а не в onMounted.
 */
function availableListWidth(el) {
  const styles = getComputedStyle(el)

  return (
    el.clientWidth -
    (Number.parseFloat(styles.paddingLeft) || 0) -
    (Number.parseFloat(styles.paddingRight) || 0)
  )
}

watch(listViewRef, el => {
  if (listResizeObserver) {
    listResizeObserver.disconnect()
    listResizeObserver = null
  }

  if (!el || typeof ResizeObserver === 'undefined') {
    return
  }

  // Стартовое значение — по ширине контента (без паддингов).
  listColumns.value = computeListColumns(availableListWidth(el))

  listResizeObserver = new ResizeObserver(entries => {
    const width = entries[0]?.contentRect?.width

    if (width) {
      listColumns.value = computeListColumns(width)
    }
  })

  listResizeObserver.observe(el)
})

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

/*
 * Делегирование кликов для попапов карты.
 *
 * Разметку кнопок и месяцев строит popupContent.js; попап — статичная
 * HTML-строка, поэтому реактивность Vue до неё не достаёт и состояние
 * (режим/выбор) переключаем напрямую через классы DOM.
 */
/* Поверхность активна: в портфеле или включён режим выбора месяцев. */
function isSurfaceActive(id) {
  return (
    id !== null &&
    id !== undefined &&
    id !== '' &&
    (isInPortfolio(id) || isSelectionMode(id))
  )
}

/*
 * Приводит DOM попапа к актуальному состоянию после переключения:
 * класс is-active у кнопок «Портфель» и класс pf-mode у корня попапа.
 * Если активных кнопок не осталось — снимает is-selected со всех месяцев.
 */
function refreshPopupState(popupRoot) {
  if (!popupRoot) {
    return
  }

  let anyActive = false

  popupRoot.querySelectorAll('[data-pf-toggle]').forEach(button => {
    const id = button.getAttribute('data-pf-toggle')
    const active = isSurfaceActive(id)

    button.classList.toggle('is-active', active)

    if (active) {
      anyActive = true
    }
  })

  popupRoot.classList.toggle('pf-mode', anyActive)

  if (!anyActive) {
    popupRoot
      .querySelectorAll('.popup-month.is-selected')
      .forEach(monthEl => monthEl.classList.remove('is-selected'))
  }
}

/* Снимает акцентные рамки со всех месяцев указанной поверхности. */
function clearSurfaceMonths(popupRoot, surfaceId) {
  if (!popupRoot) {
    return
  }

  popupRoot
    .querySelectorAll(`[data-pf-month^="${surfaceId}|"]`)
    .forEach(monthEl => monthEl.classList.remove('is-selected'))
}

function onDocumentClick(event) {
  const target = event.target

  if (!(target instanceof Element)) {
    return
  }

  // Кнопка «Портфель» в попапе: неактивна -> режим выбора; активна -> сброс.
  const toggleEl = target.closest('[data-pf-toggle]')

  if (toggleEl) {
    const id = toggleEl.getAttribute('data-pf-toggle')

    if (id) {
      const popupRoot =
        toggleEl.closest('.popup') ||
        toggleEl.closest('.albion-popup')

      if (isSurfaceActive(id)) {
        // Сброс: removeSurface удаляет и месяцы, и режим из стора,
        // поэтому сразу снимаем рамки со всех месяцев поверхности.
        removeSurface(id)
        clearSurfaceMonths(popupRoot, id)
      } else {
        toggleSelectionMode(id)
      }

      refreshPopupState(popupRoot)
    }

    return
  }

  // Месяц в попапе: добавить/убрать пару (поверхность, месяц).
  const monthEl = target.closest('[data-pf-month]')

  if (!monthEl) {
    return
  }

  const raw = monthEl.getAttribute('data-pf-month') || ''
  const sep = raw.indexOf('|')

  if (sep <= 0) {
    return
  }

  const surfaceId = raw.slice(0, sep)
  const monthFull = raw.slice(sep + 1)

  // Данные поверхности берём из уже загруженного списка конструкций.
  const surface = constructions.value.find(
    construction => String(construction?.id) === surfaceId
  )

  if (!surface) {
    return
  }

  toggleMonth(surface, monthFull, surface.month_prices?.[monthFull])

  monthEl.classList.toggle(
    'is-selected',
    isMonthSelected(surfaceId, monthFull)
  )

  const popupRoot =
    monthEl.closest('.popup') ||
    monthEl.closest('.albion-popup')

  // Снят последний месяц — позиция ушла из портфеля: убираем рамки
  // со всех её месяцев, иначе они останутся висеть.
  if (!isSurfaceActive(surfaceId)) {
    clearSurfaceMonths(popupRoot, surfaceId)
  }

  // Кнопки и pf-mode корня — по актуальному состоянию стора.
  refreshPopupState(popupRoot)
}

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)

  try {
    const data = await getConstructions()
    constructions.value = Array.isArray(data) ? data : []

    // Подтягиваем свежие цены/статусы выбранных месяцев из psql.
    syncWithConstructions(constructions.value)

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

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)

  if (listResizeObserver) {
    listResizeObserver.disconnect()
    listResizeObserver = null
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
  /* Ровно экран минус реальные высоты шапки и подвала (меряются в MainLayout)
     — подвал встаёт сразу под контентом, без пустого зазора. */
  height: calc(100vh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px));
  height: calc(100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px));

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

  /* Скроллится не вся область, а сам виртуальный список внутри
     (см. .construction-list) — иначе высоту не ограничить. */
  overflow: hidden;

  padding: 122px 28px 40px;

  background: #f4f6f7;
}

.list-header {
  margin-bottom: 22px;
}

.list-kicker {
  color: var(--albion-accent);

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
  /* Корень q-virtual-scroll — единственный скроллер списка:
     высота ограничена рамкой .list-view, поэтому прокручивается
     только область списка, а не страница целиком. */
  height: 100%;

  overflow-y: auto;

  display: block;
}

/* Одна виртуальная строка — сетка из listColumns колонок,
   как прежний auto-fill minmax(300px, 1fr). */
.construction-row {
  display: grid;

  grid-template-columns: repeat(3, 1fr);

  gap: 18px;

  margin-bottom: 18px;
}

/* Убираем фоновые «полоски»-заглушки Quasar у элементов-распорок
   виртуального скролла. */
.construction-list :deep(.q-virtual-scroll__padding) {
  background: none;
}

.construction-card {
  overflow: hidden;

  display: flex;
  flex-direction: column;

  /* Высота — по содержимому: в виртуальном скролле контейнер имеет
     заданную высоту, и height:100% дал бы каждой карточке её всю. */
  height: auto;

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
  color: var(--albion-accent);
  font-size: 20px;
  line-height: 1;
  font-weight: 950;
}

.card-promo-price .promo-price-currency {
  color: var(--albion-accent);
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

/* Кнопка «Оставить заявку» и её статус */

.card-request {
  /* Прижимаем кнопку к низу карточки — низ выровнен у всех */
  margin-top: auto;
  padding-top: 12px;

  border-top: 1px solid #edf0f2;
}

.card-request-btn {
  width: 100%;
  min-height: 40px;
  padding: 0 14px;

  border: 0;
  border-radius: 10px;

  background: var(--albion-accent);
  color: #fff;

  cursor: pointer;

  font-size: 11px;
  font-weight: 900;
  letter-spacing: .06em;

  transition:
    background .18s ease,
    opacity .18s ease;
}

.card-request-btn:hover:not(:disabled) {
  background: #c92219;
}

.card-request-btn:disabled {
  opacity: .6;
  cursor: default;
}

.card-request-note {
  margin-top: 8px;

  font-size: 11px;
  line-height: 1.4;
}

.card-request-note--ok {
  color: #1b5e20;
}

.card-request-note--err {
  color: #b3261e;
}
.card-content h2 {
  margin: 0 0 3px;

  color: #17212b;

  font-size: 17px;
  line-height: 1.15;
}

.card-address-main {
  /* Ровно две строки: фото во всех карточках начинаются на одном уровне */
  min-height: 2.3em;

  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;

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

/* Фото карточки открывает общее окно просмотра */
.card-photo-clickable {
  cursor: pointer;
}

.card-block .card-months {
  margin-top: 10px;
  padding-top: 9px;
}

/* Месяцы в строке динамической стороны — без верхней границы и отступов.
   Специфичность как у `.card-block .card-months`, иначе оно перебивает. */
.card-block .card-months--inline {
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

/* Портфель: кнопка и кликабельные месяцы в режиме выбора. */

.card-portfolio {
  margin-top: 10px;
}

.card-pf-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  padding: 6px 11px;

  border: 1px solid #dce2e6;
  border-radius: 8px;

  background: #fff;
  color: #52606a;

  cursor: pointer;

  font-size: 10px;
  font-weight: 800;
  letter-spacing: .3px;

  transition: .15s ease;
}

.card-pf-toggle:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

/* Активное состояние: поверхность редактируется (в портфеле либо режим). */
.card-pf-toggle.is-active {
  border-color: var(--albion-accent);
  background: #fdeceb;
  color: var(--albion-accent);
}

/* Месяцы кликабельны только у активного блока. */
.card-block.pf-mode .card-month {
  cursor: pointer;
}

.card-block.pf-mode .card-month:hover {
  filter: brightness(.96);
}

/* Выбранный месяц — акцентная рамка. */
.card-month.is-selected {
  outline: 2px solid var(--albion-accent);
  outline-offset: 1px;
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
  gap: 10px;
}

.card-dynamic-side {
  flex: 0 0 auto;

  min-width: 40px;

  display: inline-flex;
  align-items: center;

  color: #17212b;

  font-size: 10px;
  font-weight: 900;
  line-height: 1.2;
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

  background: var(--albion-accent);

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

  /* Число колонок строки задаётся из JS (listColumns) inline-стилем,
     поэтому здесь правило не нужно. */
  .construction-row {
    gap: 14px;
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
  bottom: 96px;
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
  background: var(--albion-accent);
  color: #fff;
}

.point-confirm-button:hover {
  background: #c92219;
}

.point-change-button {
  border: 1px solid #d5dade;
  background: #fff;
  color: #17212b;
}

.point-fixed-badge {
  position: absolute;
  left: 50%;
  bottom: 96px;
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

/* Плавающий слайдер радиуса (под плашкой точки) */
.point-radius-float {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 949;

  width: min(460px, calc(100% - 40px));

  padding: 10px 14px 8px;

  background: rgba(255, 255, 255, .97);
  border: 1px solid #dfe4e7;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(23, 33, 43, .16);
}

.point-radius-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;

  margin-bottom: 4px;

  color: #68757e;

  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1px;
}

.point-radius-head strong {
  color: var(--albion-accent);
  font-size: 12px;
  font-weight: 900;
}

.point-radius-range {
  width: 100%;
  accent-color: var(--albion-accent);
  cursor: pointer;
}

.point-radius-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
}

.point-radius-marks span {
  color: #b3bcc2;
  font-size: 8px;
  font-weight: 700;
}

.point-radius-marks span.active {
  color: #17212b;
}

/* Мишень поиска: двойное кольцо (тёмное + акцент) и центральная точка. */
.point-map-crosshair::before {
  content: '';

  position: absolute;
  inset: 3px;

  border: 2px solid rgba(23, 33, 43, .8);
  border-radius: 50%;

  box-shadow: 0 1px 6px rgba(23, 33, 43, .18);
}

.point-map-crosshair::after {
  content: '';

  position: absolute;
  inset: 10px;

  border: 2px solid var(--albion-accent);
  border-radius: 50%;
}

.point-map-crosshair span {
  position: absolute;

  left: 50%;
  top: 50%;

  width: 9px;
  height: 9px;

  transform: translate(-50%, -50%);

  border: 2px solid #fff;
  border-radius: 50%;

  background: var(--albion-accent);

  box-shadow: 0 1px 4px rgba(23, 33, 43, .4);
}

/* Точка выбрана и ждёт фиксации — мягкая пульсация. */
.point-map-crosshair.pending::before {
  border-color: var(--albion-accent);

  animation: crosshair-pulse 1.4s ease-out infinite;
}

@keyframes crosshair-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(225, 42, 31, 0);
  }

  50% {
    box-shadow: 0 0 0 8px rgba(225, 42, 31, .12);
  }
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

/* =========================================================
   ПОРТФЕЛЬ В ПОПАПАХ КАРТЫ
   Разметку строит popupContent.js; попапы вне Vue-дерева,
   поэтому стили — глобальные (не scoped).
   ========================================================= */

/* Вне режима выбора месяцы некликабельны; в режиме — активны. */
.popup .popup-months,
.popup .popup-month {
  pointer-events: none;
}

.popup.pf-mode .popup-months,
.popup.pf-mode .popup-month {
  pointer-events: auto;
  cursor: pointer;
}

.popup.pf-mode .popup-month:hover {
  filter: brightness(.96);
}

/* Выбранный месяц — акцентная рамка (как на карточках списка). */
.popup-month.is-selected {
  outline: 2px solid var(--albion-accent);
  outline-offset: 1px;
}

/* Кнопка «Портфель» в секции попапа. */
.popup-portfolio {
  display: flex;
  justify-content: center;

  margin-top: 9px;
}

.popup-pf-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  padding: 5px 11px;

  border: 1px solid #dce2e6;
  border-radius: 8px;

  background: #fff;
  color: #52606a;

  cursor: pointer;

  font-family: inherit;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .3px;

  transition: .15s ease;
}

.popup-pf-toggle:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

.popup-pf-toggle.is-active {
  border-color: var(--albion-accent);
  background: #fdeceb;
  color: var(--albion-accent);
}

.popup-pf-icon {
  font-size: 15px;
  line-height: 1;
}
</style>
