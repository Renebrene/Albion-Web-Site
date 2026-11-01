<template>
  <transition name="cookie-rise" appear>
    <aside
      v-if="visible"
      class="cookie-consent"
      role="region"
      aria-label="Использование cookie и веб-аналитики"
    >
      <p class="cookie-text">
        Мы используем файлы cookie. Это позволяет нам анализировать
        взаимодействие посетителей с сайтом и делать его лучше. Продолжая
        пользоваться сайтом, вы соглашаетесь с использованием файлов cookie и
        нашей
        <a
          :href="privacyUrl || '#'"
          class="cookie-link"
          target="_blank"
          rel="noopener noreferrer"
        >
          Политикой конфиденциальности</a
        >.
      </p>

      <button type="button" class="cookie-accept" @click="accept">
        ПРИНЯТЬ
      </button>
    </aside>
  </transition>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { safeCmsUrl } from '../../utils/safeCmsUrl'

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

/* Ссылка на политику берётся из того же меню подвала, что и в футере. */
const privacyUrl = ref('')

onMounted(async () => {
  try {
    const response = await fetch('/api/site-menu')
    const data = await response.json()
    const item = (data?.footer || []).find(entry => entry.key === 'privacy')

    if (item) {
      privacyUrl.value = safeCmsUrl(item.url) || ''
    }
  } catch (error) {
    /* без ссылки плашка всё равно остаётся рабочей */
  }
})

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
  right: 18px;
  bottom: calc(var(--albion-footer-h, 46px) + 14px);
  z-index: 1700;

  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;

  width: min(360px, calc(100vw - 24px));

  padding: 12px 14px;

  border: 1px solid #e3e8eb;
  border-radius: 12px;

  background: rgba(255, 255, 255, 0.98);
  color: #17212b;

  box-shadow: 0 12px 32px rgba(23, 33, 43, 0.18);

  font-size: 11.5px;
  line-height: 1.45;
}

.cookie-text {
  margin: 0;
}

.cookie-link {
  color: var(--albion-accent, #e12a1f);

  font-weight: 700;

  text-decoration: underline;
  text-underline-offset: 2px;
}

.cookie-link:hover {
  text-decoration-thickness: 2px;
}

.cookie-accept {
  align-self: flex-end;

  padding: 7px 16px;

  border: 0;
  border-radius: 8px;

  background: var(--albion-accent, #e12a1f);
  color: #fff;

  cursor: pointer;

  font-family: inherit;
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.04em;

  transition: filter 0.15s ease;
}

.cookie-accept:hover {
  filter: brightness(0.94);
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
    right: 10px;
    bottom: calc(var(--albion-footer-h, 46px) + 10px);

    width: calc(100vw - 20px);

    padding: 12px 14px;
  }
}
</style>
