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

    <div
      v-if="scenarioDisabled"
      class="scenario-mode-hint"
    >
      Сценарии доступны в режиме «Произвольный». Переключите режим в
      «Настройках АИ и источников», чтобы создавать и применять сценарии.
    </div>

    <!-- Готовые сценарии — те же, что в умном чате. -->
    <section
      class="panel ready-panel"
      :class="{ 'rr-disabled': scenarioDisabled }"
    >
      <div class="panel-head">
        <h2>Готовые сценарии</h2>
        <div class="panel-actions">
          <span v-if="appliedName" class="ready-applied">
            Применён: {{ appliedName }}
          </span>
          <q-btn
            flat
            dense
            no-caps
            icon="refresh"
            label="Обновить"
            :loading="readyLoading"
            @click="loadReadyScenarios"
          />
        </div>
      </div>

      <p class="hint ready-hint">
        Как в умном чате: нажмите «Применить» — баннер переключится сразу,
        а после окончания вернётся к настройкам из базы.
      </p>

      <p v-if="readyError" class="result-error">{{ readyError }}</p>

      <div v-if="readyLoading && !readyScenarios.length" class="ready-empty">
        Загружаем готовые сценарии…
      </div>
      <div v-else-if="!readyScenarios.length" class="ready-empty">
        Готовых сценариев пока нет.
      </div>
      <div v-else class="ready-grid">
        <article
          v-for="item in readyScenarios"
          :key="readyKey(item)"
          class="ready-card"
          :class="{ 'is-applied': appliedName === item.name }"
        >
          <div class="ready-card-head">
            <span class="ready-name">{{ item.name }}</span>
            <span class="ready-badge" :class="`ready-badge--${item.source}`">
              {{ readySourceLabel(item.source) }}
            </span>
          </div>
          <p class="ready-desc">{{ item.description || item.prompt }}</p>
          <div class="ready-meta">
            <span>{{ item.duration }} с</span>
            <span>{{ (item.events || []).length }} событий</span>
          </div>
          <div class="ready-actions">
            <q-btn
              color="primary"
              dense
              no-caps
              label="Применить"
              :loading="applyingName === item.name"
              @click="applyReady(item)"
            />
            <q-btn
              flat
              dense
              no-caps
              label="Открыть"
              @click="openReady(item)"
            />
          </div>
        </article>
      </div>
    </section>

    <div
      class="generator-grid"
      :class="{ 'rr-disabled': scenarioDisabled }"
    >
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

  </component>
</template>

<script setup>

defineProps({
  embedded: { type: Boolean, default: false }
})

import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { adminRequest as request } from '../services/adminApi'
import { roadrunnerMode } from '../composables/useRoadrunnerMode'

const scenarioDisabled = computed(() => roadrunnerMode.value !== 'custom')

const router = useRouter()

const prompt = ref('')
const generatedScenario = ref(null)
const generatedError = ref('')
const generating = ref(false)
const error = ref('')
const fileInput = ref(null)

const readyScenarios = ref([])
const readyLoading = ref(false)
const readyError = ref('')
const applyingName = ref('')
const appliedName = ref('')

const SOURCE_LABELS = {
  chat: 'Чат',
  db: 'Сохранён',
  file: 'Готовый'
}

function readySourceLabel(source) {
  return SOURCE_LABELS[source] || 'Готовый'
}

function readyKey(item) {
  return `${item.source}:${item.db_id ?? item.id ?? item.name}`
}

async function loadReadyScenarios() {
  readyLoading.value = true
  readyError.value = ''

  try {
    const data = await request('/api/roadrunner/scenarios/ready')
    readyScenarios.value = data.scenarios || []
  } catch (exc) {
    readyError.value = `Не удалось загрузить готовые сценарии: ${exc}`
  } finally {
    readyLoading.value = false
  }
}

async function applyReady(item) {
  if (scenarioDisabled.value) return

  applyingName.value = item.name
  readyError.value = ''

  try {
    await request('/api/roadrunner/scenarios/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        scenario: {
          id: item.id,
          name: item.name,
          duration: item.duration,
          events: item.events
        }
      })
    })
    appliedName.value = item.name
  } catch (exc) {
    readyError.value = `Не удалось применить «${item.name}»: ${exc}`
  } finally {
    applyingName.value = ''
  }
}

function openReady(item) {
  generatedScenario.value = {
    id: item.id,
    name: item.name,
    description: item.description,
    duration: item.duration,
    tags: item.tags || [],
    events: item.events || []
  }
  prompt.value = ''
  generatedError.value = ''
}

onMounted(loadReadyScenarios)

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
.scenario-mode-hint {
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: #fffbeb;
  color: #92400e;
  font-size: 13px;
}

.rr-disabled {
  opacity: 0.5;
  pointer-events: none;
  filter: grayscale(0.4);
}

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

.ready-panel {
  margin-bottom: 16px;
}

.ready-hint {
  margin: 0 0 12px;
}

.ready-applied {
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
}

.ready-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.ready-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.ready-card:hover {
  border-color: #bfdbfe;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
}

.ready-card.is-applied {
  border-color: #86efac;
  background: #f0fdf4;
}

.ready-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.ready-name {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.ready-badge {
  flex: 0 0 auto;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
}

.ready-badge--chat {
  background: #ede9fe;
  color: #6d28d9;
}

.ready-badge--db {
  background: #dcfce7;
  color: #15803d;
}

.ready-badge--file {
  background: #dbeafe;
  color: #1d4ed8;
}

.ready-desc {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.45;
}

.ready-meta {
  display: flex;
  gap: 12px;
  color: #94a3b8;
  font-size: 12px;
}

.ready-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 4px;
}

.ready-empty {
  padding: 20px;
  border: 1px dashed #e2e8f0;
  border-radius: 10px;
  color: #94a3b8;
  text-align: center;
  font-size: 13px;
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
