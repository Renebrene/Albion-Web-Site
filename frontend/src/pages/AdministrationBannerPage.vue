<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-banner">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>БАННЕР-ДОРОГА</h1>
        <p>
          Код поведения 3D-баннера и настройки, которые он читает из своего
          блока <code>#banner-settings</code>.
        </p>
      </div>

      <div class="header-actions">
        <q-btn
          color="primary"
          no-caps
          label="Сохранить"
          :loading="saving"
          :disable="!slide || !dirty"
          @click="save"
        />
        <q-btn
          outline
          no-caps
          label="Запустить"
          :disable="!slide || dirty"
          @click="restartPreview"
        />
        <q-btn
          flat
          no-caps
          label="PDF"
          @click="downloadPdf"
        />
        <q-btn
          flat
          no-caps
          icon="tune"
          label="Настройки"
          @click="router.push('/administration/roadrunner?tab=settings')"
        />
        <q-btn
          flat
          no-caps
          icon="movie"
          label="Генератор"
          @click="router.push('/administration/roadrunner?tab=scenarios')"
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

    <p v-if="!loading && !slide" class="empty-text">
      Слайд «Светофорные объекты» не найден. Создайте его в разделе «Главная
      страница» с типом «Светофорные объекты (код баннера)».
    </p>

    <template v-if="slide">
      <div class="toolbar">
        <label class="file-btn">
          <input
            type="file"
            accept=".html,.htm,.txt,text/html,text/plain"
            @change="onFile"
          />
          Заменить файлом
        </label>
        <q-btn
          flat
          dense
          no-caps
          label="Скачать код"
          :disable="!code"
          @click="download"
        />
        <q-btn
          flat
          dense
          no-caps
          label="Сбросить к стандартному"
          @click="resetCode"
        />
        <span class="hint"
          >{{ codeSize }} · {{ settingsStatus }}. Код сохраняется в базе
          данных.</span
        >
        <span v-if="dirty" class="dirty">есть несохранённые изменения</span>
      </div>

      <div class="banner-grid">
        <section class="panel settings-panel">
          <div class="panel-head">
            <h2>Настройки из кода</h2>
            <q-btn
              flat
              dense
              no-caps
              icon="refresh"
              label="Перечитать"
              @click="parseSettings(code)"
            />
          </div>

          <p v-if="settingsError" class="settings-error">
            {{ settingsError }}
          </p>

          <p v-else-if="!settings.length" class="hint">
            В коде нет блока настроек. Добавьте
            <code
              >&lt;script type="application/json" id="banner-settings"&gt;</code
            >
            — поля появятся здесь автоматически.
          </p>

          <div v-for="item in settings" :key="item.key" class="setting-row">
            <div class="setting-head">
              <span>
                {{ item.label }}
                <code class="setting-key">{{ item.key }}</code>
              </span>
              <b>{{ displayValue(item) }}{{ item.unit || '' }}</b>
            </div>

            <q-toggle
              v-if="item.type === 'boolean'"
              :model-value="Boolean(item.value)"
              color="primary"
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-select
              v-else-if="item.type === 'select'"
              :model-value="item.value"
              :options="item.options || []"
              emit-value
              map-options
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-slider
              v-else-if="
                item.type === 'number' &&
                item.min !== undefined &&
                item.max !== undefined
              "
              :model-value="Number(item.value)"
              :min="Number(item.min)"
              :max="Number(item.max)"
              :step="Number(item.step) || 1"
              dense
              color="primary"
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-input
              v-else-if="item.type === 'number'"
              :model-value="Number(item.value)"
              type="number"
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-input
              v-else
              :model-value="String(item.value ?? '')"
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />
          </div>
        </section>

        <section class="panel preview-panel">
          <div class="panel-head">
            <h2>Предпросмотр</h2>
            <span class="hint">изменения применяются сразу</span>
          </div>

          <iframe
            v-if="slide.has_code"
            :key="previewKey"
            :src="previewUrl"
            class="preview-frame"
            sandbox="allow-scripts"
            referrerpolicy="no-referrer"
            title="Предпросмотр баннера-дороги"
          ></iframe>
          <p v-else class="hint">Код баннера пуст.</p>
        </section>
      </div>

      <section class="panel code-panel">
        <div class="panel-head">
          <h2>HTML-код баннера</h2>
          <span class="hint">
            настройки читаются из
            <code
              >&lt;script type="application/json" id="banner-settings"&gt;</code
            >
          </span>
        </div>

        <q-input
          v-model="code"
          type="textarea"
          outlined
          class="code-area"
          :input-style="{ fontFamily: 'monospace', fontSize: '12px' }"
        />
      </section>
    </template>
  </component>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'

