<template>
  <q-page class="administration-settings">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Настройки</h1>
        <p>Карта, внешний вид сайта (шрифты, цвета, скругления). Наборы настроек.</p>
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

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <div v-else>
      <div v-if="error" class="error-text">{{ error }}</div>

      <!--
        ============ ФОРМА НАСТРОЕК ============
        Поля рисуются по группам из схемы (field.group), чтобы «Карта»
        была отдельным видимым блоком, а не последним полем внизу.
      -->
      <section
        v-for="group in fieldGroups"
        :key="group.key"
        class="section-card"
      >
        <div class="section-title">
          <div>{{ group.title }}</div>
        </div>

        <div class="form-grid">
          <div
            v-for="field in group.fields"
            :key="field.key"
            class="field"
          >
            <label>{{ field.label }}</label>

            <!-- Текстовое поле -->
            <q-input
              v-if="field.type === 'text'"
              v-model="values[field.key]"
              outlined
              dense
            />

            <!-- Числовое поле -->
            <q-input
              v-else-if="field.type === 'number'"
              v-model="values[field.key]"
              type="number"
              outlined
              dense
            />

            <!-- Список -->
            <q-select
              v-else-if="field.type === 'select'"
              v-model="values[field.key]"
              :options="field.options || []"
              option-value="value"
              option-label="label"
              emit-value
              map-options
              outlined
              dense
              @update:model-value="value => onFieldChange(field.key, value)"
            />

            <!-- Цвет -->
            <div v-else-if="field.type === 'color'" class="color-control">
              <input
                type="color"
                class="color-swatch"
                :value="values[field.key]"
                @input="values[field.key] = $event.target.value"
              >
              <q-input
                v-model="values[field.key]"
                outlined
                dense
                class="color-hex"
              />
            </div>

            <!-- Переключатель -->
            <q-toggle
              v-else-if="field.type === 'toggle'"
              :model-value="values[field.key] === 'true'"
              @update:model-value="
                value => onFieldChange(field.key, value ? 'true' : 'false')
              "
            />
          </div>
        </div>
      </section>

      <section class="section-card">
        <div class="save-row">
          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Сохранить"
            :loading="saving"
            @click="save"
          />
        </div>
      </section>

      <!-- ============ НАБОРЫ ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Наборы настроек</div>
        </div>

        <div class="preset-create">
          <q-input
            v-model="newPresetName"
            outlined
            dense
            placeholder="Название набора"
            @keyup.enter="createPreset"
          />
          <q-btn
            outline
            no-caps
            color="primary"
            label="Создать набор"
            :loading="presetBusy"
            @click="createPreset"
          />
        </div>

        <div v-if="!presets.length" class="empty-text">
          Наборов пока нет.
        </div>

        <article
          v-for="preset in presets"
          :key="preset.id"
          class="preset-row"
        >
          <div class="preset-info">
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-date">{{ formatDate(preset.created_at) }}</div>
          </div>

          <div class="preset-actions">
            <q-btn
              flat
              dense
              no-caps
              color="primary"
              icon="play_arrow"
              label="Применить"
              :disable="presetBusy"
              @click="applyPreset(preset)"
            />
            <q-btn
              flat
              dense
              no-caps
              color="negative"
              icon="delete"
              label="Удалить"
              :disable="presetBusy"
              @click="deletePreset(preset)"
            />
          </div>
        </article>
      </section>

      <!-- ============ СБРОС ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Сброс</div>
        </div>

        <div class="reset-row">
          <div class="reset-hint">
            Вернуть все параметры к значениям по умолчанию.
          </div>
          <q-btn
            outline
            no-caps
            color="negative"
            label="Сбросить к значениям по умолчанию"
            :loading="saving"
            @click="resetToDefaults"
          />
        </div>
      </section>
    </div>

    <!-- ============ УВЕДОМЛЕНИЯ ============ -->
    <transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">
        {{ toast.text }}
      </div>
    </transition>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { applyAppearanceSettings } from '../boot/settings'
import { setAvailableMode } from '../config/availableMode'
import { setShowDynCount } from '../config/dynCount'

const router = useRouter()

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...authHeaders()
    }
  })

  if (!response.ok) {
    let detail = response.statusText

    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch (exc) {
      /* не JSON */
    }

    throw new Error(detail)
  }

  return response.json()
}

const loading = ref(true)
const saving = ref(false)
const presetBusy = ref(false)
const error = ref('')

const schema = ref([])

/*
 * Группы полей формы. Заголовки и порядок блоков; неизвестные группы
 * из схемы идут в конец, чтобы новое поле не потерялось.
 */
const GROUP_TITLES = {
  map: 'Карта',
  sides: 'Отображение сторон',
  appearance: 'Параметры внешнего вида'
}

const GROUP_ORDER = ['map', 'sides', 'appearance']

