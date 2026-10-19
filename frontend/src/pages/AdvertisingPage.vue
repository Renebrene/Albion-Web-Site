<template>
  <q-page class="advertising-page">
    <div class="app">
      <FiltersSidebar
        v-if="workspaceMode !== 'point'"
        :mode="workspaceMode"
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
        <div v-if="loading" class="workspace-state" role="status">
          Загрузка конструкций…
        </div>

        <div
          v-else-if="loadError"
          class="workspace-state workspace-state--error"
          role="alert"
        >
          <p>{{ loadError }}</p>
          <button type="button" class="slide-btn" @click="reloadConstructions">
            Повторить
          </button>
        </div>

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

        <div v-if="workspaceMode === 'map'" class="map-wrap">
          <MapView
            ref="mapViewRef"
            :constructions="displayedConstructions"
            :all-constructions="constructions"
            :selected-months="selectedMonths"
          />
        </div>

        <!-- ПОИСК ПО ТОЧКЕ И АДРЕСУ -->

        <div v-else-if="workspaceMode === 'point'" class="map-wrap">
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

          <!--
            Панель управления точкой — ОДНА плашка, закреплена внизу
            по центру. Слева — статус точки (подтверждение или бейдж),
            справа — радиус поиска; в один ряд.
          -->
          <div class="point-controls">
            <div
              v-if="pointSelectionState !== 'fixed'"
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

              <button type="button" @click="changeSelectedPoint">
                ИЗМЕНИТЬ ТОЧКУ
              </button>
            </div>

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
              />

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
        </div>

        <!-- СПИСОК -->

        <div
          v-else-if="workspaceMode === 'list'"
          ref="listViewRef"
          class="list-view"
        >
          <!-- Шапка списка закреплена: заголовок и переключатель колонок
               не двигаются, карточки прокручиваются под ними. -->
          <div class="list-header">
            <div>
              <div class="list-kicker"> РЕКЛАМНЫЕ ВОЗМОЖНОСТИ </div>

              <h1>
                {{ displayedConstructions.length }}
                {{ sidesPhrase(displayedConstructions.length) }}
              </h1>
            </div>

            <!-- Ручной выбор числа колонок карточек. -->
            <div class="list-columns" role="group" aria-label="Число колонок">
              <button
                v-for="count in columnOptions"
                :key="count"
                type="button"
                :class="{ active: listColumns === count }"
                @click="setListColumns(count)"
              >
                {{ count }}
              </button>
            </div>
          </div>

          <!--
            Виртуальный скролл строками: в DOM рендерятся только видимые
            строки сетки (плюс буфер), а не весь список целиком.
          -->
          <q-virtual-scroll
            v-if="listPoints.length"
            ref="virtualListRef"
            class="construction-list"
            :items="listRows"
            :virtual-scroll-item-size="820"
            @virtual-scroll="onListScroll"
          >
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
                          </div>

                          <div
                            v-if="hasPrice(blockPrimary(block))"
                            class="card-price-inline"
                          >
                            <span
                              v-if="blockPrimary(block).price"
                              class="price-value"
                              :class="{
                                'is-old': promoPriceOf(blockPrimary(block))
                              }"
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
                              <span class="promo-price-currency"> ₽ </span>
                              <span class="promo-price-note">
                                акционная цена
                              </span>
                            </div>
                          </div>
                        </div>

                        <!-- Пустая строка над городом: формат сверху -->
                        <div class="card-head">
                          <div class="card-place">
                            {{ point.city }}
                          </div>

                          <div class="card-address-main">
                            {{ point.address }}
                          </div>

                          <div v-if="blockSide(block)" class="card-side-line">
                            СТОРОНА <b>{{ blockSide(block) }}</b>
                          </div>
                        </div>

                        <div class="card-photo card-photo--block">
                          <img
                            v-if="hasCardImage(point, block, blockIndex)"
                            :src="cardImageSrc(point, block, blockIndex)"
                            :srcset="cardImageSrcset(point, block, blockIndex)"
                            sizes="(max-width: 760px) 100vw, (max-width: 1200px) 70vw, 900px"
                            :alt="point.address"
                            loading="lazy"
                            decoding="async"
                            width="1000"
                            height="625"
                            class="card-photo-clickable"
                            :title="
                              cardImageMode(point, block, blockIndex) === 'map'
                                ? 'Открыть карту и фото'
                                : 'Открыть фото и карту'
                            "
                            @click.stop="openBlockPhoto(point, block)"
                          />

                          <div v-else class="no-photo"> ALBION </div>

                          <!-- Переключатель: фото ↔ карта -->
                          <div
                            v-if="canSwitchCardMedia(block)"
                            class="media-switch"
                            @click.stop
                          >
                            <button
                              type="button"
                              class="media-switch__btn"
                              :class="{
                                'is-active':
                                  cardImageMode(point, block, blockIndex) ===
                                  'photo'
                              }"
                              @click.stop="
                                setCardMedia(point, blockIndex, 'photo')
                              "
                            >
                              Фото
                            </button>
                            <button
                              type="button"
                              class="media-switch__btn"
                              :class="{
                                'is-active':
                                  cardImageMode(point, block, blockIndex) ===
                                  'map'
                              }"
                              @click.stop="
                                setCardMedia(point, blockIndex, 'map')
                              "
                            >
                              Карта
                            </button>
                          </div>
                        </div>

                        <!-- Динамика: строки A(1)/A(2)… либо свёрнуто в сторону A -->
                        <div
                          v-if="block.kind === 'dynamic'"
                          class="card-dynamic-rows"
                        >
                          <!-- Режим «по сторонам»: одна строка на сторону;
                               месяц свободен, если свободна хоть одна
                               поверхность, иначе — продано. -->
                          <div
                            v-if="availableMode === 'sides'"
                            class="card-dynamic-row"
                          >
                            <div class="card-months card-months--inline">
                              <button
                                v-for="month in MONTHS"
                                :key="month.full"
                                type="button"
                                class="card-month"
                                :class="[
                                  sideMonthState(block, month.full),
                                  {
                                    'is-selected': isSideMonthSelected(
                                      block,
                                      month.full
                                    ),
                                    'is-locked':
                                      isBlockActive(block) &&
                                      !isSideFree(block, month.full)
                                  }
                                ]"
                                :disabled="
                                  !isBlockActive(block) ||
                                  isSideMonthLocked(block, month.full)
                                "
                                :aria-pressed="
                                  isSideMonthSelected(block, month.full)
                                "
                                :title="sideMonthLabel(block, month.full)"
                                @click="onSideMonthClick(block, month)"
                              >
                                {{ month.short }}
                              </button>
                            </div>
                          </div>

                          <template v-else>
                            <div
                              v-for="row in block.items"
                              :key="sideLabel(row)"
                              class="card-dynamic-row"
                            >
                              <!-- Подпись поверхности (A(1), A(2)…) — как было
                                   до появления режима «по сторонам». -->
                              <span class="card-dynamic-side">
                                {{ sideLabel(row) }}
                              </span>

                              <div class="card-months card-months--inline">
                                <button
                                  v-for="month in MONTHS"
                                  :key="month.full"
                                  type="button"
                                  class="card-month"
                                  :class="[
                                    getCardMonthState(row, month.full),
                                    {
                                      'is-selected':
                                        surfaceIdOf(row) !== null &&
                                        isMonthSelected(row.id, month.full),
                                      'is-locked':
                                        isBlockActive(block) &&
                                        isMonthLocked(row, month.full)
                                    }
                                  ]"
                                  :disabled="
                                    !isBlockActive(block) ||
                                    isMonthLocked(row, month.full)
                                  "
                                  :aria-pressed="
                                    surfaceIdOf(row) !== null &&
                                    isMonthSelected(row.id, month.full)
                                  "
                                  :title="getMonthStatusLabel(row, month.full)"
                                  @click="onCardMonthClick(block, row, month)"
                                >
                                  {{ month.short }}
                                </button>
                              </div>
                            </div>
                          </template>
                        </div>

                        <!-- Статика и видеоэкран: одна строка месяцев -->
                        <div v-else class="card-months">
                          <button
                            v-for="month in MONTHS"
                            :key="month.full"
                            type="button"
                            class="card-month"
                            :class="[
                              getCardMonthState(
                                blockPrimary(block),
                                month.full
                              ),
                              {
                                'is-selected':
                                  surfaceIdOf(blockPrimary(block)) !== null &&
                                  isMonthSelected(
                                    blockPrimary(block).id,
                                    month.full
                                  ),
                                'is-locked':
                                  isBlockActive(block) &&
                                  isMonthLocked(blockPrimary(block), month.full)
                              }
                            ]"
                            :disabled="
                              !isBlockActive(block) ||
                              isMonthLocked(blockPrimary(block), month.full)
                            "
                            :aria-pressed="
                              surfaceIdOf(blockPrimary(block)) !== null &&
                              isMonthSelected(
                                blockPrimary(block).id,
                                month.full
                              )
                            "
                            :title="
                              getMonthStatusLabel(
                                blockPrimary(block),
                                month.full
                              )
                            "
                            @click="
                              onCardMonthClick(
                                block,
                                blockPrimary(block),
                                month
                              )
                            "
                          >
                            {{ month.short }}
                          </button>
                        </div>

                        <!-- Портфель: кнопка (два состояния) + кликабельные месяцы -->
                        <div class="card-portfolio">
                          <button
                            type="button"
                            class="card-pf-toggle"
                            :class="{ 'is-active': isBlockActive(block) }"
                            :title="
                              isBlockActive(block)
                                ? 'Убрать из портфеля'
                                : 'Добавить в портфель'
                            "
                            @click="toggleBlockPfMode(block)"
                          >
                            <q-icon name="work_outline" size="16px" />
                            <span>Портфель</span>
                          </button>
                        </div>

                        <div class="card-features">
                          <span
                            class="card-feature"
                            :title="
                              hasLight(blockPrimary(block))
                                ? 'Подсветка есть'
                                : 'Без подсветки'
                            "
                          >
                            <span
                              class="feature-picto lightbulb"
                              :class="
                                hasLight(blockPrimary(block)) ? 'on' : 'off'
                              "
                              >💡</span
                            >
                            <span class="feature-label">подсветка</span>
                          </span>

                          <span class="card-feature" title="статика/динамика">
                            <span class="feature-dyn">
                              <span
                                class="dyn-word"
                                :class="{
                                  'is-active': block.kind === 'static'
                                }"
                                >статика</span
                              >

                              <span class="dyn-sep">/</span>

                              <span
                                class="dyn-word"
                                :class="{
                                  'is-active': block.kind !== 'static'
                                }"
                                >динамика</span
                              >

                              <!-- Кол-во поверхностей стороны (для динамики,
                                   кроме видеоэкрана; гасится настройкой
                                   «Показывать количество динамических сторон»). -->
                              <span
                                v-if="block.kind === 'dynamic' && showDynCount"
                                class="dyn-count"
                                >({{ block.items.length }})</span
                              >
                            </span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </article>
              </div>
            </template>
          </q-virtual-scroll>

          <div v-else class="empty-state">
            <div class="empty-icon"> 0 </div>

            <h2> Ничего не найдено </h2>

            <p> Измените параметры фильтра или очистите поиск. </p>

            <button type="button" @click="resetFilters">
              Сбросить фильтры
            </button>
          </div>

          <!-- Быстрый возврат к началу списка. -->
          <button
            v-if="listScrolled"
            type="button"
            class="list-to-top"
            aria-label="Наверх"
            title="Наверх"
            @click="scrollListToTop"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M12 19V5M5 12l7-7 7 7"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </div>

        <div class="map-tools">
          <button class="tool" title="Сбросить фильтры" @click="resetFilters">
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
  getMonthStatusLabel,
  isFree
} from '../utils/availability'
import {
  MONTHS,
  sideLabel,
  parentSide,
  dedupeSides,
  groupSides,
  groupByPoint,
  setMonthsFromItems
} from '../utils/constructionGroups'
import { availableMode } from '../config/availableMode'
import { showDynCount } from '../config/dynCount'
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FiltersSidebar from '../components/filters/FiltersSidebar.vue'
import MapSearch from '../components/workspace/MapSearch.vue'
import PointSearchPanel from '../components/workspace/PointSearchPanel.vue'
import MapView from '../map/MapView.vue'
import { clearPopupContentCache } from '../map/popupContent'

