<template>
  <aside class="filters-sidebar">
    <div class="sidebar-head">
      <h2>{{ mode === 'list' ? 'Список конструкций' : 'Интерактивная карта' }}</h2>
    </div>

    <section class="filter-section">
      <div class="section-title-row month-title-row">
        <div class="section-label">Свободные месяцы</div>

        <div class="logic-wrap">
          <span class="logic-help">
            ?
            <span class="logic-tooltip">
              И – одновременно все свободные месяцы, ИЛИ – свободен хотя бы
              один месяц из запрошенных
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

    <section class="filter-section">
      <div class="section-label">Формат</div>

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

    <section class="filter-section cities-section">
      <div class="section-title-row">
        <div class="section-label">Города / районы</div>

        <div class="city-actions">
          <button
            type="button"
            @click="selectAllCities"
          >
            Выбрать все
          </button>

          <button
            type="button"
            @click="clearCities"
          >
            Снять все
          </button>
        </div>
      </div>

      <div class="cities-list">
        <div
          v-for="city in cities"
          :key="city"
          class="city-row"
          :class="{ active: selectedCities.includes(city) }"
        >
          <button
            type="button"
            class="city-check-button"
            :aria-label="`Выбрать город ${city}`"
            @click.stop="toggleCity(city)"
          >
            <span class="city-check">
              <span v-if="selectedCities.includes(city)">✓</span>
            </span>
          </button>

          <button
            type="button"
            class="city-name-button"
            @click="focusCity(city)"
          >
            <span class="city-name">{{ city }}</span>
          </button>
        </div>
      </div>
    </section>
  </aside>
</template>

<script setup>
const props = defineProps({
  /* Текущий режим рабочей области: 'map' | 'list' — от него зависит заголовок. */
  mode: {
    type: String,
    default: 'map'
  },

  selectedMonths: {
    type: Array,
    default: () => []
  },

  monthLogic: {
    type: String,
    default: 'OR'
  },

  selectedTypes: {
    type: Array,
    default: () => []
  },

  selectedCities: {
    type: Array,
    default: () => []
  },

  months: {
    type: Array,
    default: () => []
  },

  types: {
    type: Array,
    default: () => []
  },

  cities: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits([
  'update:selectedMonths',
  'update:monthLogic',
  'update:selectedTypes',
  'update:selectedCities',
  'focus-city'
])

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

function focusCity(value) {
  emit('focus-city', value)
}

function toggleCity(value) {
  const values = [...props.selectedCities]
  const index = values.indexOf(value)

  if (index === -1) {
    values.push(value)
  } else {
    values.splice(index, 1)
  }

  emit('update:selectedCities', values)
}

function selectAllCities() {
  emit('update:selectedCities', [...props.cities])
}

function clearCities() {
  emit(
    'update:selectedCities',
    props.cities.includes('Ростов-на-Дону')
      ? ['Ростов-на-Дону']
      : []
  )
}
</script>

<style scoped>
.filters-sidebar {
  height: 100%;
  overflow-y: auto;
  background: #fff;
  border-right: 1px solid #e5e9eb;
  /* Верхний отступ переехал в .sidebar-head — чтобы его фон закрывал
     прокручиваемые фильтры, когда заголовок закреплён. */
  padding: 0 20px 30px;
}

/* Заголовок «Интерактивная карта» закреплён: фильтры прокручиваются под
   ним, а не уносят его вверх. */
.sidebar-head {
  position: sticky;
  top: 0;
  z-index: 5;

  padding: 28px 0 22px;

  background: #fff;
}

/* Отступ до первого блока даёт padding-bottom заголовка, второй не нужен. */
.sidebar-head + .filter-section {
  margin-top: 0;
}

.eyebrow {
  margin-bottom: 6px;
  color: var(--albion-accent);
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1.8px;
}

.sidebar-head h2 {
  margin: 0;
  color: #17212b;
  font-size: 21px;
  line-height: 1.1;
  letter-spacing: -.4px;
}





.filter-section {
  margin-top: 22px;
}

.section-label {
  margin-bottom: 9px;
  color: #68757e;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1px;
  text-transform: uppercase;
}

 .logic-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.logic-help {
  /* position намеренно не задаём: тултип позиционируется относительно
     всей строки (см. .month-title-row), иначе он уходит влево за край. */
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

  /* Ширина ограничена шириной строки, чтобы тултип не выходил за сайдбар
     (у сайдбара overflow-y: auto — всё, что вылезает влево, обрезается). */
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
    opacity .15s ease,
    visibility .15s ease;

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

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 9px;
}

/* Строка «Свободные месяцы» — точка привязки тултипа подсказки. */
.month-title-row {
  position: relative;
}

.section-title-row .section-label {
  margin-bottom: 0;
}

.city-actions {
  display: flex;
  gap: 6px;
}

.city-actions button {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--albion-accent);
  cursor: pointer;
  font-size: 9px;
  font-weight: 800;
  white-space: nowrap;
}

.city-actions button:hover {
  text-decoration: underline;
}

.cities-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.city-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 28px;
  padding: 3px 7px;
  border-radius: 7px;
  background: transparent;
  color: #52606a;
}

.city-row:hover {
  background: #f5f6f7;
}

.city-row.active {
  color: #17212b;
}

.city-check-button,
.city-name-button {
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.city-check-button {
  flex: 0 0 14px;
  width: 14px;
  height: 20px;
  display: grid;
  place-items: center;
}

.city-check {
  width: 14px;
  height: 14px;
  display: grid;
  place-items: center;
  border: 1px solid #d4dadd;
  border-radius: 4px;
  background: #fff;
  color: #fff;
  font-size: 9px;
  font-weight: 900;
}

.city-row.active .city-check {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
}

.city-name-button {
  flex: 1;
  min-width: 0;
  text-align: left;
  color: inherit;
}

.city-name-button:hover .city-name {
  color: var(--albion-accent);
}

.city-name {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 600;
}
</style>
