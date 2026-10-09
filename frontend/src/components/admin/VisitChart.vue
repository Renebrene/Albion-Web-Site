<template>
  <div class="visit-chart">
    <svg
      class="visit-chart-svg"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      :aria-label="ariaLabel"
    >
      <!-- Горизонтальная сетка -->
      <g class="grid">
        <template v-for="line in gridLines" :key="line.y">
          <line :x1="PAD_L" :x2="WIDTH - PAD_R" :y1="line.y" :y2="line.y" />
          <text :x="PAD_L - 8" :y="line.y + 4" text-anchor="end">
            {{ line.value }}
          </text>
        </template>
      </g>

      <!-- Столбцы визитов -->
      <g class="bars">
        <rect
          v-for="bar in bars"
          :key="bar.date"
          :x="bar.x"
          :y="bar.y"
          :width="bar.w"
          :height="bar.h"
          rx="3"
          class="visit-bar"
        >
          <title>{{ bar.title }}</title>
        </rect>
      </g>

      <!-- Линия уникальных посетителей -->
      <polyline
        v-if="uniquePoints"
        class="unique-line"
        :points="uniquePoints"
      />

      <!-- Подписи дат -->
      <g class="axis">
        <text
          v-for="label in dateLabels"
          :key="label.date"
          :x="label.x"
          :y="HEIGHT - 8"
          text-anchor="middle"
        >
          {{ label.text }}
        </text>
      </g>
    </svg>

    <div class="visit-chart-legend">
      <span class="legend-item"><i class="dot dot-bar" /> визиты</span>
      <span class="legend-item"><i class="dot dot-line" /> уникальные</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const WIDTH = 960
const HEIGHT = 260
const PAD_L = 46
const PAD_R = 16
const PAD_T = 16
const PAD_B = 34

const MAX_LABELS = 8

const plotW = WIDTH - PAD_L - PAD_R
const plotH = HEIGHT - PAD_T - PAD_B

const ariaLabel = computed(
  () => `График визитов по дням, точек: ${props.items.length}`
)

const maxValue = computed(() => {
  const values = props.items.flatMap(item => [
    Number(item.visits) || 0,
    Number(item.unique) || 0
  ])

  return Math.max(1, ...values)
})

function niceMax(value) {
  if (value <= 5) return 5

  const step = value <= 50 ? 10 : value <= 500 ? 50 : 100

  return Math.ceil(value / step) * step
}

const topValue = computed(() => niceMax(maxValue.value))

function yOf(value) {
  return PAD_T + plotH * (1 - value / topValue.value)
}

const gridLines = computed(() => {
  const count = 4
  const lines = []

  for (let i = 0; i <= count; i += 1) {
    const value = Math.round((topValue.value * i) / count)

    lines.push({ value, y: yOf(value) })
  }

  return lines
})

const slot = computed(() =>
  props.items.length ? plotW / props.items.length : plotW
)

const bars = computed(() => {
  const width = Math.max(2, Math.min(slot.value * 0.62, 42))
  const offset = (slot.value - width) / 2

  return props.items.map((item, index) => {
    const visits = Number(item.visits) || 0
    const y = yOf(visits)

    return {
      date: item.date,
      x: PAD_L + slot.value * index + offset,
      y,
      w: width,
      h: Math.max(0, PAD_T + plotH - y),
      title: `${item.date}: ${visits} визитов, ${Number(item.unique) || 0} уникальных`
    }
  })
})

const uniquePoints = computed(() => {
  if (props.items.length < 2) {
    return ''
  }

  return props.items
    .map((item, index) => {
      const x = PAD_L + slot.value * index + slot.value / 2
      const y = yOf(Number(item.unique) || 0)

      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const dateLabels = computed(() => {
  const total = props.items.length

  if (!total) {
    return []
  }

  const step = Math.max(1, Math.ceil(total / MAX_LABELS))

  return props.items
    .map((item, index) => {
      if (index % step !== 0 && index !== total - 1) {
        return null
      }

      // «2026-10-09» → «09.10»
      const [, month, day] = String(item.date).split('-')

      return {
        date: item.date,
        x: PAD_L + slot.value * index + slot.value / 2,
        text: month && day ? `${day}.${month}` : item.date
      }
    })
    .filter(Boolean)
})
</script>

<style scoped>
.visit-chart {
  width: 100%;
}

.visit-chart-svg {
  display: block;
  width: 100%;
  height: auto;
}

.grid line {
  stroke: #eef1f3;
  stroke-width: 1;
}

.grid text,
.axis text {
  fill: #9aa6ae;
  font-size: 11px;
}

.visit-bar {
  fill: var(--albion-accent, #e12a1f);
  opacity: 0.85;
}

.visit-bar:hover {
  opacity: 1;
}

.unique-line {
  fill: none;
  stroke: #2f6f9f;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.visit-chart-legend {
  display: flex;
  gap: 18px;
  margin-top: 6px;
  color: #66727c;
  font-size: 12px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: inline-block;
}

.dot-bar {
  background: var(--albion-accent, #e12a1f);
}

.dot-line {
  background: #2f6f9f;
  border-radius: 50%;
}
</style>
