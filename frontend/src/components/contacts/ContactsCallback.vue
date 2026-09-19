<template>
  <section
    v-if="data?.enabled !== false"
    class="callback"
  >
    <div class="callback-copy">
      <div class="eyebrow">ОБРАТНАЯ СВЯЗЬ</div>
      <h2>{{ data?.title }}</h2>
      <p>{{ data?.text }}</p>

      <a
        v-if="phone"
        class="callback-phone"
        :href="`tel:${phone.replace(/[^+0-9]/g, '')}`"
      >
        {{ phone }}
      </a>
    </div>

    <form class="form" @submit.prevent="submit">
      <div
        v-for="field in data.fields"
        :key="field.name"
        class="field"
      >
        <textarea
          v-if="field.type === 'textarea'"
          v-model="form[field.name]"
          :placeholder="field.label"
          :required="field.required"
          rows="4"
        />

        <input
          v-else
          v-model="form[field.name]"
          :type="field.type"
          :placeholder="field.label"
          :required="field.required"
        >
      </div>

      <button type="submit">
        Отправить заявку →
      </button>

      <small>
        Нажимая кнопку, вы соглашаетесь с обработкой персональных данных.
      </small>
    </form>
  </section>
</template>

<script setup>
import { reactive } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({
      fields: []
    })
  },
  phone: {
    type: String,
    default: ''
  }
})

const form = reactive({})

for (const field of props.data?.fields || []) {
  form[field.name] = ''
}

function submit() {
  console.log('Контактная форма:', { ...form })

  alert('Спасибо! Заявка подготовлена к отправке.')

  for (const key of Object.keys(form)) {
    form[key] = ''
  }
}
</script>

<style scoped>
.callback {
  margin: 0 5vw 70px;
  padding: 50px;
  border-radius: 26px;
  background: #17212b;
  color: white;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
}

.eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .16em;
  opacity: .55;
}

h2 {
  margin: 12px 0 18px;
  font-size: clamp(34px, 4vw, 52px);
  letter-spacing: -.035em;
}

p {
  max-width: 520px;
  color: rgba(255,255,255,.7);
  line-height: 1.55;
}

.callback-phone {
  display: inline-block;
  margin-top: 22px;
  color: white;
  font-size: 22px;
  font-weight: 800;
  text-decoration: none;
}

.form {
  display: grid;
  gap: 12px;
  align-content: start;
}

.field input,
.field textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(255,255,255,.15);
  border-radius: 12px;
  padding: 15px 16px;
  background: rgba(255,255,255,.06);
  color: white;
  outline: none;
  font: inherit;
}

.field input::placeholder,
.field textarea::placeholder {
  color: rgba(255,255,255,.5);
}

.form button {
  margin-top: 6px;
  padding: 15px 18px;
  border: 0;
  border-radius: 12px;
  background: white;
  color: #17212b;
  font-weight: 800;
  cursor: pointer;
}

.form small {
  color: rgba(255,255,255,.45);
  line-height: 1.4;
}

@media (max-width: 800px) {
  .callback {
    grid-template-columns: 1fr;
    padding: 30px;
  }
}
</style>
