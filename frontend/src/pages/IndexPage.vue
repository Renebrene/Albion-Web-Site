<template>
  <q-page class="page">
    <div class="container">
      <div class="hero">
        <div>
          <div class="eyebrow">ALBION · НАРУЖНАЯ РЕКЛАМА</div>

          <h1>
            Реклама,<br />
            которая работает
          </h1>

          <p> Собственная сеть рекламных конструкций в Ростовской области. </p>

          <q-btn
            unelevated
            rounded
            color="negative"
            label="Найти рекламную конструкцию"
            size="lg"
            @click="loadData"
          />
        </div>

        <div class="stats">
          <div class="stat">
            <strong>{{ constructionsCount }}</strong>
            <span>конструкций</span>
          </div>

          <div class="stat">
            <strong>{{ citiesCount }}</strong>
            <span>городов и территорий</span>
          </div>

          <div class="stat">
            <strong>{{ formatsCount }}</strong>
            <span>форматов</span>
          </div>
        </div>
      </div>

      <q-banner v-if="error" class="bg-red-1 text-negative q-mb-lg" rounded>
        {{ error }}
      </q-banner>

      <div v-if="loading" class="loading">
        Загружаем рекламные возможности…
      </div>

      <div v-if="loaded" class="success">
        ✓ API подключено. Данные загружены.
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getConstructions } from '@/services/api'

const constructions = ref([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

const constructionsCount = computed(() => constructions.value.length)

const citiesCount = computed(
  () => new Set(constructions.value.map(x => x.city)).size
)

const formatsCount = computed(
  () => new Set(constructions.value.map(x => x.type)).size
)

async function loadData() {
  loading.value = true
  error.value = ''

  try {
    constructions.value = await getConstructions()
    loaded.value = true
  } catch (err) {
    error.value = 'Не удалось подключиться к серверу данных: ' + err.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  background: #f5f5f5;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 70px 40px;
}

.hero {
  min-height: 520px;
  border-radius: 32px;
  padding: 70px;
  background: #171717;
  color: white;

  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 60px;
}

.eyebrow {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #e52b20;
  margin-bottom: 25px;
}

h1 {
  margin: 0 0 25px;
  font-size: clamp(52px, 6vw, 90px);
  line-height: 0.92;
  font-weight: 800;
  letter-spacing: -4px;
}

.hero p {
  max-width: 520px;
  font-size: 20px;
  line-height: 1.5;
  color: #c8c8c8;
  margin-bottom: 35px;
}

.stats {
  display: grid;
  gap: 20px;
  min-width: 230px;
}

.stat {
  border: 1px solid #333;
  border-radius: 20px;
  padding: 22px 25px;
}

.stat strong {
  display: block;
  font-size: 38px;
  font-weight: 800;
}

.stat span {
  color: #999;
  font-size: 14px;
}

.loading {
  margin-top: 25px;
  padding: 20px;
  border-radius: 16px;
  background: white;
}

.success {
  margin-top: 25px;
  padding: 20px;
  border-radius: 16px;
  background: #e9f7ec;
  color: #237333;
}

@media (max-width: 800px) {
  .container {
    padding: 20px;
  }

  .hero {
    padding: 35px;
    flex-direction: column;
    align-items: flex-start;
  }

  .stats {
    width: 100%;
  }
}
</style>
