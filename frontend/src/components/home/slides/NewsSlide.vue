<template>
  <h1 class="slide-title">{{ slide.title }}</h1>
  <p v-if="slide.text" class="slide-text">{{ slide.text }}</p>

  <div class="news-grid">
    <a
      v-for="item in topNews"
      :key="item.slug"
      class="news-card"
      :href="`/novosti/${item.slug}`"
    >
      <div class="news-date">
        {{ formatDate(item.date || item.published_at) }}
      </div>
      <div class="news-title">{{ item.title }}</div>
      <div v-if="item.excerpt" class="news-excerpt">
        {{ item.excerpt }}
      </div>
    </a>
  </div>

  <div class="news-actions">
    <template v-for="btn in buttons" :key="btn.key">
      <button
        v-if="isFormButton(btn)"
        type="button"
        class="slide-btn"
        :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
        @click="$emit('open-form')"
      >
        {{ btn.label }}
      </button>
      <a
        v-else
        class="slide-btn"
        :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
        :href="btn.url"
      >
        {{ btn.label }}
      </a>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { isFormButton, slideButtons } from './slideButtons'

/*
 * Слайд «Новости»: три последние публикации и кнопки из админки.
 * Список новостей грузит HomeSlider (он общий для страницы) и передаёт
 * сюда готовым.
 */
const props = defineProps({
  slide: {
    type: Object,
    required: true
  },

  news: {
    type: Array,
    default: () => []
  }
})

defineEmits(['open-form'])

const NEWS_FALLBACK_BUTTONS = [
  { label: 'Все новости', url: '/novosti', variant: 'ghost' }
]

const topNews = computed(() => props.news.slice(0, 3))

const buttons = computed(() => slideButtons(props.slide, NEWS_FALLBACK_BUTTONS))

function formatDate(value) {
  if (!value) return ''

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  const pad = n => String(n).padStart(2, '0')

  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`
}
</script>

<style scoped>
/* Базовые классы слайда — см. комментарий в FeedbackSlide.vue. */
.slide-title {
  margin: 0;

  font-size: clamp(26px, 4vw, 56px);
  font-weight: 900;
  letter-spacing: 0.04em;
}

.slide-text {
  margin: 0;

  max-width: 780px;

  font-size: clamp(14px, 1.5vw, 20px);
  opacity: 0.9;
}

.slide-btn {
  margin-top: 8px;
  padding: 12px 26px;

  border: 0;
  border-radius: 999px;

  background: var(--albion-accent, #e2231a);
  color: #fff;

  font-family: inherit;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-decoration: none;

  cursor: pointer;

  transition: transform 0.15s ease;
}

.slide-btn:hover {
  transform: translateY(-2px);
}

.slide-btn--ghost {
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: transparent;
}

/* Обёртка списка кнопок новостного и текстового слайдов. */
.news-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;

  margin-top: 22px;
}

.news-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;

  width: min(1000px, 92vw);
  margin-top: 6px;
}

.news-card {
  display: block;

  padding: 16px;

  border-radius: 12px;

  background: rgba(255, 255, 255, 0.08);
  color: #fff;

  text-align: left;
  text-decoration: none;

  transition: transform 0.15s ease;
}

.news-card:hover {
  transform: translateY(-3px);
}

.news-date {
  font-size: 12px;
  opacity: 0.7;
}

.news-title {
  margin: 6px 0;

  font-size: 15px;
  font-weight: 700;
}

.news-excerpt {
  font-size: 13px;
  opacity: 0.82;
}

@media (max-width: 760px) {
  .news-grid {
    grid-template-columns: 1fr;
  }
}
</style>
