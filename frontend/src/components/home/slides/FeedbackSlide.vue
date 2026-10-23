<template>
  <h1 class="slide-title">{{ slide.title }}</h1>
  <p v-if="slide.text" class="slide-text">{{ slide.text }}</p>

  <form class="feedback" @submit.prevent="submit">
    <input
      v-model="form.name"
      class="fb-input"
      type="text"
      placeholder="Имя"
      aria-label="Ваше имя"
      autocomplete="name"
    />
    <input
      v-model="form.phone"
      class="fb-input"
      type="tel"
      placeholder="Телефон"
      aria-label="Телефон для связи"
      autocomplete="tel"
    />
    <textarea
      v-model="form.message"
      class="fb-input fb-textarea"
      placeholder="Сообщение"
      aria-label="Сообщение"
      rows="3"
    ></textarea>

    <button type="submit" class="slide-btn fb-submit" :disabled="sending">
      {{ sending ? 'Отправляем…' : 'Отправить' }}
    </button>

    <div v-if="sent" class="fb-note fb-note--ok">
      Спасибо! Мы свяжемся с вами.
    </div>
    <div v-else-if="formError" class="fb-note fb-note--err">
      {{ formError }}
    </div>
  </form>
</template>

<script setup>
import { ref } from 'vue'

/*
 * Слайд «Обратная связь»: форма уходит публичным POST /api/feedback.
 * Вынесен из HomeSlider — состояние и отправка полностью локальные.
 */
defineProps({
  slide: {
    type: Object,
    required: true
  }
})

const form = ref({ name: '', phone: '', message: '' })
const sending = ref(false)
const sent = ref(false)
const formError = ref('')

async function submit() {
  formError.value = ''
  /* Новый сабмит всегда снимает прошлое «Спасибо», иначе ошибка не видна. */
  sent.value = false

  if (!form.value.name.trim()) {
    formError.value = 'Укажите имя.'
    return
  }

  const phoneDigits = form.value.phone.replace(/\D/g, '')

  if (phoneDigits.length < 10 || phoneDigits.length > 15) {
    formError.value = 'Укажите телефон в формате +7 (999) 123-45-67.'
    return
  }

  sending.value = true

  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.value.name.trim(),
        phone: form.value.phone.trim(),
        message: form.value.message.trim()
      })
    })

    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(
        data?.detail || `Не удалось отправить (HTTP ${res.status})`
      )
    }

    sent.value = true
    form.value = { name: '', phone: '', message: '' }
  } catch (exc) {
    formError.value = String(exc.message || exc)
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
/*
 * Типографика слайда: у каждого слайда свои scoped-стили, поэтому
 * базовые классы продублированы (общий список стилей у HomeSlider).
 */
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

.feedback {
  display: flex;
  flex-direction: column;
  gap: 10px;

  width: min(460px, 92vw);
  margin-top: 8px;
}

.fb-input {
  padding: 12px 14px;

  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 10px;

  background: rgba(255, 255, 255, 0.1);
  color: #fff;

  font-family: inherit;
  font-size: 14px;

  outline: none;
}

.fb-input:focus-visible {
  outline: 2px solid #fff;
  outline-offset: 2px;
}

.fb-input::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.fb-textarea {
  resize: vertical;
}

.fb-submit {
  align-self: center;
}

.fb-note {
  font-size: 13px;
}

.fb-note--ok {
  color: #86efac;
}

.fb-note--err {
  color: #fca5a5;
}
</style>
