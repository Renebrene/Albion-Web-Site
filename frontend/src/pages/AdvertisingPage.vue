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
        :point-filter="pointFilterInfo"
        :count-label="sidebarCountLabel"
        @focus-city="focusCity"
        @remove-point="changeSelectedPoint"
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
        :point-fixed="pointSelectionState === 'fixed'"
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
        <div
          class="workspace-float"
          :class="{ 'workspace-float--chat': chatResultsActive }"
        >
          <div class="workspace-mode-switch">
            <button
              type="button"
              :class="{ active: workspaceMode === 'map' }"
              @click="setWorkspaceMode('map')"
            >
              <span class="mode-label">Интерактивная карта</span>
              <span class="mode-label-short">Карта</span>
            </button>
            <button
              type="button"
              :class="{ active: workspaceMode === 'point' }"
              :disabled="chatResultsActive"
              :title="
                chatResultsActive
                  ? 'Недоступно в результатах умного чата'
                  : undefined
              "
              @click="setWorkspaceMode('point')"
            >
              <span class="mode-label">Поиск по точке и адресу</span>
              <span class="mode-label-short">Точка</span>
            </button>
            <button
              type="button"
              :class="{ active: workspaceMode === 'list' }"
              @click="setWorkspaceMode('list')"
            >
              <span class="mode-label">Список</span>
              <span class="mode-label-short">Список</span>
            </button>
          </div>

          <MapSearch
            v-model="topSearchValue"
            :count="toolbarCount"
            :show-mode="workspaceMode === 'point'"
            :mode="topSearchMode"
            :error="topSearchError"
            :loading="workspaceMode === 'point' && addressLoading"
            :disabled="chatResultsActive"
            @update:mode="topSearchMode = $event"
            @select-suggestion="onTopSuggestionSelect"
            @search="onTopSearch"
          />

          <div
            v-if="workspaceMode === 'list'"
            class="workspace-columns"
            role="group"
            aria-label="Число колонок"
          >
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

          <!--
            Результаты умного чата: плашка живёт, пока в адресе есть chat=1
            и чат вернул хотя бы одну конструкцию. «Сбросить» возвращает
            обычный каталог; сама история чата не трогается.
          -->
          <div
            v-if="chatResultsActive"
            class="chat-results-plaque"
            role="status"
          >
            <span class="chat-results-text">
              Результаты умного чата · {{ chatResultsLabel }}
            </span>

            <button type="button" @click="resetChatResults">Сбросить</button>
          </div>
        </div>

        <!-- КАРТА И ПОИСК ПО ТОЧКЕ -->
        <!--
          Один экземпляр MapView на оба режима: переключение вкладок не
          размонтирует карту, поэтому центр, зум и загруженный регион
          сохраняются. В «Списке» карта скрыта через v-show.
        -->
        <div
          v-show="workspaceMode === 'map' || workspaceMode === 'point'"
          ref="mapWrapRef"
          class="map-wrap"
        >
          <MapView
            ref="mapViewRef"
            :constructions="mapConstructions"
            :all-constructions="constructions"
            :selected-months="selectedMonths"
            :search-point="mapSearchPoint"
            :search-radius="mapSearchRadius"
            @map-center="updatePointCoordinatesFromMap"
            @search-point-hover="onSearchPointHover"
            @search-point-open="openPointTab"
          />

          <!--
            Чип «Убрать точку»: появляется при наведении на пин точки (или на
            сам чип) и убирает точку. Клик по пину при этом ничего не убирает —
            он переводит в закладку «Поиск по точке».
          -->
          <button
            v-if="pointChipVisible && pointChipPosition"
            type="button"
            class="point-chip"
            :style="{
              left: `${pointChipPosition.x}px`,
              top: `${pointChipPosition.y}px`
            }"
            @mouseenter="pointChipHovered = true"
            @mouseleave="pointChipHovered = false"
            @click="resetSearchPoint"
          >
            Убрать точку
          </button>

          <template v-if="workspaceMode === 'point'">
            <div
              v-if="pointSelectionState !== 'fixed'"
              ref="pointTargetRef"
              class="point-map-crosshair"
              :class="{
                dragging: isDraggingPointTarget,
                pending: pointSelectionState === 'pending'
              }"
              :style="
                pointTargetPosition
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
              <!--
                Метка-домик: остриё снизу — это и есть точка поиска.
                Координаты в панели берутся под остриём, а не под центром.
              -->
              <svg
                class="point-target-pin"
                :viewBox="`0 0 ${SEARCH_POINT_ICON.width} ${SEARCH_POINT_ICON.height}`"
                :width="SEARCH_POINT_ICON.width"
                :height="SEARCH_POINT_ICON.height"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  class="point-target-pin__body"
                  :d="SEARCH_POINT_ICON.body"
                />
                <path
                  class="point-target-pin__house"
                  :d="SEARCH_POINT_ICON.house"
                />
                <path
                  class="point-target-pin__door"
                  :d="SEARCH_POINT_ICON.door"
                />
              </svg>
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

              <div
                class="point-radius-float"
                :class="{ 'is-inactive': pointSelectionState !== 'fixed' }"
              >
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
                  :disabled="pointSelectionState !== 'fixed'"
                  :title="
                    pointSelectionState === 'fixed'
                      ? 'Радиус поиска вокруг зафиксированной точки'
                      : 'Сначала зафиксируйте точку'
                  "
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
          </template>
        </div>

        <!-- СПИСОК -->

        <div
          v-if="workspaceMode === 'list'"
          ref="listViewRef"
          class="list-view"
        >
          <!-- Шапка списка закреплена: заголовок и переключатель колонок
               не двигаются, карточки прокручиваются под ними. -->
          <div
            v-if="pointSelectionState === 'fixed'"
            class="list-point-note list-point-note--standalone"
          >
            <span>В радиусе {{ formatRadius(pointRadius) }} от точки</span>
            <button type="button" @click="changeSelectedPoint">
              Показать весь каталог
            </button>
          </div>

          <!--
            Список рендерится строками сетки без виртуализации: карточки
            сохраняют естественную высоту. Если на мобильных появятся
            просадки — вернёмся к «Показать ещё» или DynamicScroller.
          -->
          <div
            v-if="listPoints.length"
            ref="listScrollerRef"
            class="construction-list"
            @scroll.passive="onListScroll"
          >
            <!-- Строка сетки: columns колонок, повторяет прежний auto-fill. -->
            <div
              v-for="row in visibleListRows"
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
                      :class="`card-block--${block.kind}`"
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
                          sizes="(max-width: 760px) 92vw, 320px"
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
                            @click.stop="setCardMedia(point, blockIndex, 'map')"
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
                                  'is-locked': isSideMonthLocked(
                                    block,
                                    month.full
                                  )
                                }
                              ]"
                              :disabled="isSideMonthLocked(block, month.full)"
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
                                    'is-locked': isMonthLocked(row, month.full)
                                  }
                                ]"
                                :disabled="isMonthLocked(row, month.full)"
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
                            getCardMonthState(blockPrimary(block), month.full),
                            {
                              'is-selected':
                                surfaceIdOf(blockPrimary(block)) !== null &&
                                isMonthSelected(
                                  blockPrimary(block).id,
                                  month.full
                                ),
                              'is-locked': isMonthLocked(
                                blockPrimary(block),
                                month.full
                              )
                            }
                          ]"
                          :disabled="
                            isMonthLocked(blockPrimary(block), month.full)
                          "
                          :aria-pressed="
                            surfaceIdOf(blockPrimary(block)) !== null &&
                            isMonthSelected(blockPrimary(block).id, month.full)
                          "
                          :title="
                            getMonthStatusLabel(blockPrimary(block), month.full)
                          "
                          @click="
                            onCardMonthClick(block, blockPrimary(block), month)
                          "
                        >
                          {{ month.short }}
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

            <div v-if="hasMoreRows" class="list-load-more">
              <button type="button" @click="loadMoreRows">
                Показать ещё
              </button>

              <span>
                показано {{ visibleListRows.length }} из
                {{ listRows.length }} строк
              </span>
            </div>
          </div>

          <div v-else class="empty-state">
            <div class="empty-icon"> 0 </div>

            <h2> Ничего не найдено </h2>

            <p> Измените параметры фильтра или очистите поиск. </p>

            <button type="button" @click="resetAllFilters">
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
          <!-- Сброс точки — только в закладке «Точка»: обнуляет координаты,
               радиус и адрес поиска по точке. -->
          <button
            v-if="workspaceMode === 'point'"
            class="tool"
            type="button"
            title="Сбросить точку"
            aria-label="Сбросить точку"
            @click="resetSearchPoint"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="6.5"
                stroke="currentColor"
                stroke-width="1.8"
              />
              <path
                d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
              />
              <path
                d="M6.8 17.2 17.2 6.8"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
              />
            </svg>
          </button>

          <button
            class="tool"
            :title="
              linkCopied
                ? 'Ссылка скопирована'
                : 'Скопировать ссылку на фильтры'
            "
            @click="shareCurrentLink"
          >
            {{ linkCopied ? '✓' : '⤴' }}
          </button>

          <button
            class="tool"
            title="Сбросить фильтры"
            @click="resetAllFilters"
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
import { urlStateMode, urlStateTokenFormat } from '../config/urlStateMode'
import { decodeUrlState, encodeUrlState } from '../utils/urlState'
import { decodePortfolioLink } from '../utils/portfolioLink'
import { computed, ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FiltersSidebar from '../components/filters/FiltersSidebar.vue'
import MapSearch from '../components/workspace/MapSearch.vue'
import PointSearchPanel from '../components/workspace/PointSearchPanel.vue'
import MapView from '../map/MapView.vue'
import { clearPopupContentCache } from '../map/popupContent'
import { SEARCH_POINT_ICON } from '../map/searchPointIcon'

import { getConstructions } from '../services/api'
import { geocodeAddress, reverseGeocode } from '../services/geoApi'

import { useConstructionsFilter } from '../composables/useConstructionsFilter'

import { useChatWorkspace } from '../composables/useChatWorkspace'
import { usePortfolio } from '../composables/usePortfolio'
import {
  photoLabel,
  sanitizeFileName,
  usePhotoViewer
} from '../composables/usePhotoViewer'
import { mapDebug } from '../map/mapDebug'

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

/* Месяц стороны — состояние по стороне целиком (логика в usePortfolio). */
function isSideMonthSelected(block, month) {
  return isPortfolioSideMonthSelected(block?.items || [], month)
}

/*
 * Клик по месяцу свёрнутой стороны: в портфель уходит ОДНА позиция —
 * сторона, конкретная поверхность (A(1), A(2)…) не хранится
 * (см. toggleSideMonth в composables/usePortfolio.js).
 */
function onSideMonthClick(block, month) {
  toggleSideMonth(block?.items || [], month.full)
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
 * API отдаёт два превью и large:
 *   photo       — card 640px (2× ширины карточки),
 *   photo_thumb — thumb 400px (портфель и узкие сетки),
 *   photo_large — large 1600px (просмотр/скачивание).
 * Любой вариант может отсутствовать — подставляем соседний.
 */
function photoThumb(item) {
  return item?.photo_thumb || item?.photo || item?.photo_large || ''
}

function photoCard(item) {
  return item?.photo || item?.photo_thumb || item?.photo_large || ''
}

function photoSrcset(item) {
  const parts = []

  const thumb = item?.photo_thumb
  if (thumb) {
    parts.push(`${thumb} 400w`)
  }

  const card = item?.photo
  if (card) {
    parts.push(`${card} 640w`)
  }

  const large = item?.photo_large
  if (large) {
    parts.push(`${large} 1600w`)
  }

  return parts.join(', ')
}

/* ------------------------------------------- карта-схема на карточке */

/*
 * На карточке можно переключать, что показывать: фото или карту-схему.
 * Выбор запоминается по ключу карточки и блока, чтобы не сбиваться при
 * при смене строк. Если чего-то из двух изображений нет — показываем
 * то, что есть, без переключателя.
 *
 * `item.map` — ссылка на страницу Яндекс.Диска, а не изображение:
 * в src/srcset она не годится (блокируется CSP и не рендерится), поэтому
 * работаем только с локальными вариантами map_thumb/map_card/map_large.
 */
const cardMedia = ref({})

function blockMap(item) {
  return item?.map_large || item?.map_card || item?.map_thumb || ''
}

/* Фото/карта карточки — 640px (2× реальной ширины 200–320 CSS-пикселей). */
function cardMap(item) {
  return item?.map_card || item?.map_thumb || item?.map_large || ''
}

function mapSrcset(item) {
  const parts = []

  if (item?.map_thumb) {
    parts.push(`${item.map_thumb} 400w`)
  }

  if (item?.map_card) {
    parts.push(`${item.map_card} 640w`)
  }

  if (item?.map_large) {
    parts.push(`${item.map_large} 1600w`)
  }

  return parts.join(', ')
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
    ? cardMap(item)
    : photoCard(item)
}

function cardImageSrcset(point, block, blockIndex) {
  if (cardImageMode(point, block, blockIndex) === 'map') {
    return mapSrcset(blockPrimary(block)) || undefined
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
 * Портфель — общий стор приложения. Месяцы на карточке кликабельны
 * всегда: свободный добавляется, выбранный снимается.
 */
const {
  isMonthSelected,
  toggleMonth,
  toggleSideMonth,
  syncWithConstructions,
  applyShared,
  isSideMonthSelected: isPortfolioSideMonthSelected,
  isSideMonthLocked: isPortfolioSideMonthLocked,
  items: portfolioItems,
  selectionMode: portfolioSelectionMode
} = usePortfolio()

/*
 * Разметка поп-апа карты статична, а классы «активно/выбрано» ставятся
 * вручную. Поэтому при внешнем изменении портфеля (очистка в панели или
 * личном кабинете, удаление позиции) приводим открытые поп-апы к
 * актуальному состоянию — иначе подсветка остаётся.
 */
/* Отпечаток позиций портфеля — без режима выбора (например, для ссылки). */
function portfolioStateKey(list) {
  return list
    .map(
      item =>
        `${item?.surfaceId}:${Object.keys(item?.months || {})
          .sort()
          .join('|')}`
    )
    .sort()
    .join(',')
}

const portfolioSignature = computed(() => {
  const items = portfolioStateKey(portfolioItems.value)

  const modes = Object.keys(portfolioSelectionMode)
    .filter(key => portfolioSelectionMode[key])
    .sort()
    .join(',')

  return `${items}::${modes}`
})

function refreshOpenPopups() {
  /*
   * `.popup` — корень разметки из popupContent.js. Он есть и в Leaflet,
   * и в балуне Яндекс.Карт; селектор с .leaflet-popup не находил
   * яндексовские попапы, и подсветка портфеля в них устаревала.
   */
  document.querySelectorAll('.popup').forEach(root => refreshPopupState(root))
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
  const mapUrl = item?.map_large || item?.map_card || item?.map_thumb || ''

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

/* Месяц стороны: выбранный можно снять, остальные — только свободные. */
function isSideMonthLocked(block, monthFull) {
  return isPortfolioSideMonthLocked(block?.items || [], monthFull)
}

/* Месяц можно ВЫБРАТЬ только если он свободен (снять — всегда можно). */
function isMonthLocked(surface, monthFull) {
  const id = surfaceIdOf(surface)

  if (id === null || isMonthSelected(id, monthFull)) {
    return false
  }

  return !isFree(surface, monthFull)
}

/* Клик по месяцу: свободный добавляет, выбранный снимает. */
function onCardMonthClick(block, surface, month) {
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

/* Значения точки по умолчанию — к ним возвращает сброс точки. */
const DEFAULT_POINT_COORDINATES = '47.2357, 39.7015'
const DEFAULT_POINT_RADIUS = 1000

const pointCoordinates = ref(DEFAULT_POINT_COORDINATES)
const pointAddress = ref('')
const addressLoading = ref(false)
const addressError = ref('')
/* Номер последнего geocode-запроса: старые ответы не должны перезаписывать новые. */
let addressRequestSeq = 0
/* То же для обратного геокодера (адрес по координатам точки). */
let reverseRequestSeq = 0
const pointRadius = ref(DEFAULT_POINT_RADIUS)

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

/* Показываются результаты точки: режим точки или список, открытый из него. */
const pointResultsActive = computed(
  () => workspaceMode.value === 'point' || pointSelectionState.value === 'fixed'
)
/*
 * Пиксельная позиция метки относительно .map-wrap. null — метка стоит
 * по центру (CSS 50%/50%), пока её не перетащили и не задали якорь.
 */
const pointTargetPosition = ref(null)

/*
 * Географический якорь метки. После того как метку отпустили, она
 * «приклеивается» к месту на карте: при панорамировании и зуме позиция
 * пересчитывается из этих координат, а не остаётся в пикселях экрана.
 * null — метки ещё не ставили, она привязана к центру вида.
 */
const pointAnchor = ref(null)

const isDraggingPointTarget = ref(false)
const pointTargetPointerOffset = ref({ x: 0, y: 0 })
const pointTargetRef = ref(null)
const mapWrapRef = ref(null)

/* Экранная точка (clientX/Y) → позиция метки внутри .map-wrap. */
function placePointTargetAtScreenPoint(screenX, screenY) {
  const wrap = mapWrapRef.value

  if (!wrap) {
    return
  }

  const rect = wrap.getBoundingClientRect()

  /* left/top позиционируются от padding-края (за вычетом рамки). */
  pointTargetPosition.value = {
    x: screenX - rect.left - wrap.clientLeft,
    y: screenY - rect.top - wrap.clientTop
  }
}

/* Ставит метку по её географическому якорю под текущий вид карты. */
function syncPointTargetToAnchor() {
  const anchor = pointAnchor.value

  if (!anchor) {
    return
  }

  const screen = mapViewRef.value?.getScreenPointAtCoordinates(
    anchor.lat,
    anchor.lng
  )

  if (screen) {
    placePointTargetAtScreenPoint(screen.x, screen.y)
  }
}

function updatePointCoordinatesFromMap(center) {
  syncPointChipPosition()

  /*
   * После фиксации точка не должна «уезжать» вместе с картой: результаты
   * считаются вокруг fixedSearchPoint, а координаты в поле — иначе они
   * показывали бы уже другую точку.
   */
  if (
    workspaceMode.value !== 'point' ||
    pointSelectionState.value === 'fixed'
  ) {
    return
  }

  /* Пока метку тащат, её положением управляет movePointTarget. */
  if (isDraggingPointTarget.value) {
    return
  }

  /*
   * Метка приклеена к карте: держим её на месте координат и не
   * пересчитываем координаты по экрану — они уже точные.
   */
  if (pointAnchor.value) {
    syncPointTargetToAnchor()
    return
  }

  /*
   * Метку ещё не ставили — она в центре вида. Координаты берём под её
   * остриём (нижний центр габаритов), с фоллбэком на центр карты.
   */
  let lat = Number(center?.lat)
  let lng = Number(center?.lng)

  const target = pointTargetRef.value

  if (target && mapViewRef.value) {
    const rect = target.getBoundingClientRect()
    const coordinates = mapViewRef.value.getCoordinatesAtScreenPoint(
      rect.left + rect.width / 2,
      rect.top + rect.height
    )

    if (coordinates) {
      lat = Number(coordinates.lat)
      lng = Number(coordinates.lng)
    }
  }

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

  /*
   * Опорная точка — остриё пина (нижний центр), а не центр габаритов:
   * иначе при перетаскивании метка «прыгает» вверх на половину высоты.
   */
  pointTargetPointerOffset.value = {
    x: event.clientX - (targetRect.left + targetRect.width / 2),
    y: event.clientY - (targetRect.top + targetRect.height)
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

  /*
   * Координаты — под остриём метки (x/y считаются от угла карты), а не
   * под курсором: метку можно тащить за любое место корпуса.
   */
  const coordinates = mapViewRef.value?.getCoordinatesAtScreenPoint(
    rect.left + x,
    rect.top + y
  )

  if (!coordinates) {
    return
  }

  /*
   * Запоминаем якорь сразу, ещё во время перетаскивания: после отпускания
   * метка уже привязана к месту на карте и переживёт панорамирование и зум.
   */
  pointAnchor.value = {
    lat: coordinates.lat,
    lng: coordinates.lng
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
    addressError.value = 'Укажите широту и долготу через запятую.'
    return
  }

  addressError.value = ''
  fixedSearchPoint.value = {
    lat: parts[0],
    lng: parts[1]
  }

  pointSelectionState.value = 'fixed'
  pointAddress.value = ''
  void fillAddressForPoint(parts[0], parts[1])
}

function changeSelectedPoint() {
  /* Отменяем незавершённый обратный геокодер: его адрес уже неактуален. */
  reverseRequestSeq += 1

  /*
   * Метку возвращаем туда, где точка стоит на карте СЕЙЧАС. Пиксельные
   * координаты перетаскивания к этому моменту устарели: пока точка была
   * зафиксирована, карту могли сдвинуть или приблизить — и метка
   * появлялась бы в старом месте экрана, «отвязанной» от карты.
   */
  const point = fixedSearchPoint.value

  if (point) {
    /*
     * Возвращённая в правку точка тоже приклеена к карте, а не к пикселям
     * экрана: якорь запоминаем, позицию считаем под текущий вид.
     */
    pointAnchor.value = { lat: point.lat, lng: point.lng }
    syncPointTargetToAnchor()
  }

  fixedSearchPoint.value = null
  pointSelectionState.value = 'idle'
}

/*
 * Сброс точки (плавающая кнопка в закладке «Точка»): снимаем фиксацию,
 * возвращаем радиус к значению по умолчанию, очищаем адрес, а мишень
 * ставим в центр текущего вида — точку можно ставить заново.
 */
function resetSearchPoint() {
  /* Незавершённые геокодеры больше не нужны: их ответы устарели. */
  reverseRequestSeq += 1
  addressRequestSeq += 1

  fixedSearchPoint.value = null
  pointSelectionState.value = 'idle'
  pointRadius.value = DEFAULT_POINT_RADIUS
  pointAddress.value = ''
  addressError.value = ''

  const wrap = mapWrapRef.value
  const api = mapViewRef.value
  const rect = wrap ? wrap.getBoundingClientRect() : null

  /* Центр вида: мишень остаётся на экране, а не уезжает за край. */
  const center =
    rect && api
      ? api.getCoordinatesAtScreenPoint(
          rect.left + rect.width / 2,
          rect.top + rect.height / 2
        )
      : null

  if (center) {
    pointAnchor.value = { lat: center.lat, lng: center.lng }
    pointCoordinates.value = `${center.lat.toFixed(6)}, ${center.lng.toFixed(6)}`
    syncPointTargetToAnchor()

    return
  }

  pointAnchor.value = null
  pointTargetPosition.value = null
  pointCoordinates.value = DEFAULT_POINT_COORDINATES
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
 * если точка зафиксирована — показываем результаты поиска по точке
 * (например, после «Открыть список»). Ввод текста в строку поиска
 * в этих режимах снимает фиксацию — см. topSearchValue.
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

/*
 * Режим «результаты чата»: чат передал id найденных конструкций, и страница
 * показывает их вместо каталога. Фильтры и поиск по точке в этом режиме
 * намеренно не применяются — поэтому поиск по точке неактивен, а строка
 * поиска отключена, чтобы не выглядела рабочей.
 */
const chatResultsActive = computed(
  () => route.query.chat === '1' && chatResultIds.value.length > 0
)

const chatResultsLabel = computed(() => {
  const value = displayedConstructions.value.length

  return `${value} ${sidesPhrase(value)}`
})

/* «Сбросить»: убираем chat/mode из адреса — каталог снова с фильтрами. */
function resetChatResults() {
  const query = { ...route.query }

  delete query.chat
  delete query.mode

  router.replace({ path: route.path, query })
}

/* В результатах чата точки нет — если в ней стояли, уводим в карту. */
watch(chatResultsActive, active => {
  if (active && workspaceMode.value === 'point') {
    setWorkspaceMode('map')
  }
})

/* Заголовок левой панели в режиме «Список»: количество сторон. */
const sidebarCountLabel = computed(() => {
  const value = displayedConstructions.value.length

  return `${value} ${sidesPhrase(value)}`
})

/* Данные для единственного экземпляра MapView: в точке — радиус, иначе фильтр. */
const mapConstructions = computed(() =>
  workspaceMode.value === 'point'
    ? pointFilteredConstructions.value
    : displayedConstructions.value
)

/*
 * Чип «Убрать точку» у пина зафиксированной точки: показываем при наведении
 * на пин или на сам чип. Позиция — экранная точка пина в координатах
 * .map-wrap (как у перетаскиваемой мишени), пересчитывается при движении
 * карты вместе с координатами точки.
 */
const pointPinHovered = ref(false)
const pointChipHovered = ref(false)
const pointChipPosition = ref(null)

/* Чип показываем, только пока курсор на пине или на самом чипе. */
const pointChipVisible = computed(
  () =>
    pointSelectionState.value === 'fixed' &&
    !!fixedSearchPoint.value &&
    (pointPinHovered.value || pointChipHovered.value)
)

/*
 * Город точки: по ближайшей к ней конструкции каталога (обратный геокодер
 * даёт адрес, но не всегда город). Берём только город из справочника,
 * иначе фильтр не применится.
 */
const pointCity = computed(() => {
  const point = fixedSearchPoint.value

  if (!point) {
    return ''
  }

  let nearest = null
  let nearestDistance = Infinity

  for (const item of constructions.value) {
    const lat = Number(item?.lat)
    const lng = Number(item?.lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      continue
    }

    const distance = (lat - point.lat) ** 2 + (lng - point.lng) ** 2

    if (distance < nearestDistance) {
      nearestDistance = distance
      nearest = item
    }
  }

  const city = String(nearest?.city || '').trim()

  return city && cities.value.includes(city) ? city : ''
})

/*
 * Город определяется точкой: как только точка зафиксирована — в закладке
 * «Точка», в списке или на карте, — ставим в фильтр город этой точки.
 * Иначе фильтр городов расходился с точкой: выдача сужена радиусом, а
 * в «Городах / районах» не отмечено ничего.
 */
watch(pointCity, city => {
  if (!city) {
    return
  }

  if (pointSelectionState.value !== 'fixed') {
    return
  }

  if (sameSelection(selectedCities.value, [city])) {
    return
  }

  syncingPointCities = true
  selectedCities.value = [city]

  nextTick(() => {
    syncingPointCities = false
  })
})

/* Данные строки-фильтра «Поиск по точке» в сайдбаре. */
const pointFilterInfo = computed(() => {
  const point = fixedSearchPoint.value

  if (!point || pointSelectionState.value !== 'fixed') {
    return null
  }

  return {
    title: `Радиус ${formatRadius(pointRadius.value)} от точки`,
    address: String(pointAddress.value || '').trim()
  }
})

/*
 * Между пином и чипом есть зазор в несколько пикселей: без задержки чип
 * успевал исчезнуть ровно на пути курсора. Даём 220 мс — за это время
 * указатель либо доходит до чипа (тогда таймер снимает его mouseenter),
 * либо уходит совсем.
 */
let pointChipHideTimer = null

function onSearchPointHover(hovered) {
  if (pointChipHideTimer) {
    clearTimeout(pointChipHideTimer)
    pointChipHideTimer = null
  }

  if (hovered === true) {
    pointPinHovered.value = true

    return
  }

  pointChipHideTimer = setTimeout(() => {
    pointChipHideTimer = null
    pointPinHovered.value = false
  }, 220)
}

/* Клик по пину — переход в закладку «Поиск по точке». */
function openPointTab() {
  setWorkspaceMode('point')
}

function syncPointChipPosition() {
  const point = fixedSearchPoint.value
  const wrap = mapWrapRef.value
  const api = mapViewRef.value

  if (!point || !wrap || !api) {
    pointChipPosition.value = null

    return
  }

  const screen = api.getScreenPointAtCoordinates(point.lat, point.lng)

  if (!screen) {
    pointChipPosition.value = null

    return
  }

  const rect = wrap.getBoundingClientRect()

  pointChipPosition.value = {
    x: screen.x - rect.left - wrap.clientLeft,
    /* Остриё пина внизу, сам пин выше: чип ставим над ним. */
    y: screen.y - rect.top - wrap.clientTop - SEARCH_POINT_ICON.height - 6
  }
}

watch(
  [pointSelectionState, () => fixedSearchPoint.value],
  () => {
    syncPointChipPosition()
  },
  { immediate: true }
)

/*
 * Маркер точки: в режиме «Точка» — всегда (мишень видно и во время правки),
 * в карте и списке — пока точка зафиксирована. Выдача там сужена радиусом
 * (см. displayedConstructions), и это сужение должно быть видно.
 */
const searchPointVisible = computed(
  () => workspaceMode.value === 'point' || pointSelectionState.value === 'fixed'
)

const mapSearchPoint = computed(() =>
  searchPointVisible.value ? fixedSearchPoint.value : null
)

/*
 * Круг радиуса — только у ЗАФИКСИРОВАННОЙ точки: пока точку правят
 * («ИЗМЕНИТЬ ТОЧКУ»), круг не рисуется и слайдер выключен, но значение
 * радиуса сохраняется и возвращается вместе с фиксацией.
 */
const mapSearchRadius = computed(() =>
  pointSelectionState.value === 'fixed' ? pointRadius.value : 0
)

/*
 * В точке счётчик показывает найденное вокруг неё, в карте/списке — по базе.
 * Пока точка не зафиксирована, результата нет — вместо нуля прочерк, чтобы
 * «0» не читался как «в районе ничего не найдено».
 */
const toolbarCount = computed(() => {
  if (
    workspaceMode.value === 'point' &&
    pointSelectionState.value !== 'fixed'
  ) {
    return '—'
  }

  return workspaceMode.value === 'point'
    ? pointFilteredConstructions.value.length
    : displayedConstructions.value.length
})

/*
 * Переключение вкладок. Зафиксированная точка НЕ снимается: результаты
 * поиска по точке — те же данные, что нужны в «Списке» и на «Карте», и
 * раньше при переходе по закладкам они пропадали (список показывал весь
 * каталог). Сужение больше не молчаливое: в списке видна плашка «В радиусе
 * … от точки», на карте — маркер точки и круг радиуса.
 *
 * Снять фиксацию можно явно: «Изменить точку» в закладке «Точка»,
 * «Показать весь каталог» в списке, «Сбросить фильтры» в карте и списке.
 */
function setWorkspaceMode(mode) {
  workspaceMode.value = mode
}

/* Из панели точки: открыть закладку «Список» с найденными результатами. */
function openListFromPoint() {
  /* Пустая выдача: открывать нечего (кнопка в панели тоже выключена). */
  if (!pointFilteredConstructions.value.length) {
    return
  }

  workspaceMode.value = 'list'
}

/*
 * Сброс фильтров. В карте/списке дополнительно снимаем фиксацию точки:
 * иначе скрытый радиус продолжит сужать выдачу. В point-режиме точка
 * остаётся — там радиус виден и является частью запроса.
 */
/* Обратная связь кнопки «Поделиться» на 2 секунды. */
const linkCopied = ref(false)
let linkCopiedTimer = null

function buildShareUrl() {
  const query = buildFilterQuery()
  const params = new URLSearchParams()

  Object.entries(query).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach(item => params.append(key, String(item)))
    } else if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })

  const search = params.toString()

  return `${window.location.origin}${route.path}${search ? `?${search}` : ''}`
}

async function shareCurrentLink() {
  const url = buildShareUrl()

  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(url)
    } else {
      window.prompt('Скопируйте ссылку:', url)
      return
    }

    linkCopied.value = true

    if (linkCopiedTimer) {
      clearTimeout(linkCopiedTimer)
    }

    linkCopiedTimer = setTimeout(() => {
      linkCopied.value = false
      linkCopiedTimer = null
    }, 2000)
  } catch {
    window.prompt('Скопируйте ссылку:', url)
  }
}

function resetAllFilters() {
  /* Сброс отменяет и отложенные фильтры карты/списка. */
  stashedSearchQuery = ''
  searchStashed = false
  stashedCities = []
  citiesStashed = false

  resetFilters()

  if (workspaceMode.value !== 'point') {
    changeSelectedPoint()
    pointAddress.value = ''
    addressError.value = ''
  }
}

/*
 * Поиск в верхней плавающей строке.
 * В режиме точки — геокодер: подсказки и геокодирование адреса (или
 * координаты по переключателю). В карте и списке — фильтр по базе:
 * город, улица, формат.
 */
const topSearchMode = ref('address')

/* Ошибка поиска показывается только в режиме точки — там работает геокодер. */
const topSearchError = computed(() =>
  workspaceMode.value === 'point' ? addressError.value : ''
)

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
      addressError.value = ''

      if (topSearchMode.value === 'coords') {
        pointCoordinates.value = value
      } else {
        pointAddress.value = value
      }
    } else {
      /* В карте и списке строка поиска — обычный фильтр по базе.
         Зафиксированная ранее точка не должна сужать его выдачу. */
      if (pointSelectionState.value === 'fixed') {
        /* Пользователь начал новый поиск — отложенные старые фильтры не возвращаем. */
        searchStashed = false
        stashedSearchQuery = ''
        citiesStashed = false
        stashedCities = []
        changeSelectedPoint()
      }

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
    addressError.value =
      'Введите две координаты через запятую: широта, долгота.'
    return
  }

  const [lat, lng] = parts

  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    addressError.value = 'Координаты вне допустимого диапазона.'
    return
  }

  addressError.value = ''
  pointCoordinates.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`

  fixedSearchPoint.value = {
    lat,
    lng
  }

  pointSelectionState.value = 'fixed'
  pointAddress.value = ''
  mapViewRef.value?.setMapCenter(lat, lng, 14)
  void fillAddressForPoint(lat, lng)
}

async function fillAddressForPoint(lat, lng) {
  const seq = ++reverseRequestSeq

  try {
    const result = await reverseGeocode(lat, lng)

    /* Пока ждали ответ, точку могли изменить или снять. */
    if (seq !== reverseRequestSeq) {
      return
    }

    const current = fixedSearchPoint.value

    if (
      !current ||
      Math.abs(current.lat - lat) > 1e-6 ||
      Math.abs(current.lng - lng) > 1e-6
    ) {
      return
    }

    if (result?.address && !String(pointAddress.value || '').trim()) {
      pointAddress.value = result.address
    }
  } catch (error) {
    /* Обратный геокодер не должен мешать поиску по точке. */
    console.warn('Albion reverse geocode:', error)
  }
}

/* Выбор подсказки в верхней строке: сразу геокодируем выбранный адрес. */
function onTopSuggestionSelect(suggestion) {
  if (workspaceMode.value !== 'point') {
    return
  }

  const address = String(
    suggestion?.display_name || suggestion?.query || ''
  ).trim()

  if (!address) {
    return
  }

  topSearchMode.value = 'address'
  pointAddress.value = address
  void executeAddressSearch()
}

async function executeAddressSearch() {
  const seq = ++addressRequestSeq
  /* Новый адресный поиск отменяет незавершённый reverse-geocode. */
  reverseRequestSeq += 1

  const address = String(pointAddress.value || '').trim()

  if (!address) {
    addressLoading.value = false
    addressError.value = 'Введите адрес.'
    return
  }

  addressLoading.value = true
  addressError.value = ''

  try {
    const result = await geocodeAddress(address)

    /* Пока ждали ответ, пользователь мог запустить более новый поиск. */
    if (seq !== addressRequestSeq) {
      return
    }

    const lat = Number(result.lat)
    const lng = Number(result.lon)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      throw new Error('Геокодер вернул некорректные координаты')
    }

    pointAddress.value = result.address || address
    pointCoordinates.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`
    fixedSearchPoint.value = { lat, lng }
    pointSelectionState.value = 'fixed'
    mapViewRef.value?.setMapCenter(lat, lng, 14)
  } catch (error) {
    if (seq !== addressRequestSeq) {
      return
    }

    addressError.value =
      error?.message || 'Не удалось найти адрес в Ростовской области.'
  } finally {
    if (seq === addressRequestSeq) {
      addressLoading.value = false
    }
  }
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
 * Синхронизация фильтров с URL.
 *
 * До завершения гидратации обратная запись выключена: авто-выбор всех
 * городов/форматов иначе затирает city/type из ссылки раньше, чем они
 * применятся. После гидратации URL служит источником истины и при
 * Back/Forward, а изменения фильтров пишутся обратно с debounce.
 */
