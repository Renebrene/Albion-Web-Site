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

          <h3>Поиск рядом</h3>
        </div>
      </div>
    </div>

    <!-- КООРДИНАТЫ -->
    <div class="panel-section first-section">
      <label
        class="section-label"
        for="point-coordinates"
      >
        Координаты
      </label>

      <div class="input-row">
        <input
          id="point-coordinates"
          :value="coordinates"
          type="text"
          class="search-input"
          placeholder="47.2315, 39.7233"
          autocomplete="off"
          @input="$emit('update:coordinates', $event.target.value)"
          @keyup.enter="$emit('search')"
        />

        <button
          type="button"
          class="input-action"
          title="Найти по координатам"
          @click="$emit('search')"
        >
          →
        </button>
      </div>

      <div class="input-hint">
        Введите широту и долготу через запятую
      </div>
    </div>

    <!-- АДРЕС -->
    <div class="panel-section">
      <label
        class="section-label"
        for="point-address"
      >
        Адрес
      </label>

      <div class="input-row">
        <input
          id="point-address"
          :value="address"
          type="text"
          class="search-input"
          placeholder="Введите адрес"
          autocomplete="off"
          @input="$emit('update:address', $event.target.value)"
          @keyup.enter="$emit('search-address')"
        />

        <button
          type="button"
          class="input-action"
          title="Найти адрес"
          @click="$emit('search-address')"
        >
          →
        </button>
      </div>

      <div class="input-hint">
        Поиск по адресу будет подключён к геокодеру
      </div>
    </div>

    <!-- РАДИУС -->
    <div class="panel-section">
      <div class="section-label">
        Радиус поиска
      </div>

      <div class="radius-list">
        <button
          v-for="value in radiusOptions"
          :key="value"
          type="button"
          class="radius-button"
          :class="{ active: radius === value }"
          @click="$emit('update:radius', value)"
        >
          {{ formatRadius(value) }}
        </button>
      </div>
    </div>

    <!-- КНОПКА -->
    <button
      type="button"
      class="search-button"
      @click="$emit('search')"
    >
      <span class="search-button-icon">⌖</span>
      <span>НАЙТИ В РАДИУСЕ</span>
    </button>

    <!-- ВЫБРАННАЯ ТОЧКА -->
    <div
      v-if="city || district || pointLabel"
      class="point-location"
    >
      <div class="location-marker">📍</div>

      <div class="location-content">
        <div class="location-label">
          Найденная точка
        </div>

        <strong>
          {{ city || 'Точка на карте' }}
        </strong>

        <span
          v-if="district"
          class="location-district"
        >
          {{ district }}
        </span>

        <span
          v-if="pointLabel"
          class="location-point"
        >
          {{ pointLabel }}
        </span>
      </div>
    </div>

    <!-- РЕЗУЛЬТАТ -->
    <div class="result-count">
      <div class="count-value">
        {{ count }}
      </div>

      <div class="count-text">
        {{ constructionLabel }}
      </div>

      <div class="count-caption">
        найдено в выбранном радиусе
      </div>
    </div>

    <!-- ФОРМАТЫ -->
    <div class="panel-section formats-section">
      <div class="section-heading">
        <div class="section-label">
          Доступные форматы
        </div>

        <span class="formats-count">
          {{ availableFormats.length }}
        </span>
      </div>

      <div
        v-if="availableFormats.length"
        class="formats-list"
      >
        <button
          v-for="format in availableFormats"
          :key="format.value"
          type="button"
          class="format-item"
          :class="{
            active: selectedFormats.includes(format.value)
          }"
          @click="toggleFormat(format.value)"
        >
          <span class="format-name">
            {{ format.label }}
          </span>

          <strong class="format-count">
            {{ format.count }}
          </strong>
        </button>
      </div>

      <div
        v-else
        class="formats-empty"
      >
        В выбранном радиусе
        нет доступных форматов.
      </div>
    </div>

    <div class="point-status">
      <span class="status-dot"></span>

      <span>
        {{ pointLabel || 'Укажите точку или адрес для поиска' }}
      </span>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    default: false
  },

  city: {
    type: String,
    default: ''
  },

  district: {
    type: String,
    default: ''
  },

  count: {
    type: Number,
    default: 0
  },

  radius: {
    type: Number,
    default: 3000
  },

  radiusOptions: {
    type: Array,
    default: () => [
      500,
      1000,
      3000,
      5000,
      10000
    ]
  },

  availableFormats: {
    type: Array,
    default: () => []
  },

  selectedFormats: {
    type: Array,
    default: () => []
  },

  pointLabel: {
    type: String,
    default: ''
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
  'update:radius',
  'update:selectedFormats',
  'update:coordinates',
  'update:address',
  'search',
  'search-address'
])

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

function formatRadius(value) {
  if (value < 1000) {
    return `${value} м`
  }

  return `${value / 1000} км`
}

function toggleFormat(value) {
  const values = [...props.selectedFormats]
  const index = values.indexOf(value)

  if (index === -1) {
    values.push(value)
  } else {
    values.splice(index, 1)
  }

  emit('update:selectedFormats', values)
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

  color: #e12a1f;

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

  color: #17212b;

  font-size: 11px;
  font-weight: 900;

  letter-spacing: 0.8px;

  text-transform: uppercase;
}

