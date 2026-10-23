<template>
  <q-page class="administration-users">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Пользователи</h1>
        <p>Учётные записи и права доступа</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="person_add"
          color="primary"
          label="Добавить пользователя"
          @click="openCreate"
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

    <div v-if="message" class="message-text">
      {{ message }}
    </div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <section v-else class="section-card">
      <div class="section-title">
        Список пользователей
        <span class="counter">{{ users.length }}</span>
      </div>

      <div v-if="!users.length" class="empty-text">
        Пользователей пока нет.
      </div>

      <table v-else class="users-table">
        <thead>
          <tr>
            <th>Логин</th>
            <th>Имя</th>
            <th>Роль</th>
            <th>Статус</th>
            <th>Создан</th>
            <th>Вход</th>
            <th class="actions-col"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td class="login-cell">{{ user.login }}</td>
            <td>{{ user.name }}</td>
            <td>
              <span class="role-badge">{{ roleLabel(user.role) }}</span>
            </td>
            <td>
              <span
                class="status-badge"
                :class="user.is_active ? 'is-active' : 'is-inactive'"
              >
                {{ user.is_active ? 'Активен' : 'Отключён' }}
              </span>
            </td>
            <td class="date-cell">{{ formatDate(user.created_at) }}</td>
            <td class="date-cell">{{ formatDate(user.last_login_at) }}</td>
            <td class="actions-cell">
              <q-btn flat dense no-caps icon="edit" @click="openEdit(user)" />
              <q-btn
                flat
                dense
                no-caps
                icon="key"
                @click="openPassword(user)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ============ ЗАЯВКИ ============ -->
    <section class="section-card">
      <div class="section-title">
        Заявки
        <span class="counter">{{ requests.length }}</span>
        <q-btn
          flat
          dense
          no-caps
          class="action-secondary"
          label="Обновить"
          :loading="requestsLoading"
          @click="loadRequests"
        />
        <q-btn
          flat
          dense
          no-caps
          class="action-secondary"
          label="CSV"
          :disable="!requests.length"
          @click="exportRequests('csv')"
        />
        <q-btn
          flat
          dense
          no-caps
          class="action-secondary"
          label="Excel"
          :disable="!requests.length"
          @click="exportRequests('xlsx')"
        />
      </div>

      <p class="section-note">
        Заявки с сайта (без личного кабинета) и из кабинета — свежие сверху.
      </p>

      <!--
        Уведомления на почту: адрес выбирается здесь, параметры SMTP —
        в окружении (ALBION_SMTP_*), чтобы пароли не лежали в базе.
      -->
      <div class="notify-row">
        <q-toggle
          v-model="notifyForm.enabled"
          label="Уведомлять о новых заявках"
          :disable="notifySaving"
        />
        <q-input
          v-model="notifyForm.email"
          dense
          outlined
          class="notify-email"
          label="Почта для уведомлений"
          placeholder="reclama@albion.su"
        />
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Сохранить"
          :loading="notifySaving"
          @click="saveNotify"
        />
        <span v-if="!notifyForm.smtp_configured" class="notify-hint">
          Отправка заработает после настройки SMTP в окружении (ALBION_SMTP_HOST
          / USER / PASSWORD)
        </span>
      </div>

      <div v-if="requestsError" class="error-text">{{ requestsError }}</div>

      <div v-if="requestsLoading && !requests.length" class="loading-row">
        <q-spinner size="24px" />
      </div>

      <div v-else-if="!requests.length" class="empty-text">
        Заявок пока нет.
      </div>

      <table v-else class="users-table">
        <thead>
          <tr>
            <th>Дата</th>
            <th>Откуда</th>
            <th>Контакт</th>
            <th>Что</th>
            <th>Статус</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in requests" :key="row.id">
            <td class="date-cell">{{ formatDate(row.created_at) }}</td>
            <td class="date-cell">
              {{ row.account_login ? 'Кабинет: ' + row.account_login : 'Сайт' }}
            </td>
            <td class="date-cell">
              {{ row.payload.name || '—'
              }}<template v-if="row.payload.phone">
                · {{ row.payload.phone }}</template
              ><template v-else-if="row.payload.email">
                · {{ row.payload.email }}</template
              >
            </td>
            <td class="date-cell">{{ row.title }}</td>
            <td class="date-cell">
              <q-select
                :model-value="row.status"
                :options="requestStatusOptions"
                dense
                borderless
                emit-value
                map-options
                class="request-status-select"
                @update:model-value="value => setRequestStatus(row, value)"
              />
            </td>
            <td class="actions-cell">
              <q-btn
                flat
                dense
                round
                color="negative"
                icon="delete_outline"
                aria-label="Удалить заявку"
                @click="removeRequest(row)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ============ ДИАЛОГ СОЗДАНИЯ / РЕДАКТИРОВАНИЯ ============ -->
    <q-dialog v-model="editOpen" persistent>
      <q-card class="editor-dialog">
        <q-card-section>
          <div class="dialog-title">
            {{ isNew ? 'Новый пользователь' : 'Редактирование пользователя' }}
          </div>
        </q-card-section>

        <q-card-section>
          <template v-if="isNew">
            <div class="field">
              <label>Логин</label>
              <q-input v-model="form.login" outlined dense autofocus />
            </div>

            <div class="field">
              <label>Пароль</label>
              <q-input v-model="form.password" outlined dense type="password" />
            </div>
          </template>

          <div class="field">
            <label>Имя</label>
            <q-input v-model="form.name" outlined dense />
          </div>

          <div class="field">
            <label>Роль</label>
            <q-select
              v-model="form.role"
              :options="roleOptions"
              emit-value
              map-options
              outlined
              dense
            />
          </div>

          <div v-if="!isNew" class="field-row">
            <q-toggle v-model="form.is_active" label="Активен" />
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            color="primary"
            no-caps
            label="Сохранить"
            :loading="saving"
            @click="saveUser"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ============ ДИАЛОГ СМЕНЫ ПАРОЛЯ ============ -->
    <q-dialog v-model="passwordOpen" persistent>
      <q-card class="editor-dialog">
        <q-card-section>
          <div class="dialog-title">Смена пароля</div>
        </q-card-section>

        <q-card-section>
          <div class="password-user">
            Пользователь: <b>{{ passwordUser?.login }}</b>
          </div>

          <div class="field">
            <label>Новый пароль</label>
            <q-input
              v-model="passwordValue"
              outlined
              dense
              type="password"
              @keyup.enter="savePassword"
            />
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            color="primary"
            no-caps
            label="Сохранить"
            :loading="saving"
            @click="savePassword"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

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

