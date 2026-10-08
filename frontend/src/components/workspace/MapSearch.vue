<template>
  <div class="search-card">
    <div class="count">{{ count }}</div>

    <input
      :value="modelValue"
      type="search"
      placeholder="Поиск по адресу, городу или номеру"
      @input="$emit('update:modelValue', $event.target.value)"
      @keydown.enter="onSearch"
    >

    <button
      type="button"
      class="search-icon"
      title="Найти"
      @click="onSearch"
    >
      ⌕
    </button>
  </div>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: ''
  },

  count: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits([
  'update:modelValue',
  'search'
])

function onSearch() {
  emit('search')
}
</script>

<style scoped>
.search-card {
  position: static;

  width: 400px;
  max-width: calc(100vw - 420px);

  height: 44px;

  display: flex;
  align-items: center;
  gap: 8px;

  padding: 0 8px 0 10px;

  background: rgba(255,255,255,.97);

  border: 1px solid rgba(220,225,228,.9);

  border-radius: 12px;

  box-shadow: 0 10px 35px rgba(25,35,45,.15);
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

  color: #71808c;

  font-size: 23px;

  cursor: pointer;

  transition: background .18s ease;
}

.search-icon:hover {
  background: #f0f3f4;
}
</style>