.input-row {
  display: flex;
  align-items: stretch;

  gap: 6px;
}

.search-input {
  min-width: 0;
  flex: 1;

  height: 42px;

  padding: 0 12px;

  border: 1px solid #dce2e6;
  border-radius: 10px;

  outline: none;

  background: white;
  color: #17212b;

  font-size: 13px;

  transition: 0.2s ease;
}

.search-input::placeholder {
  color: #a1adb5;
}

.search-input:focus {
  border-color: #17212b;

  box-shadow:
    0 0 0 3px rgba(23, 33, 43, 0.07);
}

.input-action {
  width: 42px;
  min-width: 42px;

  border: 0;
  border-radius: 10px;

  background: #17212b;
  color: white;

  cursor: pointer;

  font-size: 20px;
  font-weight: 700;

  transition: 0.2s ease;
}

.input-action:hover {
  background: #e12a1f;
}

.input-hint {
  margin-top: 6px;

  color: #8b98a1;

  font-size: 10px;
  line-height: 1.4;
}

.radius-list {
  display: flex;
  flex-wrap: wrap;

  gap: 7px;
}

.radius-button {
  padding: 8px 11px;

  border: 1px solid #dce2e6;
  border-radius: 9px;

  background: white;
  color: #60707c;

  cursor: pointer;

  font-size: 11px;
  font-weight: 800;

  transition: 0.2s ease;
}

.radius-button:hover {
  border-color: #17212b;
  color: #17212b;
}

.radius-button.active {
  border-color: #17212b;

  background: #17212b;
  color: white;
}

.search-button {
  width: 100%;

  display: flex;
  align-items: center;
  justify-content: center;

  gap: 9px;

  margin-top: 22px;

  min-height: 46px;

  border: 0;
  border-radius: 12px;

  background: #e12a1f;
  color: white;

  cursor: pointer;

  font-size: 11px;
  font-weight: 900;

  letter-spacing: 0.8px;

  box-shadow:
    0 8px 22px rgba(225, 42, 31, 0.22);

  transition: 0.2s ease;
}

.search-button:hover {
  background: #c92219;

  transform: translateY(-1px);
}

.search-button-icon {
  font-size: 18px;
}

.point-location {
  display: flex;
  align-items: flex-start;

  gap: 12px;

  margin-top: 20px;
  padding-top: 18px;

  border-top: 1px solid #e5e9ec;
}

.location-marker {
  width: 34px;
  height: 34px;

  display: grid;
  place-items: center;

  border-radius: 10px;

  background: #fff1ef;

  font-size: 16px;
}

.location-content {
  min-width: 0;

  display: flex;
  flex-direction: column;
}

.location-label {
  margin-bottom: 4px;

  color: #8b98a1;

  font-size: 10px;
  font-weight: 800;

  letter-spacing: 0.8px;
  text-transform: uppercase;
}

.location-content strong {
  color: #17212b;

  font-size: 15px;
  line-height: 1.2;
}

.location-district {
  margin-top: 4px;

  color: #71808c;

  font-size: 12px;
}

.location-point {
  margin-top: 5px;

  color: #8b98a1;

  font-size: 10px;
}

.result-count {
  margin-top: 18px;

  padding: 18px;

  text-align: center;

  border-radius: 16px;

  background:
    linear-gradient(
      135deg,
      #17212b,
      #293844
    );

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

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.formats-count {
  min-width: 22px;
  height: 22px;

  display: grid;
  place-items: center;

  border-radius: 50%;

  background: #f0f3f5;
  color: #71808c;

  font-size: 10px;
  font-weight: 800;
}

.formats-list {
  display: flex;
  flex-direction: column;

  gap: 6px;

  margin-top: 10px;
}

.format-item {
  width: 100%;

  display: flex;
  align-items: center;
  justify-content: space-between;

  padding: 10px 12px;

  border: 1px solid #e2e7ea;
  border-radius: 11px;

  background: white;
  color: #17212b;

  cursor: pointer;

  text-align: left;

  transition: 0.2s ease;
}

.format-item:hover {
  border-color: #17212b;

  transform: translateX(-2px);
}

.format-item.active {
  border-color: #e12a1f;

  background: #fff5f4;
}

.format-name {
  font-size: 12px;
  font-weight: 700;
}

.format-count {
  min-width: 24px;

  text-align: right;

  color: #e12a1f;

  font-size: 13px;
}

.formats-empty {
  margin-top: 10px;

  padding: 14px;

  border-radius: 10px;

  background: #f4f6f7;
  color: #8b98a1;

  font-size: 11px;
  line-height: 1.5;
}

.point-status {
  display: flex;
  align-items: center;

  gap: 7px;

  margin-top: 20px;
  padding-top: 14px;

  border-top: 1px solid #e5e9ec;

  color: #71808c;

  font-size: 10px;
}

.status-dot {
  width: 7px;
  height: 7px;

  flex: 0 0 7px;

  border-radius: 50%;

  background: #e12a1f;

  box-shadow:
    0 0 0 4px rgba(225, 42, 31, 0.12);
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
