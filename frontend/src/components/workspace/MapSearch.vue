<template>
  <div class="search-card">

    <div class="search-icon">⌕</div>

    <input
      :value="modelValue"
      type="search"
      placeholder="Поиск по адресу, городу или номеру"
      @input="$emit('update:modelValue', $event.target.value)"
    >

    <div class="count">
      {{ count }}
    </div>

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

defineEmits([
  'update:modelValue'
])
</script>

<style scoped>
.search-card {
  position: absolute;

  z-index: 700;

  top: 22px;
  left: 22px;

  width: min(520px, calc(100% - 44px));

  height: 52px;

  display: flex;
  align-items: center;
  gap: 10px;

  padding: 0 12px;

  background: rgba(255,255,255,.97);

  border: 1px solid rgba(220,225,228,.9);

  border-radius: 15px;

  box-shadow: 0 10px 35px rgba(25,35,45,.15);
}

.search-icon {
  width: 30px;
  height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;

  color: #71808c;

  font-size: 23px;
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

.count {
  padding: 6px 9px;

  border-radius: 8px;

  background: #f2f4f5;

  color: #596771;

  font-size: 11px;
  font-weight: 800;
}
</style>
