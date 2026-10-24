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
              :aria-pressed="monthLogic === 'AND'"
              @click="$emit('update:monthLogic', 'AND')"
            >
              И
            </button>

            <button
              type="button"
              :class="{ active: monthLogic === 'OR' }"
              :aria-pressed="monthLogic === 'OR'"
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
          :aria-pressed="selectedMonths.includes(month.value)"
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
          :aria-pressed="selectedTypes.includes(type)"
          :disabled="isLastSelectedType(type)"
          :title="
            isLastSelectedType(type)
              ? 'Должен остаться хотя бы один формат'
              : undefined
          "
          @click="toggleType(type)"
        >
          {{ type }}
        </button>
      </div>
    </section>

    <!-- РЕЗУЛЬТАТ -->
    <div class="result-count">
      <!--
        Пока точка не зафиксирована, результаты не считаются: вместо «0
        конструкций · Ничего не найдено» показываем, что осталось сделать.
      -->
      <div class="count-value">
        {{ pointFixed ? count : '—' }}
      </div>

      <div class="count-text">
        {{ pointFixed ? constructionLabel : 'Поиск по точке' }}
      </div>

      <div class="count-caption">
        {{
          pointFixed
            ? 'найдено в выбранном районе'
            : 'зафиксируйте точку, чтобы увидеть результаты'
        }}
      </div>

      <button
        type="button"
        class="open-list-button"
        :disabled="!count || !pointFixed"
        :title="
          !pointFixed
            ? 'Сначала зафиксируйте точку'
            : count
              ? undefined
              : 'В выбранном районе ничего не найдено'
        "
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
            <span class="found-address-text">
              — {{ entry.address }}
              <span v-if="entry.mark" class="found-address-mark">
                {{ entry.mark }}</span
              >
            </span>

            <!-- Портфель: доступен, только если у поверхностей есть id -->
            <span v-if="entry.hasIds" class="found-pf">
              <button
                type="button"
                class="found-pf-toggle"
                :class="{ 'is-active': isEditingEntry(entry) }"
                :title="
                  isEditingEntry(entry) ? 'Скрыть месяцы' : 'Показать месяцы'
                "
                @click="toggleEntryPfMode(entry)"
              >
                <q-icon name="inventory_2" size="14px" />
              </button>

              <span v-if="isEditingEntry(entry)" class="found-pf-months">
                <button
                  v-for="month in MONTHS"
                  :key="month.full"
                  type="button"
                  :disabled="isEntryMonthLocked(entry, month.full)"
                  :aria-disabled="isEntryMonthLocked(entry, month.full)"
                  class="found-pf-month"
                  :class="{
                    'is-selected': isEntryMonthSelected(entry, month.full),
                    'is-locked': isEntryMonthLocked(entry, month.full)
                  }"
                  :title="entryMonthLabel(entry, month.full)"
                  @click="onEntryMonthClick(entry, month)"
                >
                  {{ month.short }}
                </button>
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="pointFixed" class="found-empty"> Ничего не найдено </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

import { MONTHS, parentSide } from '../../utils/constructionGroups'
import { getMonthStatusLabel, isFree } from '../../utils/availability'
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

  /* Точка зафиксирована: до этого результаты не считаются и не показываются. */
  pointFixed: {
    type: Boolean,
    default: true
  },

  results: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits([
  'update:selectedMonths',
  'update:monthLogic',
  'update:selectedTypes',
  'open-list'
])

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
  isSideMonthSelected,
  isSideMonthLocked,
  toggleSideMonth,
  isSelectionMode,
  setSelectionMode
} = usePortfolio()

/* id поверхности; null — если его нет (тогда контрол не показываем). */
function surfaceIdOf(item) {
  const id = item?.id

  return id === undefined || id === null || id === '' ? null : id
}

/* Представитель строки: первая поверхность с id (для режима выбора). */
function entryPrimary(entry) {
  return (
    entry.items.find(item => surfaceIdOf(item) !== null) ||
    entry.items[0] ||
    null
  )
}

function isEditingEntry(entry) {
  const id = surfaceIdOf(entryPrimary(entry))

  return id !== null && isSelectionMode(id)
}

/*
 * Кнопка только включает/выключает режим выбора месяцев. Удаление —
 * явной кнопкой «Убрать» в панели портфеля (с undo). Режим — у одной
 * поверхности-представителя, как было до пометок.
 */
