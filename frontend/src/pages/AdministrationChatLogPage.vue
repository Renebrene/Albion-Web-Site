<template>
  <q-page class="administration-chat-log">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Журнал умного чата</h1>
        <p>Текстовые запросы и ответы пользователей с датой и временем</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="refresh"
          label="Обновить"
          :loading="loading"
          @click="reload"
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

    <section class="section-card">
      <div class="filters">
        <div class="field">
          <label>Поиск по тексту</label>
          <q-input
            v-model="search"
            outlined
            dense
            clearable
            placeholder="Слово из вопроса или ответа"
            @keyup.enter="applyFilters"
            @clear="applyFilters"
          />
        </div>

        <div class="field field-date">
          <label>С даты</label>
          <q-input v-model="dateFrom" type="date" outlined dense />
        </div>

        <div class="field field-date">
          <label>По дату</label>
          <q-input v-model="dateTo" type="date" outlined dense />
        </div>

        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Применить"
          @click="applyFilters"
        />

        <label class="only-selected">
          <input
            type="checkbox"
            :checked="selectedOnly"
            @change="toggleSelectedOnly($event.target.checked)"
          />
          Только выбранные
        </label>

        <div class="total-hint">
          Всего записей: <b>{{ total }}</b>
          <span class="dot">·</span>
          Выбрано: <b>{{ selectedTotal }}</b>
        </div>
      </div>

      <div class="export-row">
        <q-btn
          unelevated
          no-caps
          color="primary"
          icon="download"
          :label="exportLabel"
          :loading="exporting"
          :disable="!total"
          @click="exportJsonl"
        />
        <span class="export-hint">
          Формат JSONL (по строке на запись, поле <code>messages</code>) —
          удобен для анализа и дообучения нейросетей.
        </span>
      </div>

      <div v-if="error" class="error-text">{{ error }}</div>
      <div v-if="exportError" class="error-text">{{ exportError }}</div>

      <div v-if="loading" class="loading-block">
        <q-spinner size="28px" />
      </div>

      <div v-else-if="!items.length" class="empty-text">
        Записей пока нет.
      </div>

      <div v-else class="table-wrap">
        <table class="chat-table">
          <thead>
            <tr>
              <th class="col-check">
                <input
                  ref="headCheckbox"
                  type="checkbox"
                  :checked="allPageSelected"
                  @change="toggleAllPage($event.target.checked)"
                />
              </th>
              <th class="col-date">Дата и время</th>
              <th class="col-question">Вопрос</th>
              <th class="col-answer">Ответ</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in items"
              :key="item.id"
              :class="{ 'is-selected': item.selected }"
            >
              <td class="col-check">
                <input
                  type="checkbox"
                  :checked="item.selected"
                  @change="toggleItem(item, $event.target.checked)"
                />
              </td>
              <td class="col-date">{{ formatDate(item.created_at) }}</td>
              <td class="col-question">{{ item.question }}</td>
              <td class="col-answer">{{ item.answer || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="totalPages > 1" class="pagination">
        <q-btn
          flat
          dense
          no-caps
          icon="chevron_left"
          :disable="page <= 1"
          @click="goTo(page - 1)"
        />
        <span class="page-info">Стр. {{ page }} из {{ totalPages }}</span>
        <q-btn
          flat
          dense
          no-caps
          icon="chevron_right"
          :disable="page >= totalPages"
          @click="goTo(page + 1)"
        />
      </div>
    </section>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref, watchEffect } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const PAGE_SIZE = 50

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function request(path) {
  const response = await fetch(path, { headers: authHeaders() })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      /* не JSON */
    }
    throw new Error(detail)
  }

  return response.json()
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    throw new Error(`Ошибка сервера (${response.status})`)
  }

  return response.json()
}

const items = ref([])
const total = ref(0)
const selectedTotal = ref(0)
const loading = ref(true)
const error = ref('')

const page = ref(1)
const search = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const selectedOnly = ref(false)

const exporting = ref(false)
const exportError = ref('')

const headCheckbox = ref(null)

const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / PAGE_SIZE))
)

const allPageSelected = computed(
  () => items.value.length > 0 && items.value.every(item => item.selected)
)
const somePageSelected = computed(() => items.value.some(item => item.selected))

/* Заголовок кнопки экспорта: что именно уйдёт в файл. */
const exportLabel = computed(() =>
  selectedTotal.value > 0
    ? `Экспорт выбранных (${selectedTotal.value})`
    : 'Экспорт JSONL'
)

/* Тройное состояние «выбрать всё на странице». */
watchEffect(() => {
  if (headCheckbox.value) {
    headCheckbox.value.indeterminate =
      somePageSelected.value && !allPageSelected.value
  }
})

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return value

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function queryParams() {
  const params = new URLSearchParams()

  if (search.value.trim()) params.set('q', search.value.trim())

  if (dateFrom.value) params.set('date_from', `${dateFrom.value}T00:00:00`)

  if (dateTo.value) params.set('date_to', `${dateTo.value}T23:59:59`)

  return params
}