import { getConstructions } from '../services/api'

import { useConstructionsFilter } from '../composables/useConstructionsFilter'

import { useChatWorkspace } from '../composables/useChatWorkspace'
import { usePortfolio } from '../composables/usePortfolio'
import {
  photoLabel,
  sanitizeFileName,
  usePhotoViewer
} from '../composables/usePhotoViewer'

/* Акционная цена из отдельной колонки 1С (пока в данных отсутствует). */
function promoPriceOf(item) {
  return String(item?.promoPrice ?? item?.promo_price ?? '').trim()
}

function getCardMonthState(item, month) {
  return getAvailabilityState(item, month)
}

/* --- Свёрнутый режим «по сторонам» (available_mode = 'sides') --- */

/* Месяц стороны свободен, если свободна хоть одна её поверхность. */
function isSideFree(block, month) {
  return (block?.items || []).some(
    item => getAvailabilityState(item, month) === 'free'
  )
}

function sideMonthState(block, month) {
  return isSideFree(block, month) ? 'free' : 'busy'
}

function sideMonthLabel(block, month) {
  return isSideFree(block, month) ? 'Свободно' : 'Продано'
}

function isSideMonthSelected(block, month) {
  return (block?.items || []).some(
    item => surfaceIdOf(item) !== null && isMonthSelected(item.id, month)
  )
}

