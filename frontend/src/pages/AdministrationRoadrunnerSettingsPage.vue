<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-roadrunner-settings">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>НАСТРОЙКИ ROADRUNNER</h1>
        <p>
          Провайдеры погоды, пробок, LLM-модель и глобальные настройки
          программной дороги.
        </p>
      </div>

      <div class="header-actions">
        <q-btn
          color="primary"
          no-caps
          label="Сохранить"
          :loading="saving"
          @click="save"
        />
        <q-btn
          v-if="!embedded"
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div class="settings-grid">
      <!-- Погода -->
      <section class="panel">
        <div class="panel-head">
          <h2>🌤️ Погода</h2>
          <q-btn
            flat
            dense
            no-caps
            label="Тест"
            @click="testWeather"
          />
        </div>

        <div class="setting-item">
          <label>Провайдер</label>
          <q-select
            v-model="settings.weather_provider"
            :options="weatherProviderOptions"
            emit-value
            map-options
            dense
            outlined
          />
        </div>

        <div class="setting-item">
          <label>
            Я.Погода ключ
            <q-badge color="warning" label="опционально">
              <span class="badge-text">
                Open-Meteo работает без ключа, Яндекс — быстрее и точнее
              </span>
            </q-badge>
          </label>
          <q-input
            v-model="settings.yandex_weather_key"
            type="password"
            dense
            outlined
            placeholder="YANDEX_WEATHER_KEY"
          />
        </div>

        <div class="setting-item">
          <label>Интервал обновления (сек)</label>
          <q-input
            v-model.number="settings.weather_update_interval"
            type="number"
            dense
            outlined
          />
        </div>
      </section>

      <!-- Пробки -->
      <section class="panel">
        <div class="panel-head">
          <h2>🚗 Пробки</h2>
          <q-btn
            flat
            dense
            no-caps
            label="Тест"
            @click="testTraffic"
          />
        </div>

        <div class="setting-item">
          <label>Провайдер</label>
          <q-select
            v-model="settings.traffic_provider"
            :options="trafficProviderOptions"
            emit-value
            map-options
            dense
            outlined
          />
        </div>

        <div class="setting-item">
          <label>
            Я.Пробки URL
            <q-badge color="warning" label="опционально">
              <span class="badge-text">
                Модель по часам пик работает без ключа
              </span>
            </q-badge>
          </label>
          <q-input
            v-model="settings.yandex_traffic_url"
            dense
            outlined
            placeholder="YANDEX_TRAFFIC_URL"
          />
        </div>

        <div class="setting-item">
          <label>Интервал обновления (сек)</label>
          <q-input
            v-model.number="settings.traffic_update_interval"
            type="number"
            dense
            outlined
          />
        </div>
      </section>

      <!-- AI-агент -->
      <section class="panel">
        <div class="panel-head">
          <h2>🤖 AI-агент (генератор сценариев)</h2>
        </div>

        <div class="setting-item">
          <label>Провайдер</label>
          <q-select
            v-model="settings.llm_provider"
            :options="llmProviderOptions"
            emit-value
            map-options
            dense
            outlined
          />
        </div>

        <div class="setting-item">
          <label>Модель</label>
          <q-input
            v-model="settings.llm_model"
            dense
            outlined
            placeholder="qwen2.5:7b"
          />
        </div>

        <div class="setting-item">
          <label>URL API</label>
          <q-input
            v-model="settings.llm_url"
            dense
            outlined
            placeholder="http://localhost:11434"
          />
        </div>

        <div class="setting-item">
          <label>API Key</label>
          <q-input
            v-model="settings.llm_api_key"
            type="password"
            dense
            outlined
            placeholder="YANDEXLLM_KEY или OPENAI_API_KEY"
          />
        </div>

        <div class="setting-item">
          <label>Temperature</label>
          <q-slider
            v-model.number="settings.temperature"
            :min="0"
            :max="1"
            :step="0.05"
            dense
            color="primary"
          />
        </div>

        <div class="setting-item">
          <label>Max tokens</label>
          <q-input
            v-model.number="settings.max_tokens"
            type="number"
            dense
            outlined
          />
        </div>
      </section>

      <!-- Глобальные -->
      <section class="panel">
        <div class="panel-head">
          <h2>⚙️ Глобальные</h2>
        </div>

        <div class="setting-item">
          <label>Сценарий по умолчанию</label>
          <q-select
            v-model="settings.default_scenario"
            :options="scenarioOptions"
            emit-value
            map-options
            dense
            outlined
          />
        </div>

        <div class="setting-item">
          <label>
            Погода на баннере
            <q-toggle
              v-model="settings.weather_enabled"
              color="primary"
              size="sm"
            />
          </label>
        </div>

        <div class="setting-item">
          <label>
            Пробки на баннере
            <q-toggle
              v-model="settings.traffic_enabled"
              color="primary"
              size="sm"
            />
          </label>
        </div>
      </section>
    </div>

    <!-- Текущее состояние -->
    <section class="panel status-panel">
      <div class="panel-head">
        <h2>📊 Текущее состояние</h2>
      </div>

      <div class="status-grid">
        <div class="status-item">
          <div class="status-label">Погода</div>
          <div class="status-value" :class="weatherStatusClass">
            {{ weatherStatus }}
          </div>
        </div>

        <div class="status-item">
          <div class="status-label">Пробки</div>
          <div class="status-value" :class="trafficStatusClass">
            {{ trafficStatus }}
          </div>
        </div>

        <div class="status-item">
          <div class="status-label">LLM</div>
          <div class="status-value">
            {{ settings.llm_provider }} / {{ settings.llm_model }}
          </div>
        </div>
      </div>
    </section>
  </component>
