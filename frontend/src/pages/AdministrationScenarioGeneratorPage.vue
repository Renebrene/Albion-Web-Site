<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-scenario-generator">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>ГЕНЕРАТОР СЦЕНАРИЕВ</h1>
        <p>
          AI-агент генерирует JSON-сценарии для 3D-баннера по описанию на
          естественном языке. Поддерживаются Ollama (локальная), YandexGPT и
          OpenAI-совместимые API.
        </p>
      </div>

      <div class="header-actions">
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

    <div class="generator-grid">
      <section class="panel prompt-panel">
        <div class="panel-head">
          <h2>Описание сценария</h2>
          <span class="hint">например: «вечерний дождь, машины едут медленно»</span>
        </div>

        <q-input
          v-model="prompt"
          type="textarea"
          outlined
          class="prompt-area"
          :input-style="{ fontSize: '14px' }"
          placeholder="Опишите сценарий на естественном языке..."
        />

        <div class="prompt-actions">
          <q-btn
            color="primary"
            no-caps
            label="Сгенерировать"
            :loading="generating"
            :disable="!prompt || generating"
            @click="generate"
          />
          <q-btn
            flat
            no-caps
            label="Очистить"
            @click="prompt = ''"
          />
        </div>

        <div class="examples">
          <div class="examples-title">Примеры запросов:</div>
          <div class="example-chip" @click="prompt = 'Вечерний дождь на большой садовой, машины едут медленно'">
            Вечерний дождь
          </div>
          <div class="example-chip" @click="prompt = 'Новый год: снег, ёлки, снеговик'">
            Новый год
          </div>
          <div class="example-chip" @click="prompt = 'День Победы: флаги, танки, салют'">
            День Победы
          </div>
          <div class="example-chip" @click="prompt = 'Санта Клаус на санях с оленями'">
            Санта Клаус
          </div>
        </div>
      </section>

      <section class="panel result-panel">
        <div class="panel-head">
          <h2>Сценарий</h2>
          <div class="panel-actions">
            <q-btn
              flat
              dense
              no-caps
              label="Сохранить"
              :disable="!generatedScenario"
              @click="saveScenario"
            />
            <q-btn
              flat
              dense
              no-caps
              label="Загрузить"
              @click="uploadScenario"
            />
            <input
              ref="fileInput"
              type="file"
              accept=".json"
              style="display: none"
              @change="onFileUpload"
            />
          </div>
        </div>

        <div v-if="!generatedScenario" class="result-empty">
          <div class="result-empty-icon">🎬</div>
          <div class="result-empty-text">
            Сценарий не сгенерирован. Введите описание и нажмите
            «Сгенерировать».
          </div>
        </div>

        <pre v-else class="result-code">{{ JSON.stringify(generatedScenario, null, 2) }}</pre>

        <div v-if="generatedError" class="result-error">
          {{ generatedError }}
        </div>
      </section>
    </div>

    <section class="panel settings-panel">
      <div class="panel-head">
        <h2>Настройки AI</h2>
        <q-btn
          flat
          dense
          no-caps
          label="Обновить"
          @click="loadSettings"
        />
      </div>

      <div class="settings-grid">
        <div class="setting-item">
          <label>Провайдер</label>
          <q-select
            v-model="settings.llm_provider"
            :options="providerOptions"
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
            dense
            outlined
            type="password"
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
      </div>

      <div class="settings-actions">
        <q-btn
          color="primary"
          no-caps
          label="Сохранить настройки"
          @click="saveSettings"
        />
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

const prompt = ref('')
const generatedScenario = ref(null)
const generatedError = ref('')
const generating = ref(false)
const error = ref('')
const fileInput = ref(null)

const settings = ref({
  llm_provider: 'ollama',
  llm_model: 'qwen2.5:7b',
  llm_url: 'http://localhost:11434',
  llm_api_key: '',
  temperature: 0.35,
  max_tokens: 2048
})

const providerOptions = [
  { label: 'Ollama (локальная)', value: 'ollama' },
  { label: 'YandexGPT Lite 8B', value: 'yandexgpt' },
  { label: 'OpenAI совместимый', value: 'openai' }
]

onMounted(() => {
  loadSettings()
})

async function loadSettings() {
  try {
    const data = await request('/api/roadrunner/settings')
    if (data.settings) {
      settings.value = { ...settings.value, ...data.settings }
    }
  } catch (exc) {
    error.value = `Не удалось загрузить настройки: ${exc}`
  }
}

async function saveSettings() {
  try {
    await request('/api/roadrunner/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
    error.value = ''
  } catch (exc) {
    error.value = `Не удалось сохранить настройки: ${exc}`
  }
}

async function generate() {
  if (!prompt.value.trim()) return

  generating.value = true
  generatedError.value = ''
  error.value = ''

  try {
    const data = await request('/api/roadrunner/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request: prompt.value })
    })

    generatedScenario.value = data.scenario
    prompt.value = ''
  } catch (exc) {
    generatedError.value = String(exc)
    generatedScenario.value = null
  } finally {
    generating.value = false
  }
}

async function saveScenario() {
  if (!generatedScenario.value) return

  try {
    await request('/api/roadrunner/scenarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(generatedScenario.value)
    })
    error.value = ''
  } catch (exc) {
    error.value = `Не удалось сохранить сценарий: ${exc}`
  }
}

function uploadScenario() {
  fileInput.value.click()
}

async function onFileUpload(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return

  try {
    const content = await file.text()
    const scenario = JSON.parse(content)

    generatedScenario.value = scenario
    prompt.value = `Загрузить сценарий: ${scenario.name || scenario.id}`

    await saveScenario()
  } catch (exc) {
    error.value = `Не удалось загрузить сценарий: ${exc}`
  }

  event.target.value = ''
}
</script>

<style scoped>
.admin-scenario-generator {
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

.generator-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
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

.panel-actions {
  display: flex;
  gap: 8px;
}

.hint {
  color: #64748b;
  font-size: 13px;
}

.prompt-area :deep(textarea) {
  min-height: 120px;
}

.prompt-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.examples {
  margin-top: 16px;
}

.examples-title {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.example-chip {
  display: inline-block;
  padding: 6px 12px;
  margin: 4px;
  border-radius: 16px;
  background: #f1f5f9;
  color: #475569;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
}

.example-chip:hover {
  background: #e2e8f0;
}

.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #94a3b8;
}

.result-empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.result-empty-text {
  font-size: 14px;
  max-width: 300px;
}

.result-code {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  overflow: auto;
  max-height: 500px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-error {
  margin-top: 12px;
  padding: 10px 14px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
  font-size: 13px;
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 12px;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-item label {
  font-size: 12px;
  color: #64748b;
  font-weight: 600;
}

.settings-actions {
  margin-top: 12px;
}

@media (max-width: 900px) {
  .admin-scenario-generator {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .generator-grid {
    grid-template-columns: 1fr;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
