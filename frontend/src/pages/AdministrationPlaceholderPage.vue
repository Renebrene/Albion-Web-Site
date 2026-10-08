<template>
  <q-page class="administration-placeholder">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>{{ title }}</h1>
        <p v-if="text">{{ text }}</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <section class="section-card">
      <div class="placeholder-body">
        <q-icon name="construction" size="44px" />

        <div class="placeholder-title">
          Раздел находится в разработке
        </div>

        <div class="placeholder-note">
          Функциональность появится в следующих обновлениях админ-панели.
        </div>
      </div>
    </section>
  </q-page>
</template>

<script setup>
import { useRouter } from 'vue-router'

defineProps({
  title: {
    type: String,
    required: true
  },
  text: {
    type: String,
    default: ''
  }
})

const router = useRouter()
</script>

<style scoped>
.administration-placeholder {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.eyebrow {
  color: #8b8b8b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.page-header h1 {
  margin: 4px 0;
  font-size: 30px;
  line-height: 1.1;
  font-weight: 800;
}

.page-header p {
  margin: 0;
  color: #777;
}

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.placeholder-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;

  padding: 48px 20px;

  color: #8b8b8b;

  text-align: center;
}

.placeholder-title {
  color: #17212b;

  font-size: 18px;
  font-weight: 800;
}

.placeholder-note {
  font-size: 14px;
}
</style>