function toggleEntryPfMode(entry) {
  const id = surfaceIdOf(entryPrimary(entry))

  if (id === null) {
    return
  }

  setSelectionMode(id, !isSelectionMode(id))
}

/*
 * Месяц адреса: состояние считаем по всем его поверхностям, а клик
 * добавляет ОДНУ позицию (см. toggleSideMonth в usePortfolio) — иначе
 * адрес с несколькими поверхностями превращался в несколько позиций.
 */
function isEntryMonthSelected(entry, monthFull) {
  return isSideMonthSelected(entry.items, monthFull)
}

/* Месяц недоступен, если снять нечего и ни одна поверхность не свободна. */
function isEntryMonthLocked(entry, monthFull) {
  return isSideMonthLocked(entry.items, monthFull)
}

function onEntryMonthClick(entry, month) {
  if (!isEditingEntry(entry)) {
    return
  }

  toggleSideMonth(entry.items, month.full)
}

/* Подпись месяца: берём у свободной поверхности — её и получит клиент. */
function entryMonthLabel(entry, monthFull) {
  const free = entry.items.find(item => isFree(item, monthFull))

  if (free) {
    return getMonthStatusLabel(free, monthFull)
  }

  return isEntryMonthSelected(entry, monthFull) ? 'Выбрано' : 'Занято'
}

/*
 * Группируем найденное по формату: «ЩИТ — Адрес1, Адрес2…».
 *
 * На один адрес — одна строка, но поверхностей по адресу может быть
 * несколько (щит A и B, призматрон A(1)…A(3)). Раньше вторая и следующие
 * просто терялись. Теперь строка хранит все элементы и показывает короткую
 * пометку «A, B · 6×3».
 *
 * В портфель со строки добавляется ОДНА позиция — первая свободная
 * поверхность. Портфель информационный: он не должен разрастаться на все
 * поверхности адреса одним кликом.
 */
const groupedResults = computed(() => {
  const groups = []

  for (const item of props.results) {
    const type = String(item?.type || 'Конструкция').trim()
    const address = String(item?.address || item?.name || '').trim()

    if (!address) {
      continue
    }

    let group = groups.find(existing => existing.type === type)

    if (!group) {
      group = { type, addresses: [] }
      groups.push(group)
    }

    let entry = group.addresses.find(existing => existing.address === address)

    if (!entry) {
      entry = { address, items: [] }
      group.addresses.push(entry)
    }

    entry.items.push(item)
  }

  /* Пометку и наличие id считаем один раз, а не на каждый рендер. */
  for (const group of groups) {
    for (const entry of group.addresses) {
      entry.mark = entryMark(entry.items)
      entry.hasIds = entry.items.some(item => surfaceIdOf(item) !== null)
    }
  }

  return groups
})

/* «6 X 3 Метр» → «6×3»: короткая пометка рядом с адресом. */
function formatSize(value) {
  const raw = String(value || '').trim()

  if (!raw) {
    return ''
  }

  return raw
    .replace(/\s*[xX×хХ]\s*/g, '×')
    .replace(/\s*метр\w*/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/* Пометка строки: стороны и размеры всех поверхностей без повторов. */
function entryMark(items) {
  const sides = []
  const sizes = []

  for (const item of items) {
    const side = parentSide(item?.side, item?.type)

    if (side && !sides.includes(side)) {
      sides.push(side)
    }

    const size = formatSize(item?.size)

    if (size && !sizes.includes(size)) {
      sizes.push(size)
    }
  }

  return [sides.join(', '), sizes.join(', ')].filter(Boolean).join(' · ')
}

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

/* Последний выбранный формат снять нельзя — иначе не останется ни одного. */
function isLastSelectedType(type) {
  return props.selectedTypes.length === 1 && props.selectedTypes.includes(type)
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

/* Недоступный чип (последний формат) — явно неактивный и без ховера. */
.chip:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.chip:hover {
  border-color: #d1d8dc;
}

.chip.active {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
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

.open-list-button:hover:not(:disabled) {
  background: #c92219;
}

/* Ничего не найдено — открывать нечего. */
.open-list-button:disabled {
  background: #b9c1c7;
  color: rgba(255, 255, 255, 0.9);
  cursor: not-allowed;
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

/* Пометка поверхностей: «A, B · 6×3» — тише адреса, но читаемо. */
.found-address-mark {
  margin-left: 4px;

  padding: 1px 5px;

  border-radius: 5px;

  background: #eef1f3;
  color: #5b6873;

  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
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