const urlHydrated = ref(false)
const initialAddressFromUrl = String(route.query.address || '').trim()
const MANAGED_FILTER_KEYS = [
  'city',
  'type',
  'address',
  'months',
  'monthLogic',
  'mode',
  'lat',
  'lng',
  'radius',
  'addr',
  's'
]
let urlWriteTimer = null
/* Состояние карты/списка, отложенное на время point-режима. */
let stashedSearchQuery = ''
let searchStashed = false
let stashedCities = []
let citiesStashed = false
let syncingPointCities = false

if (initialAddressFromUrl) {
  searchQuery.value = initialAddressFromUrl
}

function queryValues(value) {
  const list = Array.isArray(value) ? value : value == null ? [] : [value]

  return list.map(item => String(item).trim()).filter(Boolean)
}

/*
 * Число из адреса. Пустой параметр (`?lat=&lng=`) — это NaN, а не 0:
 * иначе `Number('')` фиксировал точку в (0, 0) и поиск уходил в океан.
 */
function readUrlNumber(value) {
  const text = String(value ?? '').trim()

  return text ? Number(text) : Number.NaN
}

function sameSelection(left, right) {
  if (left.length !== right.length) {
    return false
  }

  const set = new Set(left)

  return right.every(item => set.has(item))
}

/* Стабильное сравнение query: порядок ключей и мультизначений не важен. */
function canonicalQuery(query) {
  const entries = Object.keys(query)
    .sort()
    .map(key => {
      const value = query[key]

      return [
        key,
        Array.isArray(value)
          ? value.map(item => String(item)).sort()
          : value == null
            ? ''
            : String(value)
      ]
    })

  return JSON.stringify(entries)
}

