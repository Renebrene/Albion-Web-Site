<template>
  <section class="request-section">
    <div class="request-inner">
      <div class="request-head">
        <h2>Оставить заявку</h2>
        <p>
          Оставьте контакты — подберём конструкции под задачу и пришлём подборку
          с ценами.
        </p>
      </div>

      <div class="request-form">
        <q-input v-model="form.name" dense outlined label="Имя" />
        <q-input
          v-model="form.phone"
          dense
          outlined
          label="Телефон"
          placeholder="+7 900 000-00-00"
        />
        <q-input
          v-model="form.comment"
          dense
          outlined
          autogrow
          type="textarea"
          label="Комментарий"
        />

        <div v-if="error" class="request-error">{{ error }}</div>
        <div v-else-if="done" class="request-ok">
          Спасибо! Заявка отправлена — мы свяжемся с вами.
        </div>

        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Отправить заявку"
          class="request-submit"
          :loading="sending"
          :disable="done"
          @click="submit"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'

const form = reactive({ name: '', phone: '', comment: '' })

const sending = ref(false)
const done = ref(false)
const error = ref('')

async function submit() {
  sending.value = true
  error.value = ''

  try {
    const response = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: form.name,
        phone: form.phone,
        comment: form.comment
      })
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error(data?.detail || 'Не удалось отправить заявку')
    }

    done.value = true
    form.comment = ''
  } catch (exc) {
    error.value = String(exc?.message || exc)
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.request-section {
  padding: 8px 24px 48px;
}

.request-inner {
  max-width: 720px;
  margin: 0 auto;

  padding: 24px;
  border: 1px solid #e3e7ea;
  border-radius: 16px;
  background: #fff;
}

.request-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 800;
}

.request-head p {
  margin: 0 0 18px;
  color: #5b6b78;
  font-size: 14px;
  line-height: 1.5;
}

.request-form .q-field + .q-field {
  margin-top: 10px;
}

.request-submit {
  margin-top: 16px;
}

.request-error,
.request-ok {
  margin-top: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
}

.request-error {
  border: 1px solid #e57373;
  background: #fdecea;
  color: #c62828;
}

.request-ok {
  border: 1px solid #a5d6a7;
  background: #e8f5e9;
  color: #2e7d32;
}

@media (max-width: 700px) {
  .request-section {
    padding: 8px 14px 36px;
  }

  .request-inner {
    padding: 18px;
  }
}
</style>
