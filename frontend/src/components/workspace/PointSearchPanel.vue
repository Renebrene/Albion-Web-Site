<template>
  <aside v-if="active" class="point-search-panel">
    <div class="panel-header">
      <div class="panel-title">
        <div class="point-icon">⌖</div>

        <div class="panel-heading">
          <div class="panel-kicker"> Поиск по точке и адресу </div>
        </div>
      </div>
    </div>

    <!-- СВОБОДНЫЕ МЕСЯЦЫ -->
    <section class="panel-section first-section">
      <div class="section-title-row month-title-row">
        <div class="section-label"> Свободные месяцы </div>

        <div class="logic-wrap">
          <span class="logic-help">
            ?
            <span class="logic-tooltip">
              И – одновременно все свободные месяцы, ИЛИ – свободен хотя бы один
              месяц из запрошенных
            </span>
          </span>

          <div class="logic-switch">
            <button
              type="button"
              :class="{ active: monthLogic === 'AND' }"
              @click="$emit('update:monthLogic', 'AND')"
            >
              И
            </button>

            <button
              type="button"
              :class="{ active: monthLogic === 'OR' }"
              @click="$emit('update:monthLogic', 'OR')"
            >
              ИЛИ
            </button>
          </div>
        </div>
      </div>

      <div class="chips">
        <button
          v-for="month in months"
          :key="month.value"
          type="button"
          class="chip"
          :class="{ active: selectedMonths.includes(month.value) }"
          @click="toggleMonth(month.value)"
        >
          {{ month.label }}
        </button>
      </div>
    </section>

    <!-- ФОРМАТ -->
    <section class="panel-section">
      <div class="section-label"> Формат </div>

      <div class="chips">
        <button
          v-for="type in types"
          :key="type"
          type="button"
          class="chip"
          :class="{ active: selectedTypes.includes(type) }"
          @click="toggleType(type)"
        >
          {{ type }}
        </button>
      </div>
    </section>

    <!-- ПОИСК (координаты / адрес) -->
    <section class="panel-section">
      <div class="search-card">
        <input
          :value="searchValue"
          type="search"
          :placeholder="searchPlaceholder"
          autocomplete="off"
          @input="onInput"
          @keydown.enter="onSearch"
        />

        <div class="search-mode">
          <button
            type="button"
            :class="{ active: searchMode === 'coords' }"
            @click="setMode('coords')"
          >
            Координаты
          </button>

          <button
            type="button"
            :class="{ active: searchMode === 'address' }"
            @click="setMode('address')"
          >
            Адрес
          </button>
        </div>

        <button
          type="button"
          class="search-icon"
          title="Найти"
          @click="onSearch"
        >
          ⌕
        </button>
      </div>

      <div
        v-if="searchMode === 'address' && suggestions.length"
        class="address-suggestions"
      >
        <button
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          type="button"
          class="address-suggestion"
          @click="selectSuggestion(suggestion)"
        >
          <span class="address-suggestion-title">
            {{ suggestion.title }}
          </span>
          <span v-if="suggestion.subtitle" class="address-suggestion-sub">
            {{ suggestion.subtitle }}
          </span>
        </button>
      </div>

      <div v-if="addressLoading" class="input-hint" role="status">
        Ищем адрес…
      </div>
      <div
        v-else-if="addressError"
        class="input-hint input-hint--error"
        role="alert"
      >
        {{ addressError }}
      </div>
      <div v-else class="input-hint">
        {{ searchHint }}
      </div>
    </section>

    <!-- РЕЗУЛЬТАТ -->
    <div class="result-count">
      <div class="count-value">
        {{ count }}
      </div>

      <div class="count-text">
        {{ constructionLabel }}
      </div>

      <div class="count-caption"> найдено в выбранном районе </div>

      <button
        type="button"
        class="open-list-button"
        @click="$emit('open-list')"
      >
        ОТКРЫТЬ СПИСОК
      </button>
    </div>

    <!-- СПИСОК НАЙДЕННОГО (по форматам) -->
    <div v-if="groupedResults.length" class="found-list">
      <div
        v-for="group in groupedResults"
        :key="group.type"
        class="found-group"
      >
        <div class="found-type">
          {{ group.type }}
        </div>

        <div class="found-addresses">
          <div
            v-for="(entry, index) in group.addresses"
            :key="index"
            class="found-address"
          >
            <span class="found-address-text">— {{ entry.address }}</span>

            <!-- Портфель: доступен, только если у элемента есть id -->
            <span v-if="surfaceIdOf(entry.item) !== null" class="found-pf">
              <button
                type="button"
                class="found-pf-toggle"
                :class="{ 'is-active': isSurfaceActive(entry.item) }"
                :title="
                  isSurfaceActive(entry.item)
                    ? 'Убрать из портфеля'
                    : 'Добавить в портфель'
                "
                @click="toggleFoundPfMode(entry.item)"
              >
                <q-icon name="inventory_2" size="14px" />
              </button>

              <span v-if="isSurfaceActive(entry.item)" class="found-pf-months">
                <button
                  v-for="month in MONTHS"
                  :key="month.full"
                  type="button"
                  class="found-pf-month"
                  :class="{
                    'is-selected': isMonthSelected(entry.item.id, month.full),
                    'is-locked': isMonthLocked(entry.item, month.full)
                  }"
                  :title="getMonthStatusLabel(entry.item, month.full)"
                  @click="onFoundMonthClick(entry.item, month)"
                >
                  {{ month.short }}
                </button>
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="found-empty"> Ничего не найдено </div>
  </aside>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