function applyFiltersFromUrl() {
  /*
   * Компактный токен ?s=... и читаемые параметры ?city=... — один и тот
   * же набор полей. Если токен битый, молча откатываемся к читаемой схеме.
   */
  const compactState = route.query.s ? decodeUrlState(route.query.s) : null
  const source = compactState || {}

  /*
   * Точка из URL. Применяем до городов: pointResultsActive должен быть
   * уже истинным, иначе городской фильтр скроет часть выдачи.
   */
  const lat = compactState
    ? Number(source.point?.lat)
    : readUrlNumber(route.query.lat)
  const lng = compactState
    ? Number(source.point?.lng)
    : readUrlNumber(route.query.lng)
  const hasPoint = Number.isFinite(lat) && Number.isFinite(lng)

  if (hasPoint) {
    const previous = fixedSearchPoint.value
    const changed =
      !previous ||
      Math.abs(previous.lat - lat) > 1e-6 ||
      Math.abs(previous.lng - lng) > 1e-6

    fixedSearchPoint.value = { lat, lng }
    pointCoordinates.value = `${lat.toFixed(6)}, ${lng.toFixed(6)}`
    pointSelectionState.value = 'fixed'

    const radius = compactState
      ? Number(source.radius)
      : Number(route.query.radius)

    if (Number.isFinite(radius) && radius > 0) {
      pointRadius.value = radius
    }

    const addressFromUrl = String(
      compactState ? source.address || '' : route.query.addr || ''
    ).trim()

    if (addressFromUrl) {
      pointAddress.value = addressFromUrl
      topSearchMode.value = 'address'
    } else if (changed) {
      pointAddress.value = ''
    }

    if (changed) {
      void centerOnPointWhenReady(lat, lng)
    }
  } else if (pointSelectionState.value === 'fixed') {
    fixedSearchPoint.value = null
    pointSelectionState.value = 'idle'
  }

  /*
   * Пока показываются результаты точки, город из URL не применяем:
   * он относится к карте/списку и не должен скрыто сужать выдачу.
   * Пустой набор = «все города», неизвестный город — тоже без фильтра.
   */
  if (!pointResultsActive.value) {
    const requestedCities = queryValues(
      compactState ? source.cities : route.query.city
    )

    /*
     * Пустой параметр означает «все города». Не переписываем выбор, если все
     * города уже отмечены: адрес пишет city только для частичного набора,
     * поэтому после дебаунса отметки снимались сами собой.
     */
    const allCitiesSelected = selectedCities.value.length >= cities.value.length

    if (requestedCities.length || !allCitiesSelected) {
      const nextCities = requestedCities.length
        ? cities.value.filter(city => requestedCities.includes(city))
        : []
      const citiesChanged = !sameSelection(selectedCities.value, nextCities)

      if (citiesChanged) {
        selectedCities.value = nextCities
      }

      if (citiesChanged && nextCities.length === 1) {
        focusCityWhenReady(nextCities[0])
      }
    }
  }

  const requestedTypes = queryValues(
    compactState ? source.types : route.query.type
  )
  const matchedTypes = requestedTypes.length
    ? types.value.filter(type => requestedTypes.includes(type))
    : [...types.value]
  const nextTypes =
    requestedTypes.length && !matchedTypes.length
      ? [...types.value]
      : matchedTypes

  if (!sameSelection(selectedTypes.value, nextTypes)) {
    selectedTypes.value = nextTypes
  }

  const availableMonths = months.value.map(month => month.value)
  const requestedMonths = queryValues(
    compactState ? source.months : route.query.months
  ).filter(month => availableMonths.includes(month))

  if (!sameSelection(selectedMonths.value, requestedMonths)) {
    selectedMonths.value = requestedMonths
  }

  const nextLogic =
    String(
      compactState ? source.monthLogic : route.query.monthLogic || ''
    ).toUpperCase() === 'AND'
      ? 'AND'
      : 'OR'

  if (monthLogic.value !== nextLogic) {
    monthLogic.value = nextLogic
  }

  /*
   * Пока показываются результаты точки (режим точки или список, открытый
   * из него), строка поиска по базе не применяется: адрес из URL не
   * должен скрыто сужать выдачу.
   */
  if (!pointResultsActive.value) {
    const nextAddress = String(
      compactState ? source.searchQuery || '' : route.query.address || ''
    ).trim()

    if (String(searchQuery.value || '').trim() !== nextAddress) {
      searchQuery.value = nextAddress
    }
  }

  /*
   * Режим вкладки. Для chat-ссылок режим по-прежнему задаёт отдельный
   * watcher (map/list), чтобы не ломать их поведение.
   */
  if (route.query.chat !== '1') {
    const requestedMode = String(
      compactState ? source.mode || '' : route.query.mode || ''
    )

    if (
      requestedMode === 'map' ||
      requestedMode === 'point' ||
      requestedMode === 'list'
    ) {
      /* Точка из адреса живёт вместе с закладкой: состояние применяется выше. */
      setWorkspaceMode(requestedMode)
    } else if (workspaceMode.value !== 'map') {
      setWorkspaceMode('map')
    }
  }
}

