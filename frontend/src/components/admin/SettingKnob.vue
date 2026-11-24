<template>
  <div class="setting-knob">
    <q-knob
      :model-value="Number(value)"
      :min="Number(min)"
      :max="Number(max)"
      :step="Number(step)"
      size="62px"
      :thickness="0.16"
      color="amber"
      track-color="grey-4"
      show-value
      class="setting-knob__dial"
      @update:model-value="onInput"
    >
      <span class="setting-knob__value">
        {{ display }}
        <small v-if="unit">{{ unit }}</small>
      </span>
    </q-knob>
    <span class="setting-knob__label">{{ label }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  min: { type: [Number, String], default: 0 },
  max: { type: [Number, String], default: 100 },
  step: { type: [Number, String], default: 1 },
  unit: { type: String, default: '' }
})

const emit = defineEmits(['update:value'])

const display = computed(() => {
  const number = Number(props.value)
  if (!Number.isFinite(number)) return '—'
  const decimals = Number(props.step) < 1 ? 2 : 0
  return String(Math.round(number * 10 ** decimals) / 10 ** decimals)
})

function onInput(value) {
  emit('update:value', value)
}
</script>

<style scoped>
.setting-knob {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 78px;
}

.setting-knob__dial {
  flex: none;
}

.setting-knob__value {
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}

.setting-knob__value small {
  color: #64748b;
  font-size: 9px;
}

.setting-knob__label {
  max-width: 78px;
  color: #64748b;
  font-size: 10.5px;
  line-height: 1.2;
  text-align: center;
}
</style>
