<template>
  <div class="search-card">
    <div class="count">{{ count }}</div>

    <input
      :value="modelValue"
      type="search"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown.enter="onSearch"
    />

    <div v-if="showMode" class="search-mode">
      <button
        type="button"
        :class="{ active: mode === 'coords' }"
        @click="$emit('update:mode', 'coords')"
      >
        Координаты
      </button>

      <button
        type="button"
        :class="{ active: mode === 'address' }"
        @click="$emit('update:mode', 'address')"
      >
        Адрес
      </button>
    </div>

    <button type="button" class="search-icon" title="Найти" @click="onSearch">
      ⌕
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

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

const emit = defineEmits(['update:modelValue', 'update:mode', 'search'])

const placeholder = computed(() => {
  if (!props.showMode) {
    return 'Поиск по адресу, городу или номеру'
  }

  return props.mode === 'coords'
    ? 'Координаты: 47.2315, 39.7233'
    : 'Введите адрес'
})

function onSearch() {
  emit('search')
}
</script>

<style scoped>
.search-card {
  position: static;

  width: min(400px, 100%);
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
</style>