function buildFilterQuery() {
  /* Сохраняем chat/mode и посторонние параметры (utm и т.п.). */
  const query = { ...route.query }

  for (const key of MANAGED_FILTER_KEYS) {
    delete query[key]
  }

  /*
   * Пока результаты точки активны, в URL сохраняем городской фильтр
   * карты/списка из отложенного набора — он вернётся после снятия точки.
   */
  const cityValues =
    pointResultsActive.value && citiesStashed
      ? stashedCities
      : selectedCities.value

  if (cityValues.length && cityValues.length < cities.value.length) {
    query.city = cityValues.length === 1 ? cityValues[0] : [...cityValues]
  }

  const typeValues = selectedTypes.value

  if (typeValues.length && typeValues.length < types.value.length) {
    query.type = typeValues.length === 1 ? typeValues[0] : [...typeValues]
  }

  if (selectedMonths.value.length) {
    query.months =
      selectedMonths.value.length === 1
        ? selectedMonths.value[0]
        : [...selectedMonths.value]
  }

  /*
   * «И/ИЛИ» пишем независимо от выбранных месяцев: иначе переключение на «И»
   * при пустом наборе месяцев не попадало в адрес, и после первой же записи
   * адреса тумблер возвращался на «ИЛИ».
   */
  if (monthLogic.value === 'AND') {
    query.monthLogic = 'AND'
  }

  /*
   * Пока показываются результаты точки, searchQuery очищен, но адрес
   * карты/списка сохраняем в URL из отложенной строки — чтобы он
   * вернулся, когда точка будет снята.
   */
  const address = String(
    pointResultsActive.value ? stashedSearchQuery : searchQuery.value
  ).trim()

  if (address) {
    query.address = address
  }

  /*
   * Компактный режим: одно поле ?s= вместо набора параметров.
   * Если токен не помещается в лимит, откатываемся к читаемой схеме.
   */
  if (urlStateMode.value === 'compact') {
    try {
      query.s = encodeUrlState(
        {
          mode: workspaceMode.value,
          cities:
            cityValues.length && cityValues.length < cities.value.length
              ? cityValues
              : [],
          types:
            typeValues.length && typeValues.length < types.value.length
              ? typeValues
              : [],
          months: selectedMonths.value,
          monthLogic: monthLogic.value,
          searchQuery: address,
          address: pointAddress.value,
          point: fixedSearchPoint.value,
          radius: pointRadius.value
        },
        urlStateTokenFormat.value
      )

      /* Чат-ссылка читает режим из отдельного параметра — сохраняем его. */
      if (route.query.chat === '1') {
        query.mode = workspaceMode.value
      }

      return query
    } catch {
      /* слишком длинное состояние — ниже сработает читаемая схема */
    }
  }

  /*
   * Режим вкладки: map — значение по умолчанию. Для chat-ссылок пишем
   * всегда, чтобы ссылка из чата сохраняла карту/список после reload.
   */
  if (workspaceMode.value !== 'map' || route.query.chat === '1') {
    query.mode = workspaceMode.value
  }

  /* Зафиксированная точка и радиус — часть состояния поиска. */
  if (fixedSearchPoint.value) {
    query.lat = Number(fixedSearchPoint.value.lat).toFixed(6)
    query.lng = Number(fixedSearchPoint.value.lng).toFixed(6)

    if (Number(pointRadius.value) > 0) {
      query.radius = String(pointRadius.value)
    }

    const pointAddressText = String(pointAddress.value || '').trim()

    if (pointAddressText) {
      query.addr = pointAddressText
    }
  }

  return query
}