import { MONTHS } from '../../utils/constructionGroups'
import { getMonthStatusLabel, isFree } from '../../utils/availability'
import { usePortfolio } from '../../composables/usePortfolio'
import { suggestAddress } from '../../services/geoApi'

const props = defineProps({
  active: {
    type: Boolean,
    default: false
  },

  months: {
    type: Array,
    default: () => []
  },

  selectedMonths: {
    type: Array,
    default: () => []
  },

  monthLogic: {
    type: String,
    default: 'OR'
  },

  types: {
    type: Array,
    default: () => []
  },

  selectedTypes: {
    type: Array,
    default: () => []
  },

  count: {
    type: Number,
    default: 0
  },

  results: {
    type: Array,
    default: () => []
  },

  coordinates: {
    type: String,
    default: ''
  },

  address: {
    type: String,
    default: ''
  },

  addressLoading: {
    type: Boolean,
    default: false
  },

  addressError: {
    type: String,
    default: ''
  }
})

const emit = defineEmits([
  'update:selectedMonths',
  'update:monthLogic',
  'update:selectedTypes',
  'update:coordinates',
  'update:address',
  'search',
  'search-address',
  'open-list'
])

/* Переключатель режима поиска на краю поля. */
const searchMode = ref('coords')

const searchValue = computed(() =>
  searchMode.value === 'coords' ? props.coordinates : props.address
)

const searchPlaceholder = computed(() =>
  searchMode.value === 'coords' ? '47.2315, 39.7233' : 'Введите адрес'
)

const searchHint = computed(() =>
  searchMode.value === 'coords'
    ? 'Широта и долгота через запятую'
    : 'Начните вводить адрес — появятся подсказки'
)

const suggestions = ref([])
let suggestTimer = null
let suggestSeq = 0

function clearSuggestions() {
  suggestions.value = []
  suggestSeq += 1

  if (suggestTimer) {
    clearTimeout(suggestTimer)
    suggestTimer = null
  }
}

async function loadSuggestions(query) {
  const value = String(query || '').trim()

  if (value.length < 3) {
    suggestions.value = []
    return
  }

  const seq = ++suggestSeq

  try {
    const result = await suggestAddress(value)

    if (seq !== suggestSeq) {
      return
    }

    suggestions.value = Array.isArray(result?.suggestions)
      ? result.suggestions
      : []
  } catch (error) {
    if (seq === suggestSeq) {
      suggestions.value = []
    }
  }
}

function setMode(mode) {
  searchMode.value = mode
  clearSuggestions()
}

function onInput(event) {
  const value = event.target.value

  if (searchMode.value === 'coords') {
    clearSuggestions()
    emit('update:coordinates', value)
    return
  }

  emit('update:address', value)
  clearSuggestions()

  suggestTimer = setTimeout(() => {
    suggestTimer = null
    void loadSuggestions(value)
  }, 300)
}

function selectSuggestion(suggestion) {
  emit('update:address', suggestion.display_name || suggestion.query)
  clearSuggestions()
  emit('search-address')
}