import { adminRequest as request } from '../services/adminApi'

defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const slide = ref(null)
const code = ref('')
const savedCode = ref('')
const settings = ref([])
const settingsError = ref('')
const previewKey = ref(0)

const SETTINGS_RE =
  /<script\b[^>]*\bid=["']banner-settings["'][^>]*>([\s\S]*?)<\/script>/i
const SETTINGS_BLOCK_RE =
  /(<script\b[^>]*\bid=["']banner-settings["'][^>]*>)([\s\S]*?)(<\/script>)/i

let syncing = false
let lastSyncedCode = ''
let parseTimer = null
let syncTimer = null

const dirty = computed(() => code.value !== savedCode.value)

const codeSize = computed(() => {
  const bytes = new TextEncoder().encode(code.value || '').length
  return `${(bytes / 1024).toFixed(1)} КБ`
})

const settingsStatus = computed(() => {
  if (settingsError.value) return 'настройки не прочитаны'
  return settings.value.length
    ? `${settings.value.length} настроек`
    : 'настроек нет'
})

const previewUrl = computed(
  () => `/api/admin/home/slides/${slide.value.id}/code?v=${previewKey.value}`
)

/* Живой предпросмотр: несохранённый код уходит на сервер с задержкой,
   iframe перезагружается и показывает именно то, что редактируется.
   В БД слайда код попадает только по «Сохранить». */
let previewTimer = null

async function pushPreview() {
  if (!slide.value) return

  try {
    await request(`/api/admin/home/slides/${slide.value.id}/preview`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.value })
    })
  } catch {
    /* редактирование не должно блокироваться ошибкой предпросмотра */
  }

  previewKey.value += 1
}

function schedulePreview() {
  if (previewTimer) window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(pushPreview, 400)
}

watch(code, schedulePreview)

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/home/slides')
    const found = (data.slides || []).find(s => s.kind === 'road-banner')

    if (!found) {
      slide.value = null
      return
    }

    slide.value = found
    code.value = found.code || ''
    savedCode.value = code.value
    parseSettings(code.value)
    schedulePreview()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function normalizeSetting(key, rawItem) {
  const descriptor =
    rawItem && typeof rawItem === 'object' && !Array.isArray(rawItem)
      ? { ...rawItem }
      : { value: rawItem }

  const value = descriptor.value
  const type =
    descriptor.type ||
    (typeof value === 'boolean'
      ? 'boolean'
      : Array.isArray(descriptor.options)
        ? 'select'
        : typeof value === 'number'
          ? 'number'
          : 'string')

  return {
    ...descriptor,
    key,
    label: descriptor.label || key,
    type,
    value
  }
}

function parseSettings(text) {
  settingsError.value = ''

  const match = String(text || '').match(SETTINGS_RE)

  if (!match) {
    settings.value = []
    settingsError.value =
      'Блок настроек не найден: нужен ' +
      '<script type="application/json" id="banner-settings">…' +
      '</' +
      'script>.'
    return
  }

  try {
    const raw = JSON.parse(match[1])
    settings.value = Object.entries(raw).map(([key, item]) =>
      normalizeSetting(key, item)
    )
  } catch (exc) {
    settings.value = []
    settingsError.value = `JSON настроек не разбирается: ${exc.message}`
  }
}

function settingsPayload() {
  const raw = {}

  settings.value.forEach(item => {
    const descriptor = { ...item }
    delete descriptor.key
    raw[item.key] = descriptor
  })

  return raw
}

function syncCodeFromSettings() {
  if (!settings.value.length) return
  if (!SETTINGS_BLOCK_RE.test(code.value)) return

  const json = JSON.stringify(settingsPayload(), null, 2)

  syncing = true

  try {
    code.value = code.value.replace(
      SETTINGS_BLOCK_RE,
      (match, open, body, close) => `${open}\n${json}\n${close}`
    )
    lastSyncedCode = code.value
  } finally {
    syncing = false
  }
}