function scheduleUrlWrite() {
  if (!urlHydrated.value) {
    return
  }

  if (urlWriteTimer) {
    clearTimeout(urlWriteTimer)
  }

  urlWriteTimer = setTimeout(() => {
    urlWriteTimer = null

    if (!urlHydrated.value) {
      return
    }

    const query = buildFilterQuery()

    if (canonicalQuery(route.query) === canonicalQuery(query)) {
      return
    }

    router.replace({
      path: route.path,
      query,
      hash: route.hash
    })
  }, 300)
}

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
 * Список рендерится строками сетки с естественной высотой карточек.
 * Число колонок повторяет auto-fill minmax(300px, 1fr) с gap 18px и
 * зависит от реальной ширины области списка (ResizeObserver ниже).
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

/* Прокрутка списка: сам контейнер и признак «список прокручен». */
const listScrollerRef = ref(null)
const listScrolled = ref(false)

/* Ленивая подгрузка: сначала 12 строк сетки, дальше по 12 при скролле. */
const INITIAL_LIST_ROWS = 12
const LIST_ROWS_STEP = 12
const visibleRowCount = ref(INITIAL_LIST_ROWS)

const visibleListRows = computed(() =>
  listRows.value.slice(0, visibleRowCount.value)
)

const hasMoreRows = computed(
  () => visibleRowCount.value < listRows.value.length
)

