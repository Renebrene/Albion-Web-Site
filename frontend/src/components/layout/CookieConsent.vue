<template>
  <transition name="cookie-rise" appear>
    <aside
      v-if="visible"
      class="cookie-consent"
      role="region"
      aria-label="Использование cookie и веб-аналитики"
    >
      <p class="cookie-text">
        Используя настоящий сайт, вы предоставляете согласие на обработку ваших
        персональных данных с помощью сервисов веб-аналитики.
      </p>

      <button type="button" class="cookie-accept" @click="accept">
        Согласен
      </button>
    </aside>
  </transition>
</template>

<script setup>
import { ref } from 'vue'

/*
 * Плашка о cookie и веб-аналитике. Показывается один раз: факт согласия
 * хранится в localStorage и живёт до очистки хранилища браузера — как
 * портфель (см. composables/usePortfolio.js). Серверу согласие не уходит:
 * аналитика подключается и без него.
 */
const STORAGE_KEY = 'albion_cookie_consent'

function readConsent() {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch (error) {
    /* приватный режим или запрет хранилища — считаем, что согласия нет */
    return false
  }
}

const visible = ref(!readConsent())

function accept() {
  visible.value = false

  try {
    localStorage.setItem(STORAGE_KEY, '1')
  } catch (error) {
    /* запомнить не удалось — при следующем визите плашка появится снова */
  }
}
</script>

<style scoped>
.cookie-consent {
  /* Над подвалом (z-index 40) и над слоями карты: у Leaflet панели и
     элементы управления занимают 400…1000, а своего стекинг-контекста
     у них нет — с меньшим z-index плашку закрывали тайлы. Выше оверлея
     состояния рабочей области (1600), но ниже диалогов Quasar. */
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(var(--albion-footer-h, 46px) + 16px);
  z-index: 1700;

  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px 20px;

  max-width: 900px;
  margin: 0 auto;
  padding: 14px 18px;

  border-radius: var(--albion-radius-cards, 18px);

  background: var(--albion-accent, #e12a1f);
  color: #fff;

  box-shadow: 0 12px 32px rgba(23, 33, 43, 0.3);

  font-size: 13px;
  line-height: 1.45;
}

.cookie-text {
  flex: 1 1 420px;

  margin: 0;
}

.cookie-accept {
  flex: 0 0 auto;

  padding: 9px 22px;

  border: 0;
  border-radius: var(--albion-radius-buttons, 10px);

  background: #fff;
  color: var(--albion-accent, #e12a1f);

  cursor: pointer;

  font-family: inherit;
  font-size: 13px;
  font-weight: 800;

  transition: background 0.15s ease;
}

.cookie-accept:hover {
  background: rgba(255, 255, 255, 0.88);
}

/* Появление/скрытие: плавный подъём снизу. */
.cookie-rise-enter-active,
.cookie-rise-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}

.cookie-rise-enter-from,
.cookie-rise-leave-to {
  opacity: 0;
  transform: translateY(12px);
}

@media (prefers-reduced-motion: reduce) {
  .cookie-rise-enter-active,
  .cookie-rise-leave-active {
    transition: none;
  }
}

@media (max-width: 640px) {
  .cookie-consent {
    left: 10px;
    right: 10px;
    bottom: calc(var(--albion-footer-h, 46px) + 10px);

    padding: 13px 15px;
  }
}
</style>
