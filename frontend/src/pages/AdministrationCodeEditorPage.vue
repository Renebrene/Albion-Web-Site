<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-code-editor">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>AI-РЕДАКТОР КОДА</h1>
        <p>
          Нейросеть добавляет новые функции, элементы сцены и подписи в код
          баннера. Правки делаются на основе снимка «Дефолт» и не меняют
          текущий баннер, пока вы не нажмёте «Применить к баннеру».
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
    <p v-if="notice" class="notice-text">{{ notice }}</p>

    <div class="editor-grid">
      <section class="panel prompt-panel">
        <div class="panel-head">
          <h2>Что изменить</h2>
          <span class="hint">например: «добавь фонари на остановке»</span>
        </div>

        <q-input
          v-model="instruction"
          type="textarea"
          outlined
          class="prompt-area"
          :input-style="{ fontSize: '14px' }"
          placeholder="Опишите, какие функции или элементы добавить..."
        />

        <div class="prompt-actions">
          <q-btn
            color="primary"
            no-caps
            icon="auto_awesome"
            label="Сгенерировать"
            :loading="generating"
            :disable="!instruction.trim() || generating || !baseCode"
            @click="generate"
          />
          <q-btn
            flat
            no-caps
            label="Очистить"
            :disable="generating"
            @click="instruction = ''"
          />
        </div>

        <div class="model-line">
          <span class="model-label">Нейросеть:</span>
          <span class="model-value">{{ modelLabel }}</span>
        </div>
        <p class="field-hint">
          Выбирается на вкладке «Настройки АИ и источников».
        </p>

        <div class="default-line">
          <span class="model-label">«Дефолт»:</span>
          <span class="model-value">{{ defaultStatus }}</span>
        </div>

        <div class="default-actions">
          <q-btn
            flat
            dense
            no-caps
            icon="download"
            label="Сохранить текущий код баннера как «Дефолт»"
            :disable="loading || generating || !currentBannerCode"
            @click="snapshotBanner"
          />
          <q-btn
            flat
            dense
            no-caps
            icon="restore"
            label="Восстановить «Дефолт»"
            :loading="restoring"
            :disable="restoring || !baseCode"
            @click="restoreDefault"
          />
        </div>

        <div v-if="resultCode" class="result-actions">
          <q-btn
            color="positive"
            no-caps
            icon="check"
            label="Применить к баннеру"
            :loading="applying"
            :disable="applying || !previewCode || codeHasMarkdown"
            @click="applyToBanner"
          />
          <q-btn
            flat
            no-caps
            icon="save"
            label="Сохранить результат как «Дефолт»"
            :loading="savingDefault"
            :disable="savingDefault"
            @click="saveResultAsDefault"
          />
          <q-btn
            flat
            no-caps
            icon="undo"
            label="Вернуть «Дефолт»"
            @click="resetResult"
          />
        </div>

        <div v-if="resultCode" class="preset-save">
          <q-input
            v-model="presetName"
            dense
            outlined
            placeholder="Название новой версии"
            class="preset-name"
          />
          <q-btn
            flat
            no-caps
            icon="bookmark_add"
            label="Сохранить новую версию"
            :loading="savingPreset"
            :disable="savingPreset || !presetName.trim()"
            @click="savePreset"
          />
        </div>

        <p v-if="resultIncomplete || codeHasMarkdown" class="warning-text">
          Код содержит markdown или неполный документ. Исправьте результат
          перед применением — иначе баннер покажет резервный рисунок.
        </p>
      </section>

      <section class="panel preview-panel">
        <div class="panel-head">
          <h2>Предпросмотр</h2>
          <span class="hint">
            {{ resultCode ? 'результат ИИ' : '«Дефолт»' }}
          </span>
        </div>

        <div v-if="previewCode" class="preview-stage">
          <iframe
            :key="previewKey"
            :src="previewUrl"
            class="preview-frame"
            sandbox="allow-scripts"
            referrerpolicy="no-referrer"
            title="Предпросмотр изменённого баннера"
          ></iframe>
        </div>
        <p v-else class="hint">Код баннера пуст.</p>
      </section>
    </div>

    <div class="code-grid">
      <section class="panel code-panel">
        <div class="panel-head">
          <h2>Код-основа («Дефолт»)</h2>
          <span class="hint">на этом коде работает нейросеть</span>
        </div>

        <q-input
          v-model="baseCode"
          type="textarea"
          outlined
          class="code-area"
          :input-style="{ fontFamily: 'monospace', fontSize: '12px' }"
        />
      </section>

      <section class="panel code-panel">
        <div class="panel-head">
          <h2>Результат ИИ</h2>
          <span class="hint">можно поправить вручную перед применением</span>
        </div>

        <q-input
          v-model="resultCode"
          type="textarea"
          outlined
          class="code-area"
          :input-style="{ fontFamily: 'monospace', fontSize: '12px' }"
          placeholder="Здесь появится изменённый документ..."
        />
      </section>
    </div>

    <section class="panel presets-panel">
      <div class="panel-head">
        <h2>Сохранённые версии</h2>
        <span class="hint">новое хранится отдельно от «Дефолта» и баннера</span>
      </div>

      <p v-if="!presetNames.length" class="hint">
        Пока нет сохранённых версий. Сгенерируйте код и дайте ему название.
      </p>

      <div v-else class="preset-list">
        <div v-for="item in presetNames" :key="item" class="preset-row">
          <div class="preset-info">
            <strong>{{ item }}</strong>
            <span class="preset-date">{{ formatDate(presets[item].created_at) }}</span>
          </div>
          <div class="preset-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="play_arrow"
              label="Применить"
              :disable="restoring || applying"
              @click="applyPreset(item)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="upload"
              label="В редактор"
              @click="loadPreset(item)"
            />
            <q-btn
              flat
              dense
              no-caps
              color="negative"
              icon="delete"
              :disable="deletingPreset === item"
              @click="deletePreset(item)"
            />
          </div>
        </div>
      </div>
    </section>
  </component>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { adminRequest as request } from '../services/adminApi'

defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()

const loading = ref(true)
const generating = ref(false)
const applying = ref(false)
const restoring = ref(false)
const savingDefault = ref(false)
const savingPreset = ref(false)
const deletingPreset = ref('')

const error = ref('')
const notice = ref('')

const presets = ref({})
const presetName = ref('')

const slideId = ref(null)
const currentBannerCode = ref('')

const baseCode = ref('')
const resultCode = ref('')
const resultIncomplete = ref(false)
const instruction = ref('')

const model = ref({ provider: '', model: '' })
const defaultUpdatedAt = ref('')
const defaultSource = ref('')

const previewKey = ref(0)

const modelLabel = computed(() => {
  const provider = model.value.provider || '—'
  const name = model.value.model || '—'
  return `${provider} · ${name}`
})

const defaultStatus = computed(() => {
  if (!baseCode.value) return 'не задан'

  const source = defaultSource.value === 'banner' ? 'из кода баннера' : 'сохранён'
  const when = defaultUpdatedAt.value ? `, ${formatDate(defaultUpdatedAt.value)}` : ''

  return `${source}${when}`
})

const presetNames = computed(() => Object.keys(presets.value).sort())

const previewCode = computed(() => resultCode.value || baseCode.value)

// Markdown-обёртка в коде ломает HTML-документ баннера.
const codeHasMarkdown = computed(() => previewCode.value.includes('```'))

const previewUrl = computed(() => {
  if (!slideId.value) return ''
  return `/api/admin/home/slides/${slideId.value}/code?v=${previewKey.value}`
})

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

function clearMessages() {
  error.value = ''
  notice.value = ''
}

async function loadSlides() {
  const data = await request('/api/admin/home/slides')
  const found = (data.slides || []).find(s => s.kind === 'road-banner')

  if (found) {
    slideId.value = found.id
    currentBannerCode.value = found.code || ''
  }
}

async function loadDefault() {
  try {
    const data = await request('/api/roadrunner/code-default')
    slideId.value = data.slide_id ?? slideId.value
    baseCode.value = data.code || ''
    defaultUpdatedAt.value = data.updated_at || ''
    defaultSource.value = data.source || 'saved'
    model.value = data.model || { provider: '', model: '' }
  } catch (exc) {
    // «Дефолта» ещё нет — сохраняем текущий код баннера как основу.
    const created = await request('/api/roadrunner/code-default/from-banner', {
      method: 'POST'
    })
    slideId.value = created.slide_id ?? slideId.value
    baseCode.value = created.code || ''
    defaultUpdatedAt.value = created.updated_at || ''
    defaultSource.value = created.source || 'banner'
    model.value = await loadModelInfo()
  }
}