function loadMoreRows() {
  if (!hasMoreRows.value) {
    return
  }

  visibleRowCount.value = Math.min(
    visibleRowCount.value + LIST_ROWS_STEP,
    listRows.value.length
  )
}

function onListScroll(event) {
  const el = event.target

  listScrolled.value = el.scrollTop > 0

  /* Подгружаем следующую порцию заранее, за ~800px до конца. */
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 800) {
    loadMoreRows()
  }
}

function resetListWindow() {
  visibleRowCount.value = INITIAL_LIST_ROWS

  nextTick(() => {
    listScrollerRef.value?.scrollTo({ top: 0 })
  })
}

function scrollListToTop() {
  listScrollerRef.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

/* При смене режима список монтируется заново сверху — сбрасываем признак
   прокрутки, чтобы кнопка «наверх» не висела зря. */
watch(workspaceMode, mode => {
  listScrolled.value = false

  if (mode === 'list') {
    resetListWindow()
  }
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

/* Фильтр/поиск или число колонок изменились — начинаем список заново. */
watch(listPoints, resetListWindow)
watch(listColumns, resetListWindow)

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
 * Центрирование карты на городе/точке — после готовности карты и данных.
 * Галочку в фильтре ставит гидратация ниже.
 *
 * Вместо rAF-опроса с жёстким лимитом ждём whenReady(): если карта не
 * инициализировалась, MapView всё равно разрешает ожидание и показывает
 * ошибку. Токен отменяет устаревшие запросы (быстрые клики по городам).
 */
let pageAlive = true
let focusRequestToken = 0

async function focusCityWhenReady(city) {
  const token = ++focusRequestToken

  await nextTick()

  const view = mapViewRef.value
  const hasData =
    Array.isArray(constructions.value) && constructions.value.length > 0

  if (!view || !hasData || !pageAlive) {
    return
  }

  await view.whenReady()

  if (!pageAlive || token !== focusRequestToken) {
    return
  }

  /* Даём Vue разложить данные в пропсы карты, затем центрируем. */
  await nextTick()

  if (!pageAlive || token !== focusRequestToken) {
    return
  }

  view.focusCity(city)
}

async function centerOnPointWhenReady(lat, lng) {
  const token = ++focusRequestToken

  await nextTick()

  const view = mapViewRef.value

  if (!view || !pageAlive) {
    return
  }

  await view.whenReady()

  if (!pageAlive || token !== focusRequestToken) {
    return
  }

  await nextTick()

  if (!pageAlive || token !== focusRequestToken) {
    return
  }

  view.setMapCenter(lat, lng, 14)
}

/*
 * Гидратация: применяем URL один раз, после загрузки справочников, и
 * только затем включаем обратную запись.
 */
watch(
  [cities, types],
  () => {
    if (urlHydrated.value || !constructions.value.length) {
      return
    }

    applyFiltersFromUrl()
    urlHydrated.value = true
  },
  { immediate: true }
)

/* Back/Forward и любые изменения route.query применяем к фильтрам. */
watch(
  () => route.query,
  () => {
    if (!urlHydrated.value) {
      return
    }

    applyFiltersFromUrl()
  },
  { deep: true }
)

// URL ← фильтры (только после гидратации; запись с debounce)
watch(
  [
    selectedCities,
    selectedTypes,
    selectedMonths,
    monthLogic,
    searchQuery,
    workspaceMode,
    fixedSearchPoint,
    pointRadius,
    pointAddress
  ],
  scheduleUrlWrite,
  { deep: true }
)
// Конец URL ← фильтры

/*
 * Строка поиска по базе не должна скрыто сужать point-режим.
 *
 * При входе в точку запоминаем её и очищаем фильтр. Возвращаем, когда
 * результаты точки перестали быть активны: при выходе вкладкой или после
 * снятия точки в списке. «Открыть список» сохраняет точку, поэтому поиск
 * там остаётся очищенным. Адрес в URL сохраняется (см. buildFilterQuery).
 */
watch([workspaceMode, pointSelectionState], ([mode, state], [previousMode]) => {
  if (mode === 'point' && previousMode !== 'point') {
    if (!searchStashed) {
      stashedSearchQuery = String(searchQuery.value || '').trim()
      searchStashed = true
    }

    searchQuery.value = ''

    /*
     * Город в point-режиме определяется адресом/точкой: городской фильтр
     * карты откладываем и снимаем, чтобы он не сужал выдачу.
     */
    if (!citiesStashed) {
      stashedCities = [...selectedCities.value]
      citiesStashed = true
    }

    syncingPointCities = true
    selectedCities.value = []
    nextTick(() => {
      syncingPointCities = false
    })

    return
  }

  if (mode !== 'point' && state !== 'fixed') {
    if (searchStashed) {
      searchQuery.value = stashedSearchQuery
      stashedSearchQuery = ''
      searchStashed = false
    }

    if (citiesStashed) {
      syncingPointCities = true
      selectedCities.value = [...stashedCities]
      stashedCities = []
      citiesStashed = false
      nextTick(() => {
        syncingPointCities = false
      })
    }
  }
})

/*
 * Пользователь изменил города, пока открыт список из точки: его выбор
 * важнее отложенного фильтра, поэтому восстановление отменяем.
 */
watch(
  selectedCities,
  () => {
    if (syncingPointCities) {
      return
    }

    if (citiesStashed) {
      citiesStashed = false
      stashedCities = []
    }
  },
  { deep: true }
)

/*
 * Делегирование кликов для попапов карты.
 *
 * Разметку кнопок и месяцев строит popupContent.js; попап — статичная
 * HTML-строка, поэтому реактивность Vue до неё не достаёт и состояние
 * (режим/выбор) переключаем напрямую через классы DOM.
 */
/*
 * Приводит DOM попапа к актуальному состоянию после переключения:
 * выбранные месяцы, доступность клика, aria-атрибуты.
 */
function refreshPopupState(popupRoot) {
  if (!popupRoot) {
    return
  }

  popupRoot.querySelectorAll('.popup-month').forEach(monthEl => {
    const raw = monthEl.getAttribute('data-pf-month') || ''
    const sep = raw.indexOf('|')
    let selected = false
    let canPick = false

    if (sep > 0) {
      const ids = raw
        .slice(0, sep)
        .split(',')
        .map(value => value.trim())
        .filter(Boolean)
      const month = raw.slice(sep + 1)

      /* Ячейка стороны несёт все её поверхности — состояние по стороне. */
      const surfaces = ids
        .map(id =>
          constructions.value.find(
            construction => String(construction?.id) === id
          )
        )
        .filter(Boolean)

      selected = isPortfolioSideMonthSelected(surfaces, month)

      /* Занятый месяц нельзя выбрать, но уже выбранный можно снять. */
      canPick = !isPortfolioSideMonthLocked(surfaces, month)
    }

    monthEl.classList.toggle('is-selected', selected)
    monthEl.classList.toggle('is-locked', !canPick)
    monthEl.setAttribute('aria-pressed', String(selected))
    monthEl.disabled = !canPick
    monthEl.setAttribute('aria-disabled', String(!canPick))
  })
}

function onDocumentClick(event) {
  const target = event.target

  if (!(target instanceof Element)) {
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
   * агрегирован по стороне и несёт ВСЕ её поверхности: по ним считается
   * состояние ячейки, а клик добавляет в портфель одну позицию-сторону
   * (одна позиция на сторону — см. toggleSideMonth).
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

  toggleSideMonth(surfaces, monthFull)

  const popupRoot =
    monthEl.closest('.popup') || monthEl.closest('.albion-popup')

  monthEl.classList.toggle(
    'is-selected',
    isPortfolioSideMonthSelected(surfaces, monthFull)
  )

  refreshPopupState(popupRoot)
}

/* Ссылка из чата уже на открытой странице: переключаем режим без F5. */
watch(
  () => [route.query.chat, route.query.mode],
  ([chat, mode]) => {
    if (chat !== '1') return

    /*
     * Режим из чат-ссылки: результаты чата — самостоятельная выборка, точка
     * её не сужает (см. displayedConstructions), поэтому фиксацию не трогаем.
     */
    setWorkspaceMode(mode === 'map' ? 'map' : 'list')
  }
)

/*
 * Портфель из ссылки (?pf=…).
 *
 * Ссылка переносит только портфель — позиции и месяцы (utils/portfolioLink.js),
 * фильтры остаются в ?s=/?city=…. Свой портфель получателя молча не затираем:
 * если он не пуст и отличается, спрашиваем — «ОК» меняет его целиком,
 * «Отмена» дополняет текущий.
 *
 * Вызывается один раз, после загрузки каталога и до syncWithConstructions:
 * позиции собираются из данных каталога, поэтому сначала нужен список
 * конструкций, а цены/статусы дозаполнит синхронизация.
 * Параметр из адреса убираем сразу — иначе он переживёт перезагрузку
 * и вопрос задастся повторно.
 */
let sharedPortfolioHandled = false

function dropSharedPortfolioParam() {
  if (!route.query.pf) {
    return
  }

  const query = { ...route.query }

  delete query.pf

  router.replace({ path: route.path, query, hash: route.hash })
}

function applySharedPortfolioFromUrl() {
  if (sharedPortfolioHandled) {
    return
  }

  sharedPortfolioHandled = true

  const raw = route.query.pf

  if (!raw) {
    return
  }

  const shared = decodePortfolioLink(raw)

  dropSharedPortfolioParam()

  if (!shared) {
    return
  }

  /* Тот же портфель уже собран — спрашивать не о чем. */
  const fromLink = shared.items
    .map(item => `${item.surfaceId}:${[...item.months].sort().join('|')}`)
    .sort()
    .join(',')

  if (portfolioStateKey(portfolioItems.value) === fromLink) {
    return
  }

  const current = portfolioItems.value.length

  const replace =
    current === 0 ||
    window.confirm(
      `Заменить текущий портфель (позиций: ${current}) портфелем из ссылки? ` +
        '«Отмена» — дополнить текущий.'
    )

  const result = applyShared(shared, constructions.value, { replace })

  if (result.skipped) {
    window.alert(
      `Из ссылки недоступно позиций: ${result.skipped}. Возможно, конструкция больше не в каталоге.`
    )
  }
}

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

    // Портфель из ссылки (?pf=…): собираем позиции из свежего каталога.
    applySharedPortfolioFromUrl()

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
    mapDebug('Albion page: загружено', constructions.value.length)
  }
})

onBeforeUnmount(() => {
  if (pointChipHideTimer) {
    clearTimeout(pointChipHideTimer)
    pointChipHideTimer = null
  }

  pageAlive = false
  focusRequestToken += 1

  document.removeEventListener('click', onDocumentClick)

  if (listResizeObserver) {
    listResizeObserver.disconnect()
    listResizeObserver = null
  }

  if (urlWriteTimer) {
    clearTimeout(urlWriteTimer)
    urlWriteTimer = null
  }

  if (linkCopiedTimer) {
    clearTimeout(linkCopiedTimer)
    linkCopiedTimer = null
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
  z-index: 1500;

  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 10px;

  /* Переключатель и поиск — одна строка на всю ширину рабочей области.
     Поиск забирает всё оставшееся место (см. MapSearch). */
  width: calc(100% - 36px);
  max-width: calc(100% - 36px);

  margin: 18px 0 0 18px;
}

/*
 * Плашка результатов умного чата: висит под переключателем режимов, пока
 * в адресе chat=1 и чат вернул хотя бы одну конструкцию.
 */
/* Место под плашку внутри плавающего блока (она стоит по его низу). */
.workspace-float--chat {
  padding-bottom: 46px;
}

/*
 * Список позиционирован абсолютно от верха рабочей области и не знает о
 * высоте плавающего блока — плашке добавляем место вручную, чтобы она не
 * накрывала первые карточки (72px штатного отступа + 46px под плашку).
 */
.workspace-float--chat ~ .list-view {
  padding-top: 118px;
}

.chat-results-plaque {
  position: absolute;
  left: 0;
  bottom: 0;
  z-index: 1500;

  display: flex;
  align-items: center;
  gap: 12px;

  padding: 8px 8px 8px 14px;

  border-radius: 11px;

  background: #17212b;
  color: #fff;

  box-shadow: 0 8px 28px rgba(23, 33, 43, 0.24);

  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.chat-results-plaque button {
  padding: 6px 12px;

  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 8px;

  background: transparent;
  color: #fff;

  cursor: pointer;

  font-family: inherit;
  font-size: 11px;
  font-weight: 800;
}

.chat-results-plaque button:hover {
  background: rgba(255, 255, 255, 0.12);
}

/* Переключатель колонок в строке поиска — освобождает шапку списка. */
.workspace-columns {
  display: flex;
  align-items: center;
  gap: 2px;

  flex-shrink: 0;

  padding: 3px;

  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e1e6e9;
  border-radius: 11px;

  box-shadow: 0 8px 28px rgba(23, 33, 43, 0.14);
}

.workspace-columns button {
  min-width: 30px;
  height: 32px;

  border: 0;
  border-radius: 8px;

  background: transparent;
  color: #5b6873;

  font-size: 11px;
  font-weight: 800;

  cursor: pointer;
}

.workspace-columns button.active {
  background: #17212b;
  color: #fff;
}

.workspace-columns button:hover:not(.active) {
  background: #f0f3f4;
  color: #17212b;
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

.workspace-mode-switch button:hover:not(.active):not(:disabled) {
  background: #f0f3f4;
  color: #17212b;
}

/* В результатах чата поиск по точке недоступен. */
.workspace-mode-switch button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

/* Короткие подписи — только на узких экранах, чтобы строка не переносилась. */
.mode-label-short {
  display: none;
}

@media (max-width: 1100px) {
  .workspace-mode-switch {
    padding: 4px;
  }

  .workspace-mode-switch button {
    height: 32px;
    padding: 0 9px;
    font-size: 10px;
  }

  /* Короткие подписи освобождают место поиску. */
  .mode-label {
    display: none;
  }

  .mode-label-short {
    display: inline;
  }
}

@media (max-width: 560px) {
  .workspace-float {
    width: calc(100% - 24px);
    max-width: calc(100% - 24px);
    margin: 12px 0 0 12px;
    gap: 6px;
  }

  .workspace-mode-switch {
    gap: 2px;
    padding: 3px;
  }

  .workspace-mode-switch button {
    height: 30px;
    padding: 0 7px;
    font-size: 9px;
  }

  /* На самых узких экранах счётчик уступает место полю ввода, а
     переключатель «Координаты/Адрес» дублируется в панели слева. */
  .workspace-float :deep(.count),
  .workspace-float :deep(.search-mode) {
    display: none;
  }
}

.map-wrap {
  position: absolute;
  inset: 0;
}

.list-view {
  position: absolute;
  inset: 0;

  /* Колонка: закреплённая шапка + прокручивающийся список. Скроллится
     не вся область, а сам список (см. .construction-list), поэтому
     шапка не двигается при прокрутке карточек. */
  display: flex;
  flex-direction: column;

  overflow: hidden;

  /* Верхний отступ оставляет запас под плавающий блок с переключателем
     режимов, поиском и колонками; шапки списка больше нет. */
  padding: 72px 28px 40px;

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

/* Список открыт из point-режима: показываем, что выдача сужена радиусом. */
.list-point-note--standalone {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.list-point-note {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;

  margin-top: 9px;

  color: #5b6873;
  font-size: 12px;
}

.list-point-note button {
  padding: 4px 9px;

  border: 1px solid #d6dde1;
  border-radius: 7px;

  background: #fff;
  color: #17212b;

  font-size: 11px;
  font-weight: 700;

  cursor: pointer;
}

.list-point-note button:hover {
  border-color: #17212b;
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
  /* Единственный скроллер списка: занимает всё оставшееся под шапкой
     место (flex), поэтому прокручивается только область списка. */
  flex: 1 1 auto;
  min-height: 0;

  overflow-y: auto;

  display: block;
}

/* Одна строка — сетка из listColumns колонок,
   как прежний auto-fill minmax(300px, 1fr). */
.list-load-more {
  display: flex;
  flex-direction: column;
  align-items: center;

  gap: 8px;

  padding: 10px 0 28px;

  color: #68757e;
  font-size: 12px;
}

.list-load-more button {
  padding: 10px 20px;

  border: 1px solid #dfe5e9;
  border-radius: 10px;

  background: #fff;
  color: #17212b;

  cursor: pointer;

  font-size: 12px;
  font-weight: 800;
}

.list-load-more button:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

.construction-row {
  display: grid;

  grid-template-columns: repeat(3, 1fr);

  gap: 18px;

  /* Строка по высоте самой высокой карточки — без фиксированной высоты. */
  padding-bottom: 18px;
}

.construction-card {
  /* Кегль внутри карточки зависит от её ширины, а не от вьюпорта:
     при 5–6 колонках и на узком мониторе текст уменьшается. */
  container-type: inline-size;
  container-name: construction-card;

  overflow: hidden;

  display: flex;
  flex-direction: column;

  /* Высота — по содержимому: блоки не растягиваются на всю строку. */
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

  /* Меньше воздуха между форматом и городом — место уходит адресу. */
  margin-bottom: 4px;

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
  min-height: 0;

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
  /* Три строки вместо двух: освободили место, уменьшив отступы. */
  min-height: 3.45em;

  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;

  color: #17212b;

  font-size: 16px;
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
  min-height: 0;
}

.card-block {
  display: flex;
  flex-direction: column;

  min-height: 0;

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

/* Город/адрес/сторона идут под форматом; отступ уменьшен, чтобы
   адрес занимал до трёх строк без роста карточки. */
.card-block .card-head {
  margin-top: 4px;
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

/* Месяцы кликабельны всегда, если месяц свободен. */
.card-month:not(.is-locked) {
  cursor: pointer;
}

.card-month:not(.is-locked):hover {
  filter: brightness(0.96);
}

/* Занятый/резервный месяц выбрать нельзя. */
.card-month.is-locked {
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

  min-height: 0;
  overflow-y: auto;

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

/*
 * Адаптивный кегль карточки. Контейнерные запросы реагируют на реальную
 * ширину карточки: она меняется при выборе 4/5/6 колонок, изменении
 * размера окна и на разных мониторах.
 */
@container construction-card (max-width: 300px) {
  .card-content {
    padding: 12px 13px 13px;
  }

  .card-address-main {
    font-size: 15px;
  }

  .card-type {
    font-size: 11px;
  }

  .card-place {
    font-size: 11px;
  }

  .card-price-inline .price-value,
  .card-promo-price .promo-price-value {
    font-size: 18px;
  }

  .card-price-inline .price-currency {
    font-size: 12px;
  }

  .card-side-line,
  .card-dynamic-side,
  .card-pf-toggle,
  .card-features,
  .feature-label {
    font-size: 9px;
  }
}

@container construction-card (max-width: 250px) {
  .card-content {
    padding: 10px 11px 12px;
  }

  .card-address-main {
    font-size: 14px;
  }

  .card-type {
    font-size: 10px;
  }

  .card-price-inline .price-value,
  .card-promo-price .promo-price-value {
    font-size: 16px;
  }

  .card-price-inline .price-currency {
    font-size: 11px;
  }

  .card-price-inline .price-period,
  .card-promo-price .promo-price-note {
    font-size: 8px;
  }

  .card-pf-toggle {
    font-size: 8px;
  }
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

  display: flex;
  flex-direction: column;
  gap: 8px;
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
    /* Отступ под плавающий блок «режимы + поиск», иначе шапка списка
       уходит под него. */
    padding: 76px 16px 24px;
  }

  /* Переключатель колонок на узком экране не нужен — число колонок
     определяется шириной автоматически. */
  .list-columns,
  .workspace-columns {
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

/*
 * Чип «Убрать точку» у пина: полупрозрачный, без белой окантовки —
 * подсказка Leaflet тут не подходит (закрывается при уходе курсора).
 */
.point-chip {
  position: absolute;
  z-index: 640;

  padding: 6px 10px;

  border: 0;
  border-radius: 8px;

  background: rgba(23, 33, 43, 0.72);

  color: #fff;
  cursor: pointer;

  font-size: 11px;
  font-weight: 800;

  letter-spacing: 0.02em;
  white-space: nowrap;

  backdrop-filter: blur(4px);

  transform: translate(-50%, -100%);
}

.point-chip:hover {
  background: rgba(23, 33, 43, 0.88);
}

.point-map-crosshair {
  position: absolute;

  left: 50%;
  top: 50%;

  /* Размер — по габаритам пина: 42×50. */
  width: 42px;
  height: 50px;

  /* Остриё пина — в точке: сдвигаем вверх на всю высоту. */
  transform: translate(-50%, -100%);
  transform-origin: 50% 100%;

  z-index: 900;

  cursor: grab;
  touch-action: none;
  user-select: none;
}

.point-map-crosshair.dragging {
  cursor: grabbing;
  transform: translate(-50%, -100%) scale(1.08);
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

/*
 * Радиус действует только у зафиксированной точки: до «ЗАФИКСИРОВАТЬ» и во
 * время «ИЗМЕНИТЬ ТОЧКУ» плашка приглушена, а ползунок выключен — значение
 * при этом сохраняется и возвращается вместе с фиксацией.
 */
.point-radius-float.is-inactive {
  opacity: 0.55;
}

.point-radius-range:disabled {
  cursor: not-allowed;
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

/* Метка поиска: пин-домик, остриё снизу указывает на точку. */
.point-target-pin {
  display: block;
  overflow: visible;

  filter: drop-shadow(0 2px 5px rgba(23, 33, 43, 0.35));
}

.point-target-pin__body {
  fill: var(--albion-accent);
  stroke: #fff;
  stroke-width: 3;
}

.point-target-pin__house {
  fill: #fff;
}

.point-target-pin__door {
  fill: none;
  stroke: var(--albion-accent);
  stroke-width: 2.2;
  stroke-linejoin: round;
}

/* Точка выбрана и ждёт фиксации — мягкая пульсация у острия. */
.point-map-crosshair::after {
  content: '';

  position: absolute;
  left: 50%;
  bottom: 0;

  width: 14px;
  height: 14px;

  transform: translate(-50%, 50%);

  border-radius: 50%;

  pointer-events: none;
}

.point-map-crosshair.pending::after {
  animation: crosshair-pulse 1.4s ease-out infinite;
}

@keyframes crosshair-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(225, 42, 31, 0);
  }

  50% {
    box-shadow: 0 0 0 9px rgba(225, 42, 31, 0.18);
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
.popup-month:not(.is-locked) {
  cursor: pointer;
}

/* Занятый/резервный месяц выбрать нельзя. */
.popup-month.is-locked {
  cursor: not-allowed;
  opacity: 0.5;
}

.popup-month:not(.is-locked):hover {
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