function updateSetting(item, value) {
  if (item.type === 'number') {
    const number = Number(value)
    if (Number.isFinite(number)) value = number
  }

  item.value = value

  if (syncTimer) window.clearTimeout(syncTimer)
  syncTimer = window.setTimeout(syncCodeFromSettings, 120)
}

watch(code, value => {
  if (syncing || value === lastSyncedCode) return

  if (parseTimer) window.clearTimeout(parseTimer)
  parseTimer = window.setTimeout(() => parseSettings(value), 350)
})

function displayValue(item) {
  if (item.type === 'number') {
    const number = Number(item.value)
    return Number.isFinite(number)
      ? String(Math.round(number * 100) / 100)
      : '—'
  }

  if (item.type === 'boolean') return item.value ? 'вкл' : 'выкл'

  if (item.type === 'select') {
    const option = (item.options || []).find(candidate =>
      candidate && typeof candidate === 'object'
        ? candidate.value === item.value
        : candidate === item.value
    )

    if (option && typeof option === 'object') return option.label
  }

  return String(item.value ?? '')
}

async function downloadPdf() {
  try {
    const response = await fetch('/api/roadrunner/api-documentation.pdf')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'roadrunner-api.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (exc) {
    error.value = `Не удалось скачать PDF: ${exc}`
  }
}

async function save() {
  if (!slide.value) return

  saving.value = true
  error.value = ''

  try {
    const data = await request(`/api/admin/home/slides/${slide.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.value })
    })

    const updated = (data.slides || []).find(s => s.id === slide.value.id)

    if (updated) slide.value = updated

    savedCode.value = code.value
    previewKey.value += 1
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

function restartPreview() {
  pushPreview()
}

function onFile(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return

  if (file.size > 512 * 1024) {
    error.value = `Файл больше 512 КБ: ${file.name}`
    event.target.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    code.value = String(reader.result || '')
    lastSyncedCode = ''
    parseSettings(code.value)
    error.value = ''
  }
  reader.onerror = () => {
    error.value = `Не удалось прочитать файл: ${file.name}`
  }
  reader.readAsText(file)
  event.target.value = ''
}

function download() {
  const blob = new Blob([code.value], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'road-banner.html'
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function resetCode() {
  if (!window.confirm('Заменить текущий код стандартным баннером?')) return

  try {
    const data = await request('/api/admin/home/banner-default')
    code.value = data.code || ''
    lastSyncedCode = ''
    parseSettings(code.value)
    error.value = ''
  } catch (exc) {
    error.value = String(exc)
  }
}

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('Есть несохранённые изменения. Уйти без сохранения?')
})

onMounted(load)

onBeforeUnmount(() => {
  if (parseTimer) window.clearTimeout(parseTimer)
  if (syncTimer) window.clearTimeout(syncTimer)
  if (previewTimer) window.clearTimeout(previewTimer)
})
</script>

<style scoped>
.admin-banner {
  max-width: 1500px;
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

.empty-text {
  padding: 24px;
  color: #64748b;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.hint {
  color: #64748b;
  font-size: 13px;
}

.dirty {
  color: #b45309;
  font-size: 12px;
}

.file-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 7px 14px;
  overflow: hidden;
  border-radius: 6px;
  background: #1d4ed8;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.banner-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) 1.1fr;
  gap: 16px;
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

.settings-panel {
  max-height: 520px;
  overflow-y: auto;
}

.settings-error {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
}

.setting-row {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.setting-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
  color: #334155;
  font-size: 13px;
}

.setting-head b {
  color: #0f172a;
  white-space: nowrap;
}

.setting-key {
  display: inline-block;
  margin-left: 6px;
  color: #94a3b8;
  font-size: 11px;
}

.preview-frame {
  display: block;
  width: 100%;
  /* Та же доля экрана, что и у баннера на главной. */
  height: 50vh;
  min-height: 280px;
  border: 0;
  border-radius: 8px;
  background: #9fd4ec;
}

.code-panel {
  margin-top: 16px;
}

.code-area :deep(textarea) {
  min-height: 360px;
  max-height: 70vh;
  white-space: pre;
  overflow: auto;
}

@media (max-width: 900px) {
  .admin-banner {
    padding: 20px 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .banner-grid {
    grid-template-columns: 1fr;
  }

  .settings-panel {
    max-height: none;
  }
}
</style>