/* Клик по месяцу свёрнутой стороны применяется ко всем её поверхностям. */
function onSideMonthClick(block, month) {
  for (const item of block?.items || []) {
    onCardMonthClick(block, item, month)
  }
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
  return ['да', 'yes', 'true', '1'].includes(
    String(item?.light || '')
      .trim()
      .toLowerCase()
  )
}

/* «35 рекламных сторон», «1 рекламная сторона», «2 рекламные стороны». */
function sidesPhrase(count) {
  const n = Math.abs(Number(count) || 0)
  const mod10 = n % 10
  const mod100 = n % 100

  if (mod10 === 1 && mod100 !== 11) {
    return 'рекламная сторона'
  }

  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return 'рекламные стороны'
  }

  return 'рекламных сторон'
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

/* ------------------------------------------- карта-схема на карточке */

/*
 * На карточке можно переключать, что показывать: фото или карту-схему
 * (крупный вариант map_large). Выбор запоминается по ключу карточки и
 * блока, чтобы не сбиваться при виртуальном скролле. Если чего-то из
 * двух изображений нет — показываем то, что есть, без переключателя.
 */
const cardMedia = ref({})

function blockMap(item) {
  return item?.map_large || item?.map_card || item?.map_thumb || item?.map || ''
}

function hasBlockMap(item) {
  return Boolean(blockMap(item))
}

function canSwitchCardMedia(block) {
  const item = blockPrimary(block)

  return Boolean(photoCard(item)) && Boolean(blockMap(item))
}

function cardImageMode(point, block, blockIndex) {
  const item = blockPrimary(block)
  const wanted = cardMedia.value[`${point.key}-${blockIndex}`] || 'photo'

  if (wanted === 'map') {
    return hasBlockMap(item) ? 'map' : 'photo'
  }

  if (photoCard(item)) {
    return 'photo'
  }

  return hasBlockMap(item) ? 'map' : 'none'
}

function hasCardImage(point, block, blockIndex) {
  return cardImageMode(point, block, blockIndex) !== 'none'
}

function cardImageSrc(point, block, blockIndex) {
  const item = blockPrimary(block)

  return cardImageMode(point, block, blockIndex) === 'map'
    ? blockMap(item)
    : photoThumb(item)
}

function cardImageSrcset(point, block, blockIndex) {
  if (cardImageMode(point, block, blockIndex) === 'map') {
    return undefined
  }

  return photoSrcset(blockPrimary(block))
}

function setCardMedia(point, blockIndex, mode) {
  cardMedia.value = {
    ...cardMedia.value,
    [`${point.key}-${blockIndex}`]: mode
  }
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
  syncWithConstructions,
  items: portfolioItems,
  selectionMode: portfolioSelectionMode
} = usePortfolio()

/*
 * Разметка поп-апа карты статична, а классы «активно/выбрано» ставятся
 * вручную. Поэтому при внешнем изменении портфеля (очистка в панели или
 * личном кабинете, удаление позиции) приводим открытые поп-апы к
 * актуальному состоянию — иначе подсветка остаётся.
 */
const portfolioSignature = computed(() => {
  const items = portfolioItems.value
    .map(
      item =>
        `${item.surfaceId}:${Object.keys(item.months || {})
          .sort()
          .join('|')}`
    )
    .sort()
    .join(',')

  const modes = Object.keys(portfolioSelectionMode)
    .filter(key => portfolioSelectionMode[key])
    .sort()
    .join(',')

  return `${items}::${modes}`
})

function refreshOpenPopups() {
  document
    .querySelectorAll('.leaflet-popup .popup, .albion-popup')
    .forEach(root => refreshPopupState(root))
}

watch(portfolioSignature, refreshOpenPopups)

/* ------------------------------------------------- фото: общее окно */

const { openPhoto } = usePhotoViewer()

/*
 * Клик по фото карточки: открываем общее окно просмотра (как в портфеле) —
 * фото и карта-схема, с переключением и сохранением.
 * Название — «город, адрес · Сторона X».
 */