const fieldGroups = computed(() => {
  const groups = new Map()

  for (const field of schema.value) {
    const key = field.group || 'appearance'

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        title: GROUP_TITLES[key] || key,
        fields: []
      })
    }

    groups.get(key).fields.push(field)
  }

  const rank = key => {
    const index = GROUP_ORDER.indexOf(key)

    return index === -1 ? GROUP_ORDER.length : index
  }

  return [...groups.values()].sort((a, b) => rank(a.key) - rank(b.key))
})
const values = ref({})
const presets = ref([])
const newPresetName = ref('')

const toast = ref({ show: false, type: 'ok', text: '' })
let toastTimer = null

function notify(text, type = 'ok') {
  toast.value = { show: true, type, text }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value.show = false }, 3000)
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

/* Применяет ответ API к состоянию формы (без перезагрузки). */
function applyData(data) {
  schema.value = data.schema || []
  presets.value = data.presets || []

  const current = data.current || {}
  const next = {}

  for (const field of schema.value) {
    next[field.key] = String(current[field.key] ?? field.default ?? '')
  }

  values.value = next
}

async function load(showSpinner = true) {
  if (showSpinner) loading.value = true
  error.value = ''
  try {
    const data = await request('/api/admin/settings')
    applyData(data)
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = await request('/api/admin/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: values.value })
    })
    applyData(data)

    // Применяем новые значения сразу — без перезагрузки страницы
    // (в т.ч. режим доступности `available_mode` в списке/попапах/чате).
    applyAppearanceSettings(data.current)

    notify('Настройки сохранены.')
  } catch (exc) {
    error.value = String(exc)
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

/*
 * Поля, которые применяются СРАЗУ при изменении (без кнопки «Сохранить»):
 * отображение сторон и показ количества динамики. Значение тут же уходит
 * на сервер (точечно, только этот ключ), поэтому обновление видно и на
 * публичных страницах, и в других вкладках после перезагрузки.
 */
const LIVE_KEYS = new Set(['available_mode', 'show_dyn_count'])

async function onFieldChange(key, value) {
  values.value[key] = value

  if (!LIVE_KEYS.has(key)) {
    return
  }

  // Мгновенно применяем на текущей странице (список/попапы/чат реактивны).
  if (key === 'available_mode') {
    setAvailableMode(value)
  } else if (key === 'show_dyn_count') {
    setShowDynCount(value)
  }

  try {
    await request('/api/admin/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      // Точечно: сохраняем только изменённый ключ, не затирая прочие правки.
      body: JSON.stringify({ settings: { [key]: value } })
    })
    notify('Применено.')
  } catch (exc) {
    notify(String(exc), 'error')
  }
}

async function createPreset() {
  const name = newPresetName.value.trim()
  if (!name) {
    notify('Укажите название набора', 'error')
    return
  }

  presetBusy.value = true
  try {
    const data = await request('/api/admin/settings/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    applyData(data)
    newPresetName.value = ''
    notify(`Набор «${name}» создан.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function applyPreset(preset) {
  presetBusy.value = true
  try {
    const data = await request(
      `/api/admin/settings/presets/${preset.id}/apply`,
      { method: 'POST' }
    )
    applyData(data)
    notify(`Набор «${preset.name}» применён.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function deletePreset(preset) {
  if (!confirm(`Удалить набор «${preset.name}»?`)) return

  presetBusy.value = true
  try {
    const data = await request(
      `/api/admin/settings/presets/${preset.id}`,
      { method: 'DELETE' }
    )
    applyData(data)
    notify(`Набор «${preset.name}» удалён.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function resetToDefaults() {
  if (!confirm('Сбросить настройки к значениям по умолчанию?')) return

  saving.value = true
  try {
    const data = await request('/api/admin/settings/reset', { method: 'POST' })
    applyData(data)
    notify('Настройки сброшены к значениям по умолчанию.')
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.administration-settings {
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

.header-actions {
  display: flex;
  gap: 8px;
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

.loading-block {
  padding: 60px 0;
  display: flex;
  justify-content: center;
}

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
}

.empty-text {
  color: #777;
  padding: 18px;
}

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.section-title {
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px 18px;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.color-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.color-swatch {
  width: 42px;
  height: 40px;
  padding: 0;
  border: 1px solid #e4e6ea;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}

.color-hex {
  flex: 1;
}

.save-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.preset-create {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.preset-create .q-input {
  flex: 1;
}

.preset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  margin-bottom: 10px;
}

.preset-name {
  font-weight: 700;
  font-size: 15px;
}

.preset-date {
  color: #8b8b8b;
  font-size: 12px;
}

.preset-actions {
  display: flex;
  gap: 4px;
}

.reset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.reset-hint {
  color: #777;
  font-size: 14px;
}

/* всплывающее уведомление */
.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 5000;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
}

.toast.ok {
  background: #2e7d32;
  color: #fff;
}

.toast.error {
  background: #c62828;
  color: #fff;
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .preset-create {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