function onSearch() {
  clearSuggestions()
  emit(searchMode.value === 'coords' ? 'search' : 'search-address')
}

onBeforeUnmount(() => {
  clearSuggestions()
  suggestSeq += 1
})

const constructionLabel = computed(() => {
  const value = Number(props.count) || 0

  if (value % 10 === 1 && value % 100 !== 11) {
    return 'конструкция'
  }

  if (
    value % 10 >= 2 &&
    value % 10 <= 4 &&
    (value % 100 < 10 || value % 100 >= 20)
  ) {
    return 'конструкции'
  }

  return 'конструкций'
})

/* ---------------------------------------------------------- портфель */

/*
 * Портфель — общий стор. На каждом найденном адресе — компактный
 * контрол: кнопка + (в режиме выбора) мини-месяцы.
 */
const {
  isInPortfolio,
  isMonthSelected,
  isSelectionMode,
  toggleSelectionMode,
  removeSurface,
  // alias: в панели уже есть свой toggleMonth для чипов фильтра
  toggleMonth: togglePortfolioMonth
} = usePortfolio()

/* id поверхности; null — если его нет (тогда контрол не показываем). */
function surfaceIdOf(item) {
  const id = item?.id

  return id === undefined || id === null || id === '' ? null : id
}

/*
 * Активна (розовая кнопка, видимые месяцы), если поверхность в портфеле
 * или для неё включён режим выбора. Портфель переживает перезагрузку,
 * режим — нет, поэтому учитываем оба условия.
 */
function isSurfaceActive(item) {
  const id = surfaceIdOf(item)

  return id !== null && (isInPortfolio(id) || isSelectionMode(id))
}

/*
 * Клик по кнопке: неактивна -> включаем режим выбора;
 * активна -> removeSurface (убирает и месяцы, и режим из стора).
 */
function toggleFoundPfMode(item) {
  const id = surfaceIdOf(item)

  if (id === null) {
    return
  }

  if (isSurfaceActive(item)) {
    removeSurface(id)
  } else {
    toggleSelectionMode(id)
  }
}

function onFoundMonthClick(item, month) {
  if (!isSurfaceActive(item)) {
    return
  }

  const id = surfaceIdOf(item)

  if (id === null) {
    return
  }

  /* Снять можно всегда; добавить — только свободный месяц. */
  if (isMonthLocked(item, month.full)) {
    return
  }

  togglePortfolioMonth(item, month.full, item.month_prices?.[month.full])
}

/* Месяц недоступен для выбора: занят/резерв и ещё не выбран. */
function isMonthLocked(item, monthFull) {
  const id = surfaceIdOf(item)

  if (id === null || isMonthSelected(id, monthFull)) {
    return false
  }

  return !isFree(item, monthFull)
}

/* Группируем найденное по формату: «ЩИТ — Адрес1, Адрес2…». */
const groupedResults = computed(() => {
  const groups = []

  for (const item of props.results) {
    const type = String(item?.type || 'Конструкция').trim()
    const address = String(item?.address || item?.name || '').trim()

    let group = groups.find(existing => existing.type === type)

    if (!group) {
      group = { type, addresses: [] }
      groups.push(group)
    }

    // Храним ссылку на элемент — она нужна контролу портфеля.
    if (address && !group.addresses.some(entry => entry.address === address)) {
      group.addresses.push({ address, item })
    }
  }

  return groups
})

function toggleMonth(value) {
  const values = [...props.selectedMonths]
  const index = values.indexOf(value)

  if (index === -1) {
    values.push(value)
  } else {
    values.splice(index, 1)
  }

  emit('update:selectedMonths', values)
}

function toggleType(value) {
  const values = [...props.selectedTypes]
  const index = values.indexOf(value)

  if (index === -1) {
    values.push(value)
  } else {
    // Нельзя снять последний выбранный формат.
    if (values.length === 1) {
      return
    }

    values.splice(index, 1)
  }

  emit('update:selectedTypes', values)
}
</script>

<style scoped>
.point-search-panel {
  height: 100%;
  min-width: 0;

  overflow-y: auto;

  background: #fff;

  border-right: 1px solid #e5e9eb;

  padding: 28px 20px 30px;
  color: #17212b;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;

  padding-bottom: 18px;

  border-bottom: 1px solid #e5e9ec;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.point-icon {
  width: 38px;
  height: 38px;

  display: grid;
  place-items: center;

  border-radius: 12px;

  background: #17212b;
  color: white;

  font-size: 19px;
}