function openBlockPhoto(point, block) {
  const item = blockPrimary(block)
  const photoUrl = item?.photo_large || item?.photo || item?.photo_thumb || ''
  const mapUrl =
    item?.map_large || item?.map_card || item?.map_thumb || item?.map || ''

  if (!photoUrl && !mapUrl) {
    return
  }

  const label = photoLabel({
    city: point?.city,
    address: point?.address,
    side: blockSide(block)
  })

  const images = []

  if (photoUrl) {
    images.push({
      url: photoUrl,
      label: 'Фото',
      filename: sanitizeFileName(label, photoUrl)
    })
  }

  if (mapUrl) {
    images.push({
      url: mapUrl,
      label: 'Карта',
      filename: sanitizeFileName(`${label} · карта`, mapUrl)
    })
  }

  openPhoto({ images, title: label })
}

/* id поверхности (в портфеле может быть и число, и строка). */
function surfaceIdOf(item) {
  const id = item?.id

  return id === undefined || id === null || id === '' ? null : id
}

/*
 * Все поверхности блока: строки динамики (A(1)/A(2)/A(3)…) и ведущая.
 *
 * Кнопка должна учитывать их ВСЕ: у призматрона месяц можно выбрать на
 * любой строке, и раньше кнопка смотрела только на ведущую — из-за этого
 * выделение на остальных строках оставалось после выключения.
 */
function blockSurfaces(block) {
  const seen = new Set()
  const list = []

  const push = surface => {
    const id = surfaceIdOf(surface)

    if (id !== null && !seen.has(id)) {
      seen.add(id)
      list.push(surface)
    }
  }

  if (Array.isArray(block?.items)) {
    block.items.forEach(push)
  }

  push(blockPrimary(block))

  return list
}

function blockSurfaceIds(block) {
  return blockSurfaces(block)
    .map(surfaceIdOf)
    .filter(id => id !== null)
}

/*
 * Блок активен (розовая кнопка, кликабельные месяцы), если ЛЮБАЯ его
 * поверхность уже в портфеле или для неё включён режим выбора.
 */
function isBlockActive(block) {
  return blockSurfaceIds(block).some(
    id => isInPortfolio(id) || isSelectionMode(id)
  )
}

/*
 * Клик по кнопке-переключателю (детерминированно, без «слепого» toggle):
 *   неактивна -> включаем режим выбора;
 *   активна   -> сбрасываем ВСЕ поверхности блока, иначе выделение
 *                остаётся на строках, которые кнопка не учитывала.
 */
function toggleBlockPfMode(block) {
  const ids = blockSurfaceIds(block)

  if (!ids.length) {
    return
  }

  if (isBlockActive(block)) {
    ids.forEach(id => removeSurface(id))
  } else {
    toggleSelectionMode(ids[0])
  }
}

/* Месяц стороны: выбранный можно снять, остальные — только свободные. */
function isSideMonthLocked(block, monthFull) {
  if (isSideMonthSelected(block, monthFull)) {
    return false
  }

  return !isSideFree(block, monthFull)
}

/* Месяц можно ВЫБРАТЬ только если он свободен (снять — всегда можно). */
function isMonthLocked(surface, monthFull) {
  const id = surfaceIdOf(surface)

  if (id === null || isMonthSelected(id, monthFull)) {
    return false
  }

  return !isFree(surface, monthFull)
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

  /* Снять можно всегда; добавить — только свободный месяц. */
  if (isMonthLocked(surface, month.full)) {
    return
  }

  toggleMonth(surface, month.full, surface.month_prices?.[month.full])
}

const route = useRoute()
const router = useRouter()
const constructions = ref([])
const loading = ref(true)
const loadError = ref('')
const { resultIds: chatResultIds } = useChatWorkspace()

const mapViewRef = ref(null)
const pointSearchOpen = ref(false)

function focusCity(city) {
  /* Как клик по названию в списке городов — центрируем после готовности карты. */
  focusCityWhenReady(city)
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

  const coordinates = mapViewRef.value?.getCoordinatesAtScreenPoint(
    event.clientX,
    event.clientY
  )

  if (!coordinates) {
    return
  }

  pointCoordinates.value = `${coordinates.lat.toFixed(6)}, ${coordinates.lng.toFixed(6)}`
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

  const toRadians = value => (value * Math.PI) / 180

  const dLat = toRadians(lat2 - lat1)
  const dLng = toRadians(lng2 - lng1)

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLng / 2) ** 2

  return 2 * earthRadius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
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

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return false
    }

    return distanceInMeters(centerLat, centerLng, lat, lng) <= radius
  })
})

/*
 * Результаты для закладок «Список» и «Интерактивная карта»:
 * если точка зафиксирована — показываем результаты поиска по точке.
 */
const displayedConstructions = computed(() => {
  const source =
    pointSelectionState.value === 'fixed'
      ? pointFilteredConstructions.value
      : filteredConstructions.value

  if (route.query.chat !== '1' || !chatResultIds.value.length) {
    return source
  }

  /*
   * Результаты чата — самостоятельная выборка. Активные фильтры сайта
   * (город/формат/поиск/точка) не должны пересекаться с ней: иначе чат
   * нашёл 146 щитов, а карта показывает 0 из-за старого фильтра.
   */
  const ids = new Set(chatResultIds.value.map(value => String(value)))

  return constructions.value.filter(item => ids.has(String(item?.id)))
})

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

  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
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

  console.log('Albion address search:', address)
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
    const address = String(
      first.address || first.name || 'Адрес не указан'
    ).trim()
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
/* Авто-число колонок по ширине области (ResizeObserver). */
const autoListColumns = ref(3)
/* Ручной выбор переключателем 4/5/6; null — авто. */
const userListColumns = ref(null)
let listResizeObserver = null

// Колонок в ряду: ручной выбор (4/5/6), если он задан и экран достаточно
// широкий; иначе — авто по ширине. На узких экранах ручной выбор
// игнорируем, иначе карточки станут нечитаемыми.
const listColumns = computed(() => {
  const auto = autoListColumns.value
  const manual = userListColumns.value

  return manual && auto >= 3 ? manual : auto
})