</template>

<script setup>

defineProps({
  embedded: { type: Boolean, default: false }
})

import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { adminRequest as request } from '../services/adminApi'

const router = useRouter()

const settings = ref({
  weather_provider: 'open-meteo',
  yandex_weather_key: '',
  weather_update_interval: 600,
  traffic_provider: 'model',
  yandex_traffic_url: '',
  traffic_update_interval: 300,
  llm_provider: 'ollama',
  llm_model: 'qwen2.5:7b',
  llm_url: 'http://localhost:11434',
  llm_api_key: '',
  temperature: 0.35,
  max_tokens: 2048,
  default_scenario: 'rostov-evening-rain',
  weather_enabled: true,
  traffic_enabled: true
})

const saving = ref(false)
const error = ref('')
const weatherStatus = ref('—')
const weatherStatusClass = ref('')
const trafficStatus = ref('—')
const trafficStatusClass = ref('')

const weatherProviderOptions = [
  { label: 'Open-Meteo (без ключа)', value: 'open-meteo' },
  { label: 'Яндекс Погода', value: 'yandex' }
]

const trafficProviderOptions = [
  { label: 'Модель (по часам пик)', value: 'model' },
  { label: 'Яндекс Пробки', value: 'yandex' }
]

const llmProviderOptions = [
  { label: 'Ollama (локальная)', value: 'ollama' },
  { label: 'YandexGPT Lite 8B', value: 'yandexgpt' },
  { label: 'OpenAI совместимый', value: 'openai' }
]

const scenarioOptions = [
  { label: 'Вечерний дождь (Ростов)', value: 'rostov-evening-rain' },
  { label: 'Новый год', value: 'new-year' },
  { label: 'День Победы', value: 'victory-day' },
  { label: 'День рождения Альбион', value: 'albion-birthday' }
]

onMounted(() => {
  loadSettings()
  loadStatus()
})

async function loadSettings() {
  try {
    const data = await request('/api/roadrunner/settings')
    if (data.settings) {
      settings.value = { ...settings.value, ...data.settings }
    }
    error.value = ''
  } catch (exc) {
    error.value = `Не удалось загрузить настройки: ${exc}`
  }
}

async function loadStatus() {
  try {
    const [weatherRes, trafficRes] = await Promise.all([
      request('/api/roadrunner/weather'),
      request('/api/roadrunner/traffic')
    ])

    const weather = weatherRes.data
    const traffic = trafficRes.data

    weatherStatus.value = `${weather.condition} ${weather.temperature_c}°`
    weatherStatusClass.value = weather.source === 'open-meteo' ? 'status-ok' : 'status-model'

    trafficStatus.value = `${traffic.score} ${traffic.label}`
    trafficStatusClass.value = traffic.score <= 3 ? 'status-ok' : traffic.score <= 6 ? 'status-warning' : 'status-error'
  } catch (exc) {
    weatherStatus.value = 'ошибка'
    trafficStatus.value = 'ошибка'
  }
}

async function testWeather() {
  try {
    const data = await request('/api/roadrunner/weather')
    weatherStatus.value = `${data.data.condition} ${data.data.temperature_c}° (источник: ${data.data.source})`
    weatherStatusClass.value = 'status-ok'
    error.value = ''
  } catch (exc) {
    error.value = `Тест погоды: ${exc}`
  }
}

async function testTraffic() {
  try {
    const data = await request('/api/roadrunner/traffic')
    trafficStatus.value = `${data.data.score} ${data.data.label} (источник: ${data.data.source})`
    trafficStatusClass.value = data.data.score <= 3 ? 'status-ok' : 'status-warning'
    error.value = ''
  } catch (exc) {
    error.value = `Тест пробок: ${exc}`
  }
}

async function save() {
  saving.value = true
  error.value = ''

  try {
    await request('/api/roadrunner/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
    error.value = 'Настройки сохранены'
    await loadStatus()
  } catch (exc) {
    error.value = `Не удалось сохранить: ${exc}`
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-roadrunner-settings {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
}

.eyebrow {
  margin-bottom: 6px;
  color: #94a3b8;
  font-size: 12px;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0 0 6px;
  font-size: 26px;
}

.page-header p {
  margin: 0;
  color: #64748b;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.error-text {
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.panel {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.setting-item label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.badge-text {
  font-size: 11px;
  font-weight: 400;
  color: #92400e;
}

.status-panel {
  margin-top: 16px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.status-item {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.status-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}

.status-value {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.status-ok {
  color: #166534;
}

.status-warning {
  color: #92400e;
}

.status-error {
  color: #991b1b;
}

@media (max-width: 900px) {
  .admin-roadrunner-settings {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
