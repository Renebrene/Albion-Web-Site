<template>
  <h1 class="slide-title">{{ slide.title }}</h1>
  <p class="slide-text">{{ slide.text }}</p>

  <div class="text-actions">
    <template v-for="btn in buttons" :key="btn.key">
      <!-- Кнопка без ссылки открывает слайд с формой — событие наверх. -->
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

import { isFormButton, textSlideButtons } from './slideButtons'

/*
 * Простой текстовый слайд: заголовок, текст и кнопки из админки. Это ещё
 * и запасной вариант — сюда попадают слайды неизвестного типа.
 */
const props = defineProps({
  slide: {
    type: Object,
    required: true
  }
})

defineEmits(['open-form'])

const buttons = computed(() => textSlideButtons(props.slide))
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

.text-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;

  margin-top: 20px;
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
</style>
