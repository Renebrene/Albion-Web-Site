<template>
  <aside
    v-if="active"
    class="point-search-panel"
  >
    <div class="panel-header">
      <div class="panel-title">
        <div class="point-icon">⌖</div>

        <div>
          <div class="panel-kicker">
            ПОИСК ПО ТОЧКЕ И АДРЕСУ
          </div>

          <h3>Поиск по точке и адресу</h3>
        </div>
      </div>
    </div>

    <!-- СВОБОДНЫЕ МЕСЯЦЫ -->
    <section class="panel-section first-section">
      <div class="section-title-row">
        <div class="section-label">
          Свободные месяцы
        </div>

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
      <div class="section-label">
        Формат
      </div>

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
        >

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

      <div class="input-hint">
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

      <div class="count-caption">
        найдено в выбранном районе
      </div>

      <button
        type="button"
        class="open-list-button"
        @click="$emit('open-list')"
      >
        ОТКРЫТЬ СПИСОК
      </button>
    </div>

    <!-- СПИСОК НАЙДЕННОГО (по форматам) -->
    <div
      v-if="groupedResults.length"
      class="found-list"
    >
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
            <span
              v-if="surfaceIdOf(entry.item) !== null"
              class="found-pf"
            >
              <button
                type="button"
                class="found-pf-toggle"
                :class="{ 'is-active': isSurfaceActive(entry.item) }"
                :title="isSurfaceActive(entry.item)
                  ? 'Убрать из портфеля'
                  : 'Добавить в портфель'"
                @click="toggleFoundPfMode(entry.item)"
              >
                <q-icon name="inventory_2" size="14px" />
              </button>

              <span
                v-if="isSurfaceActive(entry.item)"
                class="found-pf-months"
              >
                <button
                  v-for="month in MONTHS"
                  :key="month.full"
                  type="button"
                  class="found-pf-month"
                  :class="{ 'is-selected': isMonthSelected(entry.item.id, month.full) }"
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

    <div
      v-else
      class="found-empty"
    >
      Ничего не найдено
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'

import { MONTHS } from '../../utils/constructionGroups'
import { getMonthStatusLabel } from '../../utils/availability'
import { usePortfolio } from '../../composables/usePortfolio'

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
    : 'Поиск по адресу подключим позже (по геокодеру)'
)

function setMode(mode) {
  searchMode.value = mode
}

function onInput(event) {
  const value = event.target.value

  if (searchMode.value === 'coords') {
    emit('update:coordinates', value)
  } else {
    emit('update:address', value)
  }
}

function onSearch() {
  emit(searchMode.value === 'coords' ? 'search' : 'search-address')
}

const constructionLabel = computed(() => {
  const value = Number(props.count) || 0

  if (value % 10 === 1 && value % 100 !== 11) {
    return 'конструкция'
  }

  if (
    value % 10 >= 2 &&
    value % 10 <= 4 &&
    (
      value % 100 < 10 ||
      value % 100 >= 20
    )
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

  togglePortfolioMonth(item, month.full, item.month_prices?.[month.full])
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
    if (
      address &&
      !group.addresses.some(entry => entry.address === address)
    ) {
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

.panel-kicker {
  margin-bottom: 3px;

  color: var(--albion-accent);

  font-size: 9px;
  font-weight: 900;

  letter-spacing: 1.3px;
  line-height: 1.3;
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
  box-shadow: 0 1px 4px rgba(20, 30, 40, .10);
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
  transition: .12s ease;
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
  box-shadow: 0 1px 4px rgba(20, 30, 40, .12);
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

  color: #71808c;

  font-size: 22px;

  cursor: pointer;

  transition: background .18s ease;
}

.search-icon:hover {
  background: #f0f3f4;
}

.input-hint {
  margin-top: 6px;

  color: #8b98a1;

  font-size: 10px;
  line-height: 1.4;
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
  color: #71808c;

  cursor: pointer;

  transition: .15s ease;
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
  letter-spacing: .2px;

  transition: .12s ease;
}

.found-pf-month:hover {
  border-color: var(--albion-accent);
}

.found-pf-month.is-selected {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
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