async function loadModelInfo() {
  try {
    const settings = await request('/api/roadrunner/settings')
    const values = settings.settings || {}
    return {
      provider: values.scene_llm_mode === 'cloud' ? 'облако' : 'локально',
      model: values.scene_llm_model || values.llm_model || ''
    }
  } catch {
    return { provider: '', model: '' }
  }
}

async function loadPresets() {
  const data = await request('/api/roadrunner/code-presets')
  presets.value = data.presets || {}
}

async function load() {
  loading.value = true
  clearMessages()

  try {
    await loadSlides()
    await loadDefault()
    await loadPresets()

    if (!model.value.model) model.value = await loadModelInfo()
    schedulePreview()
  } catch (exc) {
    error.value = `Не удалось загрузить код: ${exc}`
  } finally {
    loading.value = false
  }
}

async function generate() {
  if (!instruction.value.trim() || !baseCode.value) return

  generating.value = true
  clearMessages()

  try {
    const data = await request('/api/roadrunner/edit-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        instruction: instruction.value,
        code: baseCode.value
      })
    })

    resultCode.value = data.code || ''
    resultIncomplete.value = data.complete === false
    if (data.provider || data.model) {
      model.value = { provider: data.provider, model: data.model }
    }

    notice.value = 'Результат готов. Проверьте предпросмотр и примените к баннеру.'
    schedulePreview()
  } catch (exc) {
    error.value = `Не удалось изменить код: ${exc}`
  } finally {
    generating.value = false
  }
}

async function applyCode(code, successText) {
  if (!code || code.includes('```')) return

  applying.value = true
  clearMessages()

  try {
    const data = await request('/api/roadrunner/apply-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, slide_id: slideId.value })
    })

    currentBannerCode.value = code
    notice.value = successText || `Код применён к баннеру (слайд ${data.slide_id}).`
  } catch (exc) {
    error.value = `Не удалось применить код: ${exc}`
  } finally {
    applying.value = false
  }
}

function applyToBanner() {
  return applyCode(previewCode.value)
}

async function saveResultAsDefault() {
  if (!resultCode.value) return

  savingDefault.value = true
  clearMessages()

  try {
    const data = await request('/api/roadrunner/code-default', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: resultCode.value,
        slide_id: slideId.value
      })
    })

    baseCode.value = data.code || resultCode.value
    defaultUpdatedAt.value = data.updated_at || ''
    defaultSource.value = data.source || 'manual'
    notice.value = 'Результат сохранён как новый «Дефолт».'
  } catch (exc) {
    error.value = `Не удалось сохранить «Дефолт»: ${exc}`
  } finally {
    savingDefault.value = false
  }
}

async function snapshotBanner() {
  clearMessages()

  try {
    const data = await request('/api/roadrunner/code-default/from-banner', {
      method: 'POST'
    })

    slideId.value = data.slide_id ?? slideId.value
    baseCode.value = data.code || ''
    defaultUpdatedAt.value = data.updated_at || ''
    defaultSource.value = data.source || 'banner'
    resultCode.value = ''
    resultIncomplete.value = false
    notice.value = 'Текущий код баннера сохранён как «Дефолт».'
    schedulePreview()
  } catch (exc) {
    error.value = `Не удалось сохранить «Дефолт»: ${exc}`
  }
}

function resetResult() {
  resultCode.value = ''
  resultIncomplete.value = false
  clearMessages()
}

async function restoreDefault() {
  if (!baseCode.value || !window.confirm('Восстановить баннер из «Дефолта»? Текущий код баннера будет заменён.')) return

  restoring.value = true
  clearMessages()

  try {
    await request('/api/roadrunner/code-default/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slide_id: slideId.value })
    })

    currentBannerCode.value = baseCode.value
    resultCode.value = ''
    resultIncomplete.value = false
    notice.value = 'Баннер восстановлен из «Дефолта».'
    schedulePreview()
  } catch (exc) {
    error.value = `Не удалось восстановить «Дефолт»: ${exc}`
  } finally {
    restoring.value = false
  }
}