/* Как заголовок «Интерактивная карта» в сайдбаре, но меньшим кеглем. */
.panel-kicker {
  margin-bottom: 3px;

  color: #17212b;

  font-size: 16px;
  font-weight: 800;

  letter-spacing: -0.3px;
  line-height: 1.1;
}

.panel-title h3 {
  margin: 0;

  color: #17212b;

  font-size: 18px;
  font-weight: 800;
}

.panel-section {
  margin-top: 20px;
}

.first-section {
  margin-top: 20px;
}

.section-label {
  display: block;

  margin-bottom: 8px;

  color: #68757e;

  font-size: 9px;
  font-weight: 900;

  letter-spacing: 1px;

  text-transform: uppercase;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
}

.section-title-row .section-label {
  margin-bottom: 0;
}

/* Строка «Свободные месяцы» — точка привязки тултипа подсказки. */
.month-title-row {
  position: relative;
}

.logic-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.logic-help {
  /* position намеренно не задаём: тултип позиционируется относительно
     всей строки (см. .month-title-row), иначе уходит влево за край. */
  width: 16px;
  height: 16px;
  flex: 0 0 16px;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  border-radius: 50%;
  border: 1px solid #cdd5da;
  background: #f7f8f9;

  color: #6b7881;
  font-size: 10px;
  font-weight: 800;

  cursor: help;
}

.logic-tooltip {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;

  width: min(240px, 100%);
  padding: 8px 10px;

  border-radius: 8px;
  background: #17212b;
  color: #fff;

  font-size: 11px;
  font-weight: 400;
  line-height: 1.4;
  letter-spacing: 0;

  text-transform: none;
  white-space: normal;
  word-wrap: break-word;

  opacity: 0;
  visibility: hidden;
  pointer-events: none;

  transition:
    opacity 0.15s ease,
    visibility 0.15s ease;

  z-index: 30;
}

.logic-help:hover .logic-tooltip,
.logic-help:focus .logic-tooltip {
  opacity: 1;
  visibility: visible;
}

.logic-switch {
  display: flex;
  gap: 2px;
  padding: 2px;
  border-radius: 7px;
  background: #f1f3f4;
}

.logic-switch button {
  min-width: 27px;
  height: 22px;
  padding: 0 6px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: #7b878f;
  cursor: pointer;
  font-size: 8px;
  font-weight: 900;
}

.logic-switch button.active {
  background: #fff;
  color: #17212b;
  box-shadow: 0 1px 4px rgba(20, 30, 40, 0.1);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 7px 9px;
  border: 1px solid #e1e6e9;
  border-radius: 8px;
  background: #fff;
  color: #52606a;
  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
  transition: 0.12s ease;
}

.chip:hover {
  border-color: #d1d8dc;
}

.chip.active {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
}

/* Поисковая строка — как на закладке «Интерактивная карта» */
.search-card {
  display: flex;
  align-items: center;
  gap: 8px;

  height: 44px;
  padding: 0 8px 0 10px;

  border: 1px solid #dce2e6;
  border-radius: 12px;

  background: #fff;

  transition: 0.2s ease;
}

.search-card:focus-within {
  border-color: #17212b;
  box-shadow: 0 0 0 3px rgba(23, 33, 43, 0.07);
}

.search-card input {
  min-width: 0;
  flex: 1;

  border: 0;
  outline: 0;

  background: transparent;

  color: #17212b;

  font-size: 13px;
}

.search-card input::placeholder {
  color: #9aa5ac;
}

/* Переключатель координаты/адрес — на краю поля */
.search-mode {
  flex: 0 0 auto;

  display: flex;
  gap: 2px;

  padding: 2px;

  border-radius: 7px;
  background: #f1f3f4;
}

.search-mode button {
  height: 24px;
  padding: 0 7px;

  border: 0;
  border-radius: 5px;

  background: transparent;
  color: #7b878f;

  cursor: pointer;

  font-size: 9px;
  font-weight: 800;

  white-space: nowrap;
}

.search-mode button.active {
  background: #fff;
  color: #17212b;
  box-shadow: 0 1px 4px rgba(20, 30, 40, 0.12);
}