const roleOptions = [
  { label: 'Администратор', value: 'admin' },
  { label: 'Редактор', value: 'editor' }
]

function roleLabel(role) {
  const found = roleOptions.find(o => o.value === role)
  return found ? found.label : role
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const users = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const editOpen = ref(false)
const isNew = ref(true)
const form = ref(emptyForm())

const passwordOpen = ref(false)
const passwordUser = ref(null)
const passwordValue = ref('')

function emptyForm() {
  return {
    id: null,
    login: '',
    password: '',
    name: '',
    role: 'admin',
    is_active: true
  }
}

function clearMessages() {
  error.value = ''
  message.value = ''
}

async function loadUsers() {
  loading.value = true
  clearMessages()
  try {
    const result = await request('/api/admin/users')
    users.value = result.users || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

const requests = ref([])
const requestsLoading = ref(false)
const requestsError = ref('')
const requestStatusOptions = ref([])

/* Уведомления о заявках: адрес выбирается здесь (SMTP — в окружении). */
const notifyForm = reactive({
  enabled: false,
  email: '',
  smtp_configured: false
})
const notifySaving = ref(false)

/* Заявки: и анонимные с сайта, и из личного кабинета. */
async function loadRequests() {
  requestsLoading.value = true
  requestsError.value = ''

  try {
    const result = await request('/api/admin/requests?limit=200')
    requests.value = result.requests || []
    requestStatusOptions.value = (result.statuses || []).map(item => ({
      label: item.label,
      value: item.value
    }))

    const settings = result.settings || {}
    notifyForm.enabled = Boolean(settings.enabled)
    notifyForm.email = settings.email || ''
    notifyForm.smtp_configured = Boolean(settings.smtp_configured)
  } catch (exc) {
    requests.value = []
    requestsError.value = String(exc?.message || exc)
  } finally {
    requestsLoading.value = false
  }
}

async function setRequestStatus(row, status) {
  const previous = row.status
  row.status = status

  try {
    await request(`/api/admin/requests/${row.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    })
  } catch (exc) {
    row.status = previous
    requestsError.value = String(exc?.message || exc)
  }
}

async function removeRequest(row) {
  if (!window.confirm(`Удалить заявку №${row.id}? Действие необратимо.`)) {
    return
  }

  try {
    await request(`/api/admin/requests/${row.id}`, { method: 'DELETE' })
    requests.value = requests.value.filter(item => item.id !== row.id)
  } catch (exc) {
    requestsError.value = String(exc?.message || exc)
  }
}

/* Выгрузка: файл идёт с заголовком авторизации, поэтому через blob. */
async function exportRequests(fmt) {
  requestsError.value = ''

  try {
    const response = await fetch(`/api/admin/requests/export?format=${fmt}`, {
      headers: authHeaders()
    })

    if (!response.ok) {
      throw new Error('Не удалось выгрузить заявки')
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')

    link.href = url
    link.download = fmt === 'xlsx' ? 'zayavki.xlsx' : 'zayavki.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (exc) {
    requestsError.value = String(exc?.message || exc)
  }
}

async function saveNotify() {
  notifySaving.value = true
  requestsError.value = ''

  try {
    const result = await request('/api/admin/requests/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        enabled: notifyForm.enabled,
        email: notifyForm.email
      })
    })

    notifyForm.enabled = Boolean(result.enabled)
    notifyForm.email = result.email || ''
    notifyForm.smtp_configured = Boolean(result.smtp_configured)
  } catch (exc) {
    requestsError.value = String(exc?.message || exc)
  } finally {
    notifySaving.value = false
  }
}

function openCreate() {
  clearMessages()
  isNew.value = true
  form.value = emptyForm()
  editOpen.value = true
}

function openEdit(user) {
  clearMessages()
  isNew.value = false
  form.value = {
    id: user.id,
    login: user.login,
    password: '',
    name: user.name || '',
    role: user.role || 'admin',
    is_active: !!user.is_active
  }
  editOpen.value = true
}

async function saveUser() {
  clearMessages()

  const login = (form.value.login || '').trim()
  const name = (form.value.name || '').trim()

  if (isNew.value && !login) {
    error.value = 'Укажите логин.'
    return
  }

  if (isNew.value && (form.value.password || '').length < 4) {
    error.value = 'Пароль должен содержать минимум 4 символа.'
    return
  }

  if (!name) {
    error.value = 'Укажите имя.'
    return
  }

  saving.value = true
  try {
    if (isNew.value) {
      await request('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          login,
          password: form.value.password,
          name,
          role: form.value.role
        })
      })
      message.value = `Пользователь «${login}» создан.`
    } else {
      await request(`/api/admin/users/${form.value.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          role: form.value.role,
          is_active: !!form.value.is_active
        })
      })
      message.value = `Пользователь «${form.value.login}» обновлён.`
    }
    editOpen.value = false
    await loadUsers()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

function openPassword(user) {
  clearMessages()
  passwordUser.value = user
  passwordValue.value = ''
  passwordOpen.value = true
}

async function savePassword() {
  clearMessages()

  if ((passwordValue.value || '').length < 4) {
    error.value = 'Пароль должен содержать минимум 4 символа.'
    return
  }

  saving.value = true
  try {
    await request(`/api/admin/users/${passwordUser.value.id}/password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: passwordValue.value })
    })
    message.value = `Пароль пользователя «${passwordUser.value.login}» изменён.`
    passwordOpen.value = false
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadUsers()
  loadRequests()
})
</script>

<style scoped>
.notify-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.notify-email {
  min-width: 260px;
  max-width: 320px;
}

.notify-hint {
  color: #8a8f98;
  font-size: 12px;
}

.request-status-select {
  min-width: 150px;
}

.administration-users {
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

.message-text {
  color: #1b5e20;
  background: #ecf7ee;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
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

.loading-row {
  padding: 18px;
  display: flex;
  justify-content: center;
}

/* Пояснение под заголовком раздела. */
.section-note {
  margin: -6px 0 14px;
  color: #8b8b8b;
  font-size: 13px;
}

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

.counter {
  background: #eef1f5;
  color: #546e7a;
  border-radius: 20px;
  padding: 1px 10px;
  font-size: 12px;
  font-weight: 700;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.users-table th {
  text-align: left;
  padding: 10px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #8b8b8b;
  border-bottom: 1px solid #e4e6ea;
}

.users-table td {
  padding: 12px;
  border-bottom: 1px solid #f0f1f3;
  vertical-align: middle;
}

.users-table tr:last-child td {
  border-bottom: 0;
}

.login-cell {
  font-weight: 700;
}

.date-cell {
  color: #777;
  font-size: 12px;
  white-space: nowrap;
}

.actions-col {
  width: 1%;
}

.actions-cell {
  display: flex;
  gap: 2px;
  justify-content: flex-end;
}

.role-badge {
  display: inline-block;
  background: #eef1f5;
  color: #37474f;
  border-radius: 8px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
}

.status-badge {
  display: inline-block;
  border-radius: 8px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
}

.status-badge.is-active {
  background: #ecf7ee;
  color: #1b5e20;
}

.status-badge.is-inactive {
  background: #f5eef0;
  color: #a12b3c;
}

/* формы */
.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.field-row {
  margin-top: 4px;
}

.editor-dialog {
  min-width: 460px;
  max-width: 96vw;
}

.dialog-title {
  font-size: 18px;
  font-weight: 800;
}

.password-user {
  margin-bottom: 14px;
  color: #546e7a;
  font-size: 13px;
}

@media (max-width: 700px) {
  .editor-dialog {
    min-width: 0;
    width: 96vw;
  }

  .users-table {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }
}
</style>