const columnOptions = [4, 5, 6]

function setListColumns(count) {
  userListColumns.value = count
}

/* Прокрутка списка: ref на q-virtual-scroll и признак «список прокручен»
   для кнопки возврата наверх. */
const virtualListRef = ref(null)
const listScrolled = ref(false)

function onListScroll({ index }) {
  listScrolled.value = index > 0
}

function scrollListToTop() {
  virtualListRef.value?.scrollTo(0)
}

/* При смене режима список монтируется заново сверху — сбрасываем признак
   прокрутки, чтобы кнопка «наверх» не висела зря. */
watch(workspaceMode, () => {
  listScrolled.value = false
})

function computeListColumns(width) {
  if (!width) {
    return 1
  }

  // auto-fill minmax(300px, 1fr) + gap 18px: сколько колонок влезает.
  return Math.max(1, Math.floor((width + 18) / (300 + 18)))
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
  autoListColumns.value = computeListColumns(availableListWidth(el))

  listResizeObserver = new ResizeObserver(entries => {
    const width = entries[0]?.contentRect?.width

    if (width) {
      autoListColumns.value = computeListColumns(width)
    }
  })

  listResizeObserver.observe(el)
})

/*
 * Синхронизация фильтров из URL.
 *
 * useConstructionsFilter после загрузки данных выбирает ВСЕ города,
 * поэтому город/формат из адреса применяем после того, как списки
 * cities/types сформированы — и повторно на следующем тике, чтобы
 * гарантированно перекрыть автоматический «выбор всех».
 *
 * Для города, помимо галочки в фильтре, центрируем карту так же,
 * как при клике по названию в списке городов.
 */
function focusCityWhenReady(city) {
  let frames = 0

  const attempt = () => {
    const view = mapViewRef.value
    const hasData =
      Array.isArray(constructions.value) && constructions.value.length > 0

    /*
     * Ждём И готовности карты, И загрузки конструкций: focusToItems
     * центрируется по данным, и без них центрировать не по чему.
     * Клик по названию на уже загруженной карте поэтому работает,
     * а переход по ссылке из карточки — нет, пока данные не пришли.
     */
    if (!view || !hasData) {
      if (frames++ < 600) {
        requestAnimationFrame(attempt)
      }

      return
    }

    const ready =
      typeof view.whenReady === 'function'
        ? view.whenReady()
        : Promise.resolve()

    ready.then(() => {
      /* Даём Vue разложить данные в пропсы карты, затем центрируем. */
      nextTick(() => view.focusCity(city))
    })
  }

  requestAnimationFrame(attempt)
}