async function load() {
  loading.value = true
  error.value = ''

  const params = queryParams()
  params.set('limit', String(PAGE_SIZE))
  params.set('offset', String((page.value - 1) * PAGE_SIZE))

  if (selectedOnly.value) params.set('selected_only', '1')

  try {
    const data = await request(`/api/admin/chat-log?${params}`)
    items.value = data.items || []
    total.value = data.total || 0
    selectedTotal.value = data.selected_total || 0
  } catch (exc) {
    error.value = exc.message || 'Не удалось загрузить журнал.'
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function applyFilters() {
  page.value = 1
  load()
}

function toggleSelectedOnly(value) {
  selectedOnly.value = value
  page.value = 1
  load()
}

function goTo(value) {
  page.value = value
  load()
}

/* Отметка одной записи: сразу сохраняется на сервере. */
async function toggleItem(item, value) {
  item.selected = value

  try {
    await postJson('/api/admin/chat-log/selection', {
      ids: [item.id],
      selected: value
    })
    selectedTotal.value = Math.max(0, selectedTotal.value + (value ? 1 : -1))
  } catch (exc) {
    item.selected = !value
    error.value = exc.message || 'Не удалось сохранить отметку.'
  }
}

/* Отметка всех записей на текущей странице (тройное состояние). */
async function toggleAllPage(value) {
  const changed = items.value.filter(item => item.selected !== value)

  if (!changed.length) return

  changed.forEach(item => {
    item.selected = value
  })

  try {
    await postJson('/api/admin/chat-log/selection', {
      ids: changed.map(item => item.id),
      selected: value
    })
    selectedTotal.value = Math.max(
      0,
      selectedTotal.value + (value ? changed.length : -changed.length)
    )
  } catch (exc) {
    changed.forEach(item => {
      item.selected = !value
    })
    error.value = exc.message || 'Не удалось сохранить отметки.'
  }
}

/* Выгрузка JSONL: если есть отмеченные — только они, иначе всё по фильтру. */
async function exportJsonl() {
  exporting.value = true
  exportError.value = ''

  const params = queryParams()
  params.set('selected_only', selectedTotal.value > 0 ? '1' : '0')

  try {
    const response = await fetch(`/api/admin/chat-log/export?${params}`, {
      headers: authHeaders()
    })

    if (!response.ok) {
      throw new Error(`Не удалось выгрузить (${response.status})`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = 'chat-log.jsonl'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (exc) {
    exportError.value = exc.message || 'Не удалось выгрузить журнал.'
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.administration-chat-log {
  padding: 32px;
  background: #f3f5f6;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.eyebrow {
  color: var(--albion-accent);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 2px;
}
h1 {
  margin: 6px 0 4px;
  color: #17212b;
  font-size: 28px;
}
.page-header p {
  margin: 0;
  color: #71808c;
  font-size: 13px;
}
.header-actions {
  display: flex;
  gap: 6px;
}
.section-card {
  padding: 18px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(25, 35, 45, 0.06);
}
.filters {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 240px;
}
.field-date {
  min-width: 160px;
}
.field label {
  color: #8b98a3;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
}
.only-selected {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 8px;
  color: #52606a;
  font-size: 13px;
  cursor: pointer;
}
.only-selected input {
  cursor: pointer;
}
.total-hint {
  margin-left: auto;
  color: #71808c;
  font-size: 13px;
}
.total-hint .dot {
  margin: 0 6px;
  color: #c3cbd2;
}
.export-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.export-hint {
  color: #71808c;
  font-size: 12px;
  line-height: 1.4;
}
.export-hint code {
  padding: 1px 5px;
  border-radius: 4px;
  background: #f1f4f6;
  color: #52606a;
  font-size: 11px;
}
.error-text {
  margin-bottom: 10px;
  color: #c62828;
  font-size: 13px;
}
.loading-block {
  display: grid;
  place-items: center;
  padding: 30px 0;
}
.empty-text {
  padding: 24px 0;
  color: #71808c;
  font-size: 13px;
}
.table-wrap {
  overflow-x: auto;
}
.chat-table {
  width: 100%;
  border-collapse: collapse;
}
.chat-table th {
  padding: 8px 10px;
  border-bottom: 1px solid #eef1f3;
  color: #8b98a3;
  font-size: 10px;
  font-weight: 900;
  text-align: left;
  text-transform: uppercase;
}
.chat-table td {
  padding: 10px;
  border-bottom: 1px solid #f2f4f6;
  vertical-align: top;
  color: #17212b;
  font-size: 13px;
  line-height: 1.45;
}
.chat-table tr.is-selected td {
  background: #fdeceb;
}
.col-check {
  width: 36px;
  text-align: center;
}
.col-check input {
  cursor: pointer;
}
.col-date {
  white-space: nowrap;
  color: #71808c;
  font-size: 12px;
}
.col-question {
  width: 34%;
  font-weight: 700;
}
.col-answer {
  color: #52606a;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 14px;
}
.page-info {
  color: #71808c;
  font-size: 12px;
}
</style>