async function savePreset() {
  const name = presetName.value.trim()
  if (!name || codeHasMarkdown.value) return

  savingPreset.value = true
  clearMessages()

  try {
    await request('/api/roadrunner/code-presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, code: previewCode.value })
    })

    await loadPresets()
    presetName.value = ''
    notice.value = `Версия «${name}» сохранена отдельно от «Дефолта».`
  } catch (exc) {
    error.value = `Не удалось сохранить версию: ${exc}`
  } finally {
    savingPreset.value = false
  }
}

function loadPreset(name) {
  const preset = presets.value[name]
  if (!preset) return

  resultCode.value = preset.code || ''
  resultIncomplete.value = false
  notice.value = `Версия «${name}» загружена в редактор.`
  schedulePreview()
}

function applyPreset(name) {
  const preset = presets.value[name]
  if (!preset) return

  return applyCode(preset.code, `Версия «${name}» применена к баннеру.`)
}

async function deletePreset(name) {
  if (!window.confirm(`Удалить версию «${name}»?`)) return

  deletingPreset.value = name
  clearMessages()

  try {
    await request(`/api/roadrunner/code-presets/${encodeURIComponent(name)}`, {
      method: 'DELETE'
    })
    await loadPresets()
    notice.value = `Версия «${name}» удалена.`
  } catch (exc) {
    error.value = `Не удалось удалить версию: ${exc}`
  } finally {
    deletingPreset.value = ''
  }
}

/* Живой предпросмотр пишется во временную таблицу админки и не меняет
   публичный баннер — в home_slides.code код попадает только по
   «Применить к баннеру». */
let previewTimer = null

async function pushPreview() {
  if (!slideId.value || !previewCode.value) return

  try {
    await request(`/api/admin/home/slides/${slideId.value}/preview`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: previewCode.value })
    })
  } catch {
    /* предпросмотр не должен блокировать редактирование */
  }

  previewKey.value += 1
}

function schedulePreview() {
  if (previewTimer) window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(pushPreview, 350)
}

watch(previewCode, schedulePreview)

onMounted(load)

onBeforeUnmount(() => {
  if (previewTimer) window.clearTimeout(previewTimer)
})
</script>

<style scoped>
.admin-code-editor {
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
  font-weight: 700;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0 0 8px;
  font-size: clamp(24px, 3vw, 32px);
  font-weight: 900;
  letter-spacing: 0.04em;
}

.page-header p {
  max-width: 760px;
  margin: 0;
  color: #64748b;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.error-text,
.notice-text,
.warning-text {
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 8px;
  font-size: 13px;
}

.error-text {
  background: #fee2e2;
  color: #b91c1c;
}

.notice-text {
  background: #dcfce7;
  color: #166534;
}

.warning-text {
  margin: 12px 0 0;
  background: #fef3c7;
  color: #92400e;
}

.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
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
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.hint {
  color: #64748b;
  font-size: 12px;
}

.prompt-area :deep(textarea) {
  min-height: 120px;
}

.prompt-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.model-line,
.default-line {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  font-size: 13px;
}

.model-label {
  color: #64748b;
}

.model-value {
  color: #0f172a;
  font-weight: 600;
}

.field-hint {
  margin: 6px 0 0;
  color: #94a3b8;
  font-size: 12px;
}

.default-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.preview-frame {
  display: block;
  width: 100%;
  height: 50vh;
  min-height: 200px;
  border: 0;
  background: #9fd4ec;
  pointer-events: none;
}

.preview-stage {
  position: relative;
  overflow: hidden;
  border-radius: 8px;
}

.preview-stage::after {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  z-index: 1;
  height: clamp(20px, 3.5vh, 38px);
  background: linear-gradient(
    180deg,
    rgba(20, 24, 29, 0.58),
    rgba(20, 24, 29, 0)
  );
  pointer-events: none;
}

.code-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.preset-save {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.preset-name {
  flex: 1 1 220px;
  min-width: 180px;
}

.presets-panel {
  margin-top: 16px;
}

.preset-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preset-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.preset-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 14px;
}

.preset-date {
  color: #94a3b8;
  font-size: 12px;
}

.preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.code-area :deep(textarea) {
  min-height: 320px;
  max-height: 60vh;
  white-space: pre;
  overflow: auto;
}

@media (max-width: 1100px) {
  .editor-grid,
  .code-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .admin-code-editor {
    padding: 20px;
  }
}
</style>