/* Иконка поиска — справа */
.search-icon {
  flex: 0 0 30px;
  width: 30px;
  height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;

  border: 0;
  border-radius: 8px;

  background: transparent;

  color: #5b6873;

  font-size: 22px;

  cursor: pointer;

  transition: background 0.18s ease;
}

.search-icon:hover {
  background: #f0f3f4;
}

.input-hint {
  margin-top: 6px;

  color: #5f6c76;

  font-size: 10px;
  line-height: 1.4;
}

.input-hint--error {
  color: #a8281f;
}

.address-suggestions {
  display: flex;
  flex-direction: column;

  margin-top: 6px;
  overflow: hidden;

  border: 1px solid #dce2e6;
  border-radius: 10px;

  background: #fff;
  box-shadow: 0 10px 24px rgba(25, 35, 45, 0.12);
}

.address-suggestion {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;

  padding: 9px 11px;

  border: 0;
  border-bottom: 1px solid #eef1f3;

  background: transparent;
  color: #17212b;

  font-family: inherit;
  text-align: left;

  cursor: pointer;
}

.address-suggestion:last-child {
  border-bottom: 0;
}

.address-suggestion:hover,
.address-suggestion:focus-visible {
  background: #f4f6f7;
}

.address-suggestion-title {
  font-size: 12px;
  font-weight: 800;
}

.address-suggestion-sub {
  color: #5f6c76;
  font-size: 10px;
}

.result-count {
  margin-top: 20px;

  padding: 18px;

  text-align: center;

  border-radius: 16px;

  background: linear-gradient(135deg, #17212b, #293844);

  color: white;
}

.count-value {
  font-size: 40px;
  font-weight: 900;
  line-height: 1;
}

.count-text {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 700;
}

.count-caption {
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
}

.open-list-button {
  width: 100%;

  margin-top: 14px;

  min-height: 40px;

  border: 0;
  border-radius: 10px;

  background: var(--albion-accent);
  color: #fff;

  cursor: pointer;

  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.8px;

  transition: 0.15s ease;
}

.open-list-button:hover {
  background: #c92219;
}

.found-list {
  margin-top: 16px;

  max-height: 240px;
  overflow-y: auto;

  padding: 12px;

  border: 1px solid #e5e9ec;
  border-radius: 12px;

  background: #fafbfc;
}

.found-group + .found-group {
  margin-top: 12px;
}

.found-type {
  margin-bottom: 5px;

  color: #17212b;

  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.found-address {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;

  color: #52606a;
  font-size: 11px;
  line-height: 1.5;
}

.found-address-text {
  flex: 1 1 auto;
  min-width: 0;
}

/* Компактный контрол портфеля в списке найденного */
.found-pf {
  flex: 0 0 auto;

  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.found-pf-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  width: 24px;
  height: 24px;

  padding: 0;

  border: 1px solid #dce2e6;
  border-radius: 7px;

  background: #fff;
  color: #5b6873;

  cursor: pointer;

  transition: 0.15s ease;
}

.found-pf-toggle:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

/* Активное состояние: поверхность в портфеле либо включён режим выбора */
.found-pf-toggle.is-active {
  border-color: var(--albion-accent);
  background: #fdeceb;
  color: var(--albion-accent);
}

.found-pf-months {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 3px;
}

.found-pf-month {
  min-width: 26px;
  height: 20px;

  padding: 0 4px;

  border: 1px solid #dce2e6;
  border-radius: 5px;

  background: #fff;
  color: #66737c;

  cursor: pointer;

  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.2px;

  transition: 0.12s ease;
}

.found-pf-month:hover:not(.is-locked) {
  border-color: var(--albion-accent);
}

.found-pf-month.is-selected {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
}

/* Занятый/резервный месяц выбрать нельзя. */
.found-pf-month.is-locked {
  cursor: not-allowed;
  opacity: 0.5;
}

.found-empty {
  margin-top: 16px;

  padding: 14px;

  border-radius: 10px;

  background: #f4f6f7;
  color: #8b98a1;

  font-size: 11px;
  text-align: center;
}

@media (max-width: 900px) {
  .point-search-panel {
    left: 12px;
    right: 12px;

    top: 84px;
    bottom: 12px;

    width: auto;
  }
}
</style>