watch(
  [cities, types],
  ([cityValues, typeValues]) => {
    const cityFromUrl = String(route.query.city || '').trim()
    const typeFromUrl = String(route.query.type || '').trim()
    const addressFromUrl = String(route.query.address || '').trim()

    const actualCity =
      cityFromUrl && cityValues.length
        ? cityValues.find(city => city === cityFromUrl)
        : null

    const actualType =
      typeFromUrl && typeValues.length
        ? typeValues.find(type => type === typeFromUrl)
        : null

    if (addressFromUrl) {
      searchQuery.value = addressFromUrl
    }

    nextTick(() => {
      if (actualType) {
        selectedTypes.value = [actualType]
      }

      if (actualCity) {
        /* Галочка в фильтре + центровка карты (как клик по названию). */
        selectedCities.value = [actualCity]
        focusCityWhenReady(actualCity)
      }
    })
  },
  { immediate: true }
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

    /* Режим чата не должен теряться при изменении фильтров. */
    if (route.query.chat) {
      query.chat = route.query.chat
    }

    if (route.query.mode) {
      query.mode = route.query.mode
    }

    const currentQuery = {
      city: route.query.city,
      type: route.query.type,
      address: route.query.address,
      chat: route.query.chat,
      mode: route.query.mode
    }

    const nextQuery = {
      city: query.city,
      type: query.type,
      address: query.address,
      chat: query.chat,
      mode: query.mode
    }

    if (
      currentQuery.city === nextQuery.city &&
      currentQuery.type === nextQuery.type &&
      currentQuery.address === nextQuery.address &&
      currentQuery.chat === nextQuery.chat &&
      currentQuery.mode === nextQuery.mode
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
 * Приводит DOM попапа к актуальному состоянию после переключения.
 *
 * Режим выбора — по СЕКЦИЯМ: у каждой «половины» карточки своя кнопка
 * «Портфель», поэтому активность одной стороны не должна делать
 * кликабельными месяцы соседней.
 */
function refreshPopupState(popupRoot) {
  if (!popupRoot) {
    return
  }

  popupRoot.querySelectorAll('.popup-side-card').forEach(section => {
    let sectionActive = false

    section.querySelectorAll('[data-pf-toggle]').forEach(button => {
      const active = isSurfaceActive(button.getAttribute('data-pf-toggle'))

      button.classList.toggle('is-active', active)

      if (active) {
        sectionActive = true
      }
    })

    section.classList.toggle('pf-mode', sectionActive)

    if (!sectionActive) {
      section
        .querySelectorAll('.popup-month.is-selected')
        .forEach(monthEl => monthEl.classList.remove('is-selected'))
    }

    section.querySelectorAll('.popup-month').forEach(monthEl => {
      const unavailable =
        !sectionActive || monthEl.classList.contains('is-locked')

      monthEl.disabled = unavailable
      monthEl.setAttribute('aria-disabled', String(unavailable))
    })
  })
}

/* Снимает акцентные рамки со всех месяцев указанной поверхности. */
function clearSurfaceMonths(popupRoot, surfaceId) {
  if (!popupRoot) {
    return
  }

  const id = String(surfaceId)

  // data-pf-month может нести список id (агрегация по стороне),
  // поэтому проверяем вхождение, а не префикс.
  popupRoot.querySelectorAll('[data-pf-month]').forEach(monthEl => {
    const raw = monthEl.getAttribute('data-pf-month') || ''
    const sep = raw.indexOf('|')

    if (sep <= 0) {
      return
    }

    const ids = raw
      .slice(0, sep)
      .split(',')
      .map(value => value.trim())

    if (ids.includes(id)) {
      monthEl.classList.remove('is-selected')
    }
  })
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
        toggleEl.closest('.popup') || toggleEl.closest('.albion-popup')

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

  /*
   * data-pf-month = "<id[,id…]>|<месяц>". В режиме «по сторонам» месяц
   * агрегирован по стороне и несёт сразу несколько поверхностей — тогда
   * переключаем месяц у всех.
   */
  const idList = raw
    .slice(0, sep)
    .split(',')
    .map(value => value.trim())
    .filter(Boolean)
  const monthFull = raw.slice(sep + 1)

  // Данные поверхностей берём из уже загруженного списка конструкций.
  const surfaces = idList
    .map(id =>
      constructions.value.find(construction => String(construction?.id) === id)
    )
    .filter(Boolean)

  if (!surfaces.length) {
    return
  }

  /*
   * Месяц относится к своей половине карточки: если у этой секции
   * режим выбора не включён — клик игнорируем.
   */
  const section = monthEl.closest('.popup-side-card')

  if (!section || !section.classList.contains('pf-mode')) {
    return
  }

  /*
   * Каждую поверхность переключаем независимо — как в списке
   * (onSideMonthClick): снять можно всегда, добавить — только свободный
   * месяц. В агрегированном месяце стороны это все её поверхности сразу.
   */
  surfaces.forEach(surface => {
    if (isMonthLocked(surface, monthFull)) {
      return
    }

    toggleMonth(surface, monthFull, surface.month_prices?.[monthFull])
  })

  const popupRoot =
    monthEl.closest('.popup') || monthEl.closest('.albion-popup')

  monthEl.classList.toggle(
    'is-selected',
    surfaces.some(surface => isMonthSelected(surfaceIdOf(surface), monthFull))
  )

  // Снят последний месяц — позиция ушла из портфеля: убираем рамки
  // со всех её месяцев, иначе они останутся висеть.
  surfaces.forEach(surface => {
    const id = surfaceIdOf(surface)

    if (!isSurfaceActive(id)) {
      clearSurfaceMonths(popupRoot, id)
    }
  })

  // Кнопки и pf-mode корня — по актуальному состоянию стора.
  refreshPopupState(popupRoot)
}

/* Ссылка из чата уже на открытой странице: переключаем режим без F5. */
watch(
  () => [route.query.chat, route.query.mode],
  ([chat, mode]) => {
    if (chat !== '1') return

    workspaceMode.value = mode === 'map' ? 'map' : 'list'
  }
)

async function reloadConstructions() {
  loading.value = true
  loadError.value = ''

  try {
    const data = await getConstructions()

    if (!Array.isArray(data)) {
      throw new Error('Некорректный ответ /api/constructions')
    }

    constructions.value = data

    // Месяцы берём из данных новой базы (а не жёсткого списка).
    setMonthsFromItems(constructions.value)

    if (route.query.chat === '1' && route.query.mode === 'map') {
      workspaceMode.value = 'map'
    } else if (route.query.chat === '1') {
      workspaceMode.value = 'list'
    }

    // Подтягиваем свежие цены/статусы выбранных месяцев из psql.
    syncWithConstructions(constructions.value)

    /*
     * Данные конструкций загружены/обновлены — сбрасываем кэш разметки
     * попапов: тот же id поверхности мог прийти с новыми ценой/фото/статусом.
     */
    clearPopupContentCache()
  } catch (error) {
    constructions.value = []
    loadError.value =
      'Не удалось загрузить конструкции. Проверьте соединение и повторите.'
    console.error('Albion page: ошибка загрузки конструкций:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)
  await reloadConstructions()

  if (!loadError.value) {
    console.log('Albion page: загружено', constructions.value.length)
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
  /* Высоту задаёт .app (100dvh минус шапка и подвал). Гасим min-height
     от Quasar q-page: иначе страница получает полную высоту вьюпорта,
     шапка и подвал добавляются сверху — лишняя прокрутка на их высоту. */
  height: auto;
  min-height: 0;
  overflow: hidden;
  background: #f3f5f6;
}

.app {
  /* Ровно экран минус реальные высоты шапки и подвала (меряются в MainLayout)
     — подвал встаёт сразу под контентом, без пустого зазора. */
  height: calc(
    100vh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px)
  );
  height: calc(
    100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px)
  );

  display: grid;
  grid-template-columns: 310px 1fr;

  overflow: hidden;
}

.workspace {
  position: relative;
  min-width: 0;

  background: #e9edef;
}

.workspace-state {
  position: absolute;
  inset: 0;
  z-index: 1600;
  display: grid;
  place-content: center;
  gap: 16px;
  padding: 24px;
  color: #17212b;
  font-size: 15px;
  text-align: center;
  background: rgba(233, 237, 239, 0.94);
}

.workspace-state--error {
  color: #8f1d16;
}

.workspace-state .slide-btn {
  justify-self: center;
}

/* Переключатель режимов */

.workspace-float {
  /* «Липкий» блок: остаётся на месте у верха области карты при прокрутке
     страницы (absolute уезжал вместе с содержимым). */
  position: sticky;
  top: 18px;
  left: 18px;
  z-index: 1500;

  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;

  width: max-content;
  max-width: calc(100% - 36px);

  margin: 18px 0 0 18px;
}

.workspace-mode-switch {
  display: flex;
  align-items: center;
  gap: 3px;

  padding: 5px;

  flex-shrink: 0;

  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e1e6e9;
  border-radius: 13px;

  box-shadow: 0 8px 28px rgba(23, 33, 43, 0.14);
  backdrop-filter: blur(12px);
}

.workspace-mode-switch button {
  height: 34px;
  padding: 0 14px;
  white-space: nowrap;

  border: 0;
  border-radius: 9px;

  background: transparent;
  color: #5b6873;

  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;

  cursor: pointer;

  transition:
    background 0.18s ease,
    color 0.18s ease;
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

  /* Колонка: закреплённая шапка + прокручивающийся список. Скроллится
     не вся область, а сам виртуальный список (см. .construction-list),
     поэтому шапка не двигается при прокрутке карточек. */
  display: flex;
  flex-direction: column;

  overflow: hidden;

  /* Верхний отступ оставляет запас под плавающий блок с переключателем
     режимов и поиском. */
  padding: 88px 28px 40px;

  background: #f4f6f7;
}

.list-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;

  flex-shrink: 0;

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

/* Переключатель числа колонок карточек (4/5/6). */
.list-columns {
  display: flex;
  align-items: center;
  gap: 4px;

  flex-shrink: 0;

  padding: 4px;

  background: #fff;
  border: 1px solid #e1e6e9;
  border-radius: 11px;
}

.list-columns button {
  min-width: 36px;
  height: 32px;

  border: 0;
  border-radius: 8px;

  background: transparent;
  color: #5b6873;

  font-size: 12px;
  font-weight: 800;

  cursor: pointer;

  transition:
    background 0.18s ease,
    color 0.18s ease;
}

.list-columns button.active {
  background: #17212b;
  color: #fff;
}

.list-columns button:hover:not(.active) {
  background: #f0f3f4;
  color: #17212b;
}

/* Кнопка «наверх»: прозрачный круг со стрелкой в правом нижнем углу
   области списка, появляется при прокрутке. Стоит над кнопкой-инструментом
   .map-tools (↺), чтобы не перекрываться с ней. */
.list-to-top {
  position: absolute;
  right: 24px;
  bottom: 80px;
  z-index: 20;

  width: 48px;
  height: 48px;

  display: flex;
  align-items: center;
  justify-content: center;

  border: 1px solid rgba(23, 33, 43, 0.12);
  border-radius: 50%;

  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);

  color: #17212b;

  cursor: pointer;

  box-shadow: 0 8px 24px rgba(23, 33, 43, 0.16);

  transition:
    background 0.18s ease,
    transform 0.18s ease;
}

.list-to-top:hover {
  background: rgba(255, 255, 255, 0.85);
  transform: translateY(-2px);
}

.construction-list {
  /* Корень q-virtual-scroll — единственный скроллер списка: занимает всё
     оставшееся под шапкой место (flex), поэтому прокручивается только
     область списка, а не страница целиком. */
  flex: 1 1 auto;
  min-height: 0;

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

  box-shadow: 0 8px 30px rgba(25, 35, 45, 0.06);

  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.construction-card:hover {
  transform: translateY(-2px);

  box-shadow: 0 14px 40px rgba(25, 35, 45, 0.1);
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
  letter-spacing: 0.25px;
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
  color: var(--albion-accent, #e12a1f);

  font-size: 20px;
  line-height: 1;

  font-weight: 900;

  letter-spacing: -0.5px;
}

/* основная цена бледная и зачёркнутая при наличии акционной */
.card-price-inline .price-value.is-old {
  color: #9aa5ac;
  text-decoration: line-through;
  font-weight: 700;
  letter-spacing: 0;
}

.card-price-inline .price-currency {
  color: var(--albion-accent, #e12a1f);

  font-size: 13px;
  line-height: 1;

  font-weight: 900;
}

.card-price-inline .price-period {
  color: #5b6873;

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
  color: #5f6c76;
  font-size: 9px;
  font-weight: 600;
}

.card-content {
  flex: 1;

  display: flex;
  flex-direction: column;

  padding: 14px 16px 15px;
}

/* Кнопка «Оставить заявку» убрана. */
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

  /* Название адреса — жирным. */
  font-weight: 700;

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

/* Сторона — серая плашка, как бейдж в попапе карты. */
.card-side-line {
  align-self: flex-start;

  display: inline-flex;
  align-items: center;
  gap: 4px;

  margin-top: 6px;
  padding: 3px 8px;

  border-radius: 6px;
  background: #e6e9ec;

  color: #6b7680;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.card-side-line b {
  color: #3d3f43;
  font-weight: 900;
}

/* Блоки внутри карточки точки — по одному на формат стороны */

.card-blocks {
  display: flex;
  flex-direction: column;
  gap: 14px;

  margin-top: 10px;

  /* Занимаем всю доступную высоту карточки, чтобы блок «Портфель» и
     строка «подсветка/статика/динамика» вставали по нижнему краю. */
  flex: 1;
}

.card-block {
  display: flex;
  flex-direction: column;

  padding-top: 12px;

  border-top: 1px solid #edf0f2;
}

/* Последний блок тянется вниз и прижимает «Портфель» к нижнему краю. */
.card-block:last-child {
  flex: 1;
}

.card-block:first-child {
  padding-top: 0;

  border-top: 0;
}

.card-block .card-side-line {
  margin-top: 6px;
}

/* Город/адрес/сторона идут под форматом; над городом — «пустая строка». */
.card-block .card-head {
  margin-top: 16px;
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

/* В последнем блоке «Портфель» + фичи прижаты к низу карточки. */
.card-block:last-child .card-portfolio {
  margin-top: auto;

  padding-top: 10px;
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
  letter-spacing: 0.3px;

  transition: 0.15s ease;
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
.card-block.pf-mode .card-month:not(.is-locked) {
  cursor: pointer;
}

.card-block.pf-mode .card-month:not(.is-locked):hover {
  filter: brightness(0.96);
}

/* Занятый/резервный месяц выбрать нельзя. */
.card-block.pf-mode .card-month.is-locked {
  cursor: not-allowed;
  opacity: 0.5;
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
  letter-spacing: 0.04em;
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
  color: #5f6c76;

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

  color: #5f6c76;

  font-size: 9px;
  line-height: 1;

  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.card-price .price-main {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.card-price .price-value {
  color: #17212b;

  font-size: 32px;
  line-height: 0.95;

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

  color: #5b6873;

  font-size: 10px;
  line-height: 1;

  font-weight: 700;
}

.card-meta .size-value {
  color: #34414a;
  font-weight: 600;
}

.empty-state {
  flex: 1 1 auto;
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

  color: #5b6873;

  font-weight: 800;
}

.empty-state h2 {
  margin: 14px 0 5px;

  color: #17212b;

  font-size: 20px;
}

.empty-state p {
  margin: 0 0 18px;

  color: #5b6873;

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

  box-shadow: 0 10px 30px rgba(25, 35, 45, 0.14);
}

@media (max-width: 760px) {
  /* На узком экране колонки встают друг под друга. Базовые правила
     (fixed height + overflow: hidden у .app и .advertising-page) при этом
     схлопывали рабочую область в полоску: её дети позиционированы
     absolute и собственной высоты не имеют. Поэтому на мобильном
     отпускаем высоту и задаём рабочей области явную высоту. */
  .advertising-page {
    height: auto;
    min-height: 100%;
    overflow: visible;
  }

  .app {
    grid-template-columns: 1fr;
    height: auto;
    overflow: visible;
  }

  /* Панель фильтров сверху — ограничиваем высоту, чтобы не выдавливать карту. */
  .app :deep(.filters-sidebar) {
    max-height: 60vh;
    overflow-y: auto;
  }

  /* Рабочая область (карта/список) получает реальную высоту экрана. */
  .workspace {
    height: 78vh;
    min-height: 460px;
  }

  .list-view {
    padding: 30px 16px;
  }

  /* Переключатель колонок на узком экране не нужен — число колонок
     определяется шириной автоматически. */
  .list-columns {
    display: none;
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

/* Одна плашка внизу по центру: статус точки + радиус — в один ряд. */
.point-controls {
  position: absolute;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  z-index: 950;

  display: flex;
  align-items: stretch;

  width: min(760px, calc(100% - 24px));

  background: rgba(255, 255, 255, 0.97);
  border: 1px solid #dfe4e7;
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(23, 33, 43, 0.18);
  overflow: hidden;
}

/* Левая колонка — статус точки (подтверждение выбора). */
.point-confirmation {
  flex: 0 0 auto;

  display: flex;
  flex-direction: column;
  justify-content: center;

  min-width: 240px;
  max-width: 300px;
  padding: 14px 18px;

  border-right: 1px solid #e7ebee;

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
  flex: 0 0 auto;

  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;

  min-width: 200px;
  max-width: 280px;
  padding: 14px 18px;

  border-right: 1px solid #e7ebee;

  font-size: 11px;
  font-weight: 700;
  color: #17212b;
  text-align: center;
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

/* Правая колонка — радиус поиска (внутри общей плашки). */
.point-radius-float {
  flex: 1 1 320px;

  display: flex;
  flex-direction: column;
  justify-content: center;

  min-width: 200px;
  padding: 14px 16px;
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
  color: #66727c;
  font-size: 8px;
  font-weight: 700;
}

.point-radius-marks span.active {
  color: #17212b;
}

/* Узкий экран: панель по-прежнему внизу по центру, но колонки в столбик. */
@media (max-width: 720px) {
  .point-controls {
    flex-direction: column;
    width: min(460px, calc(100% - 24px));
  }

  .point-confirmation,
  .point-fixed-badge {
    min-width: 0;
    max-width: none;
    border-right: 0;
    border-bottom: 1px solid #e7ebee;
  }

  .point-radius-float {
    min-width: 0;
  }
}

/* Мишень поиска: двойное кольцо (тёмное + акцент) и центральная точка. */
.point-map-crosshair::before {
  content: '';

  position: absolute;
  inset: 3px;

  border: 2px solid rgba(23, 33, 43, 0.8);
  border-radius: 50%;

  box-shadow: 0 1px 6px rgba(23, 33, 43, 0.18);
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

  box-shadow: 0 1px 4px rgba(23, 33, 43, 0.4);
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
    box-shadow: 0 0 0 8px rgba(225, 42, 31, 0.12);
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

/* Месяцы всегда принимают наведение: иначе браузер не показывает
   всплывающую подсказку со статусом месяца (native title), как на
   карточках списка. Клик вне режима выбора всё равно игнорируется
   обработчиком (нужен класс .pf-mode у секции), поэтому pointer-events
   можно держать включённым постоянно. */
.popup .popup-months,
.popup .popup-month {
  pointer-events: auto;
}

/* Курсор-рука — только там, где месяц реально кликабелен. */
.popup-side-card.pf-mode .popup-month {
  cursor: pointer;
}

/* В режиме выбора занятый месяц выбрать нельзя. */
.popup-side-card.pf-mode .popup-month.is-locked {
  cursor: not-allowed;
  opacity: 0.5;
}

.popup-side-card.pf-mode .popup-month:hover {
  filter: brightness(0.96);
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

  margin-top: 5px;
}

.popup-pf-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;

  padding: 4px 10px;

  border: 1px solid #dce2e6;
  border-radius: 8px;

  background: #fff;
  color: #52606a;

  cursor: pointer;

  font-family: inherit;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.3px;

  transition: 0.15s ease;
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

/*
 * Quasar q-page-container по умолчанию имеет min-height:100vh и стоит ПОД
 * шапкой. Вместе с подвалом это давало лишнюю прокрутку страницы ровно на
 * высоту шапки+подвала, из-за чего плавающие элементы уезжали. Ограничиваем
 * контейнер по высоте ТОЛЬКО для этой страницы и ТОЛЬКО на десктопе (на
 * мобильном контент в столбик и должен прокручиваться).
 * Не-scoped: элемент вне компонента, у него нет data-v-атрибута.
 */
@media (min-width: 761px) {
  body:has(.advertising-page) .q-page-container {
    height: calc(
      100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px)
    );
    min-height: 0;
    overflow: hidden;
  }
}
</style>
