<template>
  <q-page class="administration-audit">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Журнал действий</h1>
        <p>История изменений и входов в административной панели</p>
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
        <div class="field filter-action">
          <label>Действие</label>
          <q-select
            v-model="actionFilter"
            :options="actionOptions"
            option-value="value"
            option-label="label"
            emit-value
            map-options
            outlined
            dense
            @update:model-value="onFilterChange"
          />
        </div>

        <div class="total-hint">
          Всего записей: <b>{{ total }}</b>
        </div>
      </div>

      <div v-if="error" class="error-text">{{ error }}</div>

      <div v-if="loading" class="loading-block">
        <q-spinner size="28px" />
      </div>

      <div v-else-if="!items.length" class="empty-text">
        Записей пока нет.
      </div>

      <div v-else class="table-wrap">
        <table class="audit-table">
          <thead>
            <tr>
              <th class="col-date">Дата</th>
              <th class="col-user">Пользователь</th>
              <th class="col-action">Действие</th>
              <th class="col-entity">Объект</th>
              <th class="col-ip">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td class="col-date">{{ formatDate(item.created_at) }}</td>
              <td class="col-user">
                <div class="user-cell">
                  <span class="user-name">{{
                    item.login || item.user_name || '—'
                  }}</span>
                  <span v-if="item.user_id" class="user-id"
                    >#{{ item.user_id }}</span
                  >
                </div>
              </td>
              <td class="col-action">
                <span class="action-badge" :class="actionClass(item.action)">
                  {{ actionLabel(item.action) }}
                </span>
              </td>
              <td class="col-entity">
                <template v-if="item.entity_type">
                  {{ entityLabel(item.entity_type) }}
                  <span v-if="item.entity_id" class="entity-id"
                    >#{{ item.entity_id }}</span
                  >
                </template>
                <span v-else class="muted">—</span>
              </td>
              <td class="col-ip">{{ item.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="totalPages > 1" class="pagination-row">
        <q-pagination
          v-model="page"
          :max="totalPages"
          :max-pages="7"
          boundary-numbers
          direction-links
          @update:model-value="loadPage"
        />
      </div>
    </section>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const PAGE_SIZE = 50

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...options.headers,
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

const items = ref([])
const total = ref(0)
const loading = ref(true)
const error = ref('')

const page = ref(1)
const pageSize = PAGE_SIZE
const actionFilter = ref('')

const actionOptions = [
  { value: '', label: 'Все действия' },
  { value: 'login', label: 'Вход' },
  { value: 'create', label: 'Создание' },
  { value: 'update', label: 'Изменение' },
  { value: 'delete', label: 'Удаление' }
]

const ACTION_LABELS = {
  login: 'Вход',
  logout: 'Выход',
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление'
}

const ENTITY_LABELS = {
  admin_user: 'Пользователь',
  contact_office: 'Офис',
  contact_department: 'Раздел контактов',
  contact_employee: 'Сотрудник',
  news: 'Новость',
  media: 'Медиа',
  page: 'Страница',
  settings: 'Настройки',
  site_menu: 'Меню сайта'
}

const totalPages = computed(() =>
  Math.max(1, Math.ceil(total.value / pageSize))
)

function actionLabel(action) {
  return ACTION_LABELS[action] || action || '—'
}

function actionClass(action) {
  if (action === 'delete') return 'action-delete'
  if (action === 'create') return 'action-create'
  if (action === 'login' || action === 'logout') return 'action-login'
  return 'action-update'
}

function entityLabel(entityType) {
  return ENTITY_LABELS[entityType] || entityType
}

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

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    params.set('limit', String(pageSize))
    params.set('offset', String((page.value - 1) * pageSize))
    if (actionFilter.value) {
      params.set('action', actionFilter.value)
    }

    const result = await request(`/api/admin/audit?${params.toString()}`)
    items.value = result.items || []
    total.value = result.total || 0
  } catch (exc) {
    error.value = String(exc)
    items.value = []
  } finally {
    loading.value = false
  }
}

function loadPage() {
  loadData()
}

function onFilterChange() {
  page.value = 1
  loadData()
}

function reload() {
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.administration-audit {
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

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.filters {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.filter-action {
  min-width: 220px;
  margin-bottom: 0;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.total-hint {
  color: #66727c;
  font-size: 13px;
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

.table-wrap {
  max-height: 560px;
  overflow: auto;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.audit-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f6f7f9;
  text-align: left;
  font-weight: 700;
  color: #546e7a;
  padding: 10px 14px;
  border-bottom: 1px solid #e4e6ea;
  white-space: nowrap;
}

.audit-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #eef1f5;
  vertical-align: top;
}

.audit-table tbody tr:hover {
  background: #fafbfc;
}

.col-date {
  white-space: nowrap;
  color: #546e7a;
}

.col-ip {
  white-space: nowrap;
  font-family: monospace;
  color: #66727c;
}

.user-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-weight: 700;
}

.user-id {
  color: #8b8b8b;
  font-size: 11px;
}

.entity-id {
  color: #8b8b8b;
  font-size: 12px;
}

.muted {
  color: #b0b0b0;
}

.action-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.action-login {
  background: #e8f0fe;
  color: #1a56b0;
}

.action-create {
  background: #e6f4ea;
  color: #1e7d3c;
}

.action-update {
  background: #fff4e5;
  color: #a8661b;
}

.action-delete {
  background: #fdeaea;
  color: #b3261e;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

@media (max-width: 700px) {
  .administration-audit {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }
}
</style>
