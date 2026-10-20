<template>
  <div class="search-box">
    <div class="search-card">
      <div class="count">{{ count }}</div>

      <input
        :value="modelValue"
        type="search"
        :placeholder="placeholder"
        autocomplete="off"
        @input="onInput"
        @keydown.enter="onSearch"
        @keydown.esc="clearSuggestions"
        @blur="onBlur"
      />

      <div v-if="showMode" class="search-mode">
        <button
          type="button"
          :class="{ active: mode === 'address' }"
          @click="setMode('address')"
        >
          Адрес
        </button>

        <button
          type="button"
          :class="{ active: mode === 'coords' }"
          @click="setMode('coords')"
        >
          Координаты
        </button>
      </div>

      <button type="button" class="search-icon" title="Найти" @click="onSearch">
        ⌕
      </button>
    </div>

    <!-- Подсказки геокодера: только в режиме поиска по точке и адресу. -->
    <div
      v-if="showSuggestions"
      class="search-suggestions"
      role="listbox"
      aria-label="Подсказки адреса"
    >
      <div v-if="suggestLoading" class="search-suggestion-state" role="status">
        Ищем адрес…
      </div>
      <div
        v-else-if="suggestError"
        class="search-suggestion-state search-suggestion-state--error"
        role="alert"
      >
        {{ suggestError }}
      </div>
      <button
        v-for="suggestion in suggestions"
        :key="suggestion.id"
        type="button"
        class="search-suggestion"
        role="option"
        @mousedown.prevent
        @click="selectSuggestion(suggestion)"
      >
        <span class="search-suggestion-title">
          {{ suggestion.title }}
        </span>
        <span v-if="suggestion.subtitle" class="search-suggestion-sub">
          {{ suggestion.subtitle }}
        </span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { suggestAddress } from '../../services/geoApi'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },

  count: {
    type: Number,
    default: 0
  },

  /* Переключатель Координаты/Адрес — только в режиме поиска по точке. */
  showMode: {
    type: Boolean,
    default: false
  },

  mode: {
    type: String,
    default: 'coords'
  }
})

const emit = defineEmits([
  'update:modelValue',
  'update:mode',
  'search',
  'select-suggestion'
])

const placeholder = computed(() => {
  if (!props.showMode) {
    return 'Город, улица или формат'
  }

  return props.mode === 'coords'
    ? 'Координаты: 47.2315, 39.7233'
    : 'Введите адрес'
})

/*
 * Подсказки — только для геокодера (режим точки). В карте и списке строка
 * остаётся обычным фильтром по базе: там подсказки не запрашиваются.
 */
const suggestions = ref([])
const suggestLoading = ref(false)
const suggestError = ref('')
let suggestTimer = null
let suggestSeq = 0

const isAddressMode = computed(() => props.showMode && props.mode === 'address')

const showSuggestions = computed(
  () =>
    isAddressMode.value &&
    (suggestLoading.value || suggestError.value || suggestions.value.length > 0)
)

function clearSuggestions() {
  suggestions.value = []
  suggestError.value = ''
  suggestLoading.value = false
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
  suggestLoading.value = true
  suggestError.value = ''

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
      suggestError.value = 'Не удалось получить подсказки адреса'
    }
  } finally {
    if (seq === suggestSeq) {
      suggestLoading.value = false
    }
  }
}

function onInput(event) {
  const value = event.target.value

  emit('update:modelValue', value)
  clearSuggestions()

  if (!isAddressMode.value || value.trim().length < 3) {
    return
  }

  suggestTimer = setTimeout(() => {
    suggestTimer = null
    void loadSuggestions(value)
  }, 300)
}

function selectSuggestion(suggestion) {
  emit('update:modelValue', suggestion?.display_name || suggestion?.query || '')
  clearSuggestions()
  emit('select-suggestion', suggestion)
}

function setMode(mode) {
  clearSuggestions()
  emit('update:mode', mode)
}

function onBlur() {
  /* Даём сработать клику по подсказке, затем закрываем список. */
  window.setTimeout(clearSuggestions, 150)
}

function onSearch() {
  clearSuggestions()
  emit('search')
}

watch(
  () => [props.mode, props.showMode],
  () => clearSuggestions()
)

onBeforeUnmount(clearSuggestions)
</script>

<style scoped>
.search-box {
  position: relative;

  /* Занимает всё оставшееся место в строке с переключателем режимов,
     но может сжиматься на узких экранах. */
  flex: 1 1 320px;
  width: auto;
  min-width: 0;
  max-width: 100%;
}

.search-card {
  position: static;

  width: 100%;
  max-width: 100%;
  height: 44px;

  display: flex;
  align-items: center;
  gap: 8px;

  padding: 0 8px 0 10px;

  background: rgba(255, 255, 255, 0.97);

  border: 1px solid rgba(220, 225, 228, 0.9);

  border-radius: 12px;

  box-shadow: 0 10px 35px rgba(25, 35, 45, 0.15);
}

.search-card:focus-within {
  border-color: #17212b;
  box-shadow: 0 0 0 3px rgba(23, 33, 43, 0.07);
}

/* счётчик — слева */
.count {
  padding: 5px 8px;

  border-radius: 8px;

  background: #17212b;

  color: #fff;

  font-size: 11px;
  font-weight: 800;

  white-space: nowrap;
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

/* Переключатель Координаты/Адрес — на краю поля */
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

/* иконка поиска — справа */
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

  font-size: 23px;

  cursor: pointer;

  transition: background 0.18s ease;
}

.search-icon:hover {
  background: #f0f3f4;
}

/* Подсказки адреса — под строкой поиска */
.search-suggestions {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 20;

  display: flex;
  flex-direction: column;

  max-height: 320px;
  padding: 5px;

  overflow-y: auto;

  background: rgba(255, 255, 255, 0.99);

  border: 1px solid rgba(220, 225, 228, 0.9);
  border-radius: 12px;

  box-shadow: 0 16px 40px rgba(25, 35, 45, 0.18);
}

.search-suggestion {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;

  width: 100%;
  padding: 8px 10px;

  border: 0;
  border-radius: 8px;

  background: transparent;

  text-align: left;

  cursor: pointer;
}

.search-suggestion:hover,
.search-suggestion:focus-visible {
  background: #f0f3f4;
}

.search-suggestion-title {
  color: #17212b;

  font-size: 12px;
  font-weight: 700;
}

.search-suggestion-sub {
  color: #7b878f;

  font-size: 11px;
}

.search-suggestion-state {
  padding: 9px 10px;

  color: #7b878f;

  font-size: 12px;
}

.search-suggestion-state--error {
  color: #8f1d16;
}
</style>
