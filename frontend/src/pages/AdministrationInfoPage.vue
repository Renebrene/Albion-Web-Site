<template>
  <q-page class="administration-info">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Информация</h1>
        <p>Закладки страницы «Информация» (адрес /informaciya).</p>
      </div>

      <div class="header-actions">
        <q-btn
          unelevated
          color="primary"
          no-caps
          label="Сохранить"
          :loading="saving"
          @click="save"
        />
        <q-btn
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <div v-if="error" class="error-text">{{ error }}</div>
    <div v-if="saved" class="ok-text">Сохранено.</div>

    <div class="toolbar">
      <q-btn
        color="primary"
        no-caps
        icon="add"
        label="Добавить закладку"
        @click="addTab"
      />
      <span class="hint">
        Порядок закладок — сверху вниз. Закладка «Города и районы» берёт города,
        районы и описания из раздела «Главная страница».
      </span>
    </div>

    <div v-if="loading" class="loading-row">
      <q-spinner size="28px" />
    </div>

    <template v-else>
      <section v-for="(tab, index) in tabs" :key="tab._key" class="tab-card">
        <div class="tab-head">
          <span class="tab-order">#{{ index + 1 }}</span>

          <span
            class="badge"
            :class="tab.is_active ? 'badge-on' : 'badge-off'"
            >{{ tab.is_active ? 'видна' : 'скрыта' }}</span
          >

          <span class="tab-head-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveTab(index, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="index === tabs.length - 1"
              @click="moveTab(index, 1)"
            />
            <q-btn
              flat
              dense
              color="negative"
              no-caps
              label="Удалить"
              @click="removeTab(index)"
            />
          </span>
        </div>

        <div class="grid">
          <label class="field">
            <span>Название закладки</span>
            <q-input
              v-model="tab.title"
              dense
              outlined
              placeholder="НАЗВАНИЕ"
            />
          </label>

          <label class="field">
            <span>Тип содержимого</span>
            <q-select
              v-model="tab.kind"
              :options="KIND_OPTIONS"
              dense
              outlined
              emit-value
              map-options
            />
          </label>

          <label class="field field--toggle">
            <span>Показывать</span>
            <q-toggle v-model="tab.is_active" />
          </label>
        </div>

        <label v-if="tab.kind === 'text'" class="field field--full">
          <span>Текст закладки (пусто — «Раздел находится в разработке»)</span>
          <q-input
            v-model="tab.content"
            dense
            outlined
            type="textarea"
            autogrow
          />
        </label>

        <div v-else class="geo-note">
          Города, районы и описания редактируются в разделе «Главная страница» →
          «Города, районы и достопримечательности».
        </div>
      </section>

      <div v-if="!tabs.length" class="empty-text">
        Закладок нет. Добавьте первую.
      </div>
    </template>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const KIND_OPTIONS = [
  { label: 'Текст', value: 'text' },
  { label: 'Города и районы (из базы)', value: 'geo' }
]

const tabs = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

let keyCounter = 0

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: Object.assign(authHeaders(), options.headers || {})
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

function toEditorTab(tab) {
  return {
    _key: `tab-${++keyCounter}`,
    title: tab.title || '',
    kind: tab.kind || 'text',
    content: tab.content || '',
    is_active: tab.is_active !== false
  }
}

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/info/tabs')
    tabs.value = (data.tabs || []).map(toEditorTab)
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function addTab() {
  tabs.value.push({
    _key: `tab-${++keyCounter}`,
    title: 'НОВАЯ ЗАКЛАДКА',
    kind: 'text',
    content: '',
    is_active: true
  })
}

function moveTab(index, delta) {
  const target = index + delta
  if (target < 0 || target >= tabs.value.length) return

  const list = tabs.value
  const tmp = list[index]
  list[index] = list[target]
  list[target] = tmp
}

function removeTab(index) {
  tabs.value.splice(index, 1)
}

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''

  try {
    const payload = {
      tabs: tabs.value.map((tab, index) => ({
        title: tab.title,
        kind: tab.kind,
        content: tab.kind === 'geo' ? '' : tab.content,
        is_active: tab.is_active,
        sort_order: (index + 1) * 10
      }))
    }

    const data = await request('/api/admin/info/tabs', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    tabs.value = (data.tabs || []).map(toEditorTab)
    saved.value = true
    setTimeout(() => {
      saved.value = false
    }, 2500)
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.administration-info {
  max-width: 1000px;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 12px;
}

.ok-text {
  color: #2e7d32;
  background: #f1f8f1;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 12px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.hint {
  color: #8b8b8b;
  font-size: 12px;
}

.loading-row {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.tab-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 16px;
}

.tab-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.tab-order {
  color: #a2adb4;
  font-size: 12px;
  font-weight: 800;
}

.tab-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.badge-on {
  background: #e7f5ea;
  color: #2e7d32;
}

.badge-off {
  background: #f0f1f3;
  color: #8b8b8b;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1.4fr) auto;
  gap: 14px;
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > span {
  color: #6b7680;
  font-size: 12px;
  font-weight: 700;
}

.field--toggle {
  align-items: flex-start;
}

.field--full {
  margin-top: 14px;
}

.geo-note {
  margin-top: 14px;
  padding: 12px 14px;
  background: #f4f6f7;
  border-radius: 10px;
  color: #6b7680;
  font-size: 13px;
}

.empty-text {
  color: #8b8b8b;
  padding: 16px;
}

@media (max-width: 760px) {
  .administration-info {
    padding: 20px;
  }

  .page-header {
    flex-direction: column;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
