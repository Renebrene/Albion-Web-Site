<template>
  <q-page class="administration-site">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>БЕКАП САЙТА</h1>
        <p>
          Новости, страницы, настройки, пользователи, контакты и медиа сайта —
          отдельно от конструкций. Авто-бекап раз в 7 дней, хранится до 5 штук.
        </p>
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

    <p v-if="error" class="error-text">
      {{ error }}
    </p>

    <!-- Факт последнего восстановления -->
    <div v-if="lastRestore" class="restore-note">
      <span class="restore-note-label">Последнее восстановление:</span>
      <b>{{ lastRestore.import_key }}</b>
      <span class="restore-note-time">
        · {{ formatDateTime(lastRestore.restored_at) }}
      </span>
    </div>

    <div class="section-card">
      <div class="section-title">
        Бекапы
      </div>
      <div class="section-hint">
        Перед восстановлением текущее состояние автоматически сохраняется в
        новый бекап — так всегда можно вернуться назад.
        Данные конструкций бекап не затрагивает.
      </div>

      <div class="backups-toolbar">
        <q-btn
          color="primary"
          no-caps
          icon="backup"
          label="Создать бекап сейчас"
          :loading="creating"
          @click="createBackup"
        />

        <q-btn
          flat
          no-caps
          icon="refresh"
          label="Обновить"
          :loading="loading"
          @click="loadBackups"
        />
      </div>

      <div
        v-for="item in backups"
        :key="item.name"
        class="archive-card"
      >
        <div class="archive-row">
          <div>
            <div class="archive-key">{{ item.name }}</div>
            <div class="archive-meta">
              {{ formatDateTime(item.created_at) }}
              · {{ item.size_mb }} MB
              · {{ reasonLabel(item.reason) }}
            </div>
          </div>

          <div class="archive-chips">
            <span
              v-if="item.database_exists"
              class="chip chip-blue"
            >DB</span>
            <span
              v-if="item.media_exists"
              class="chip chip-orange"
            >Media</span>
            <span
              v-if="!item.database_exists"
              class="chip chip-red"
            >без дампа</span>
          </div>
        </div>

        <div class="archive-actions">
          <q-btn
            flat
            dense
            no-caps
            class="action-secondary"
            label="Проверить (dry-run)"
            :disable="busyName !== null"
            @click="dryRun(item.name)"
          />

          <q-btn
            color="negative"
            outline
            dense
            no-caps
            label="Восстановить"
            :disable="busyName !== null || !item.database_exists"
            @click="askRestore(item.name)"
          />
        </div>
      </div>

      <div v-if="!backups.length && !loading" class="empty-text">
        Бекапов пока нет. Нажмите «Создать бекап сейчас».
      </div>
    </div>

    <!-- Подтверждение -->
    <q-dialog v-model="confirmOpen">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="dialog-title">Восстановить бекап?</div>
          <div class="dialog-text">
            Бекап <b>{{ confirmName }}</b> заменит новости, страницы, настройки,
            пользователей, контакты и медиа сайта.
            Текущее состояние будет сохранено в новый бекап автоматически.
            Конструкции и их медиа не изменяются.
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            color="negative"
            no-caps
            label="Восстановить"
            :loading="busyName !== null"
            @click="restore"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="busyOpen">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="dialog-title">Восстановление...</div>
          <div class="dialog-text">
            Восстанавливаем бекап <b>{{ busyName }}</b>.
          </div>
          <q-linear-progress
            indeterminate
            color="negative"
            class="q-mt-md"
          />
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Результат -->
    <q-dialog v-model="resultOpen">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="dialog-title">
            {{ result?.dry_run ? 'План восстановления' : 'Восстановлено' }}
          </div>

          <template v-if="result?.steps?.length">
            <div
              v-for="step in result.steps"
              :key="step.name"
              class="result-line"
            >
              <span class="result-name">{{ step.name }}</span>
              <span>· {{ step.status }}</span>
            </div>
          </template>

          <div v-if="result?.verify" class="result-grid">
            <div>новости</div>
            <div>{{ result.verify.counts?.news }}</div>

            <div>настройки</div>
            <div>{{ result.verify.counts?.site_settings }}</div>

            <div>пользователи</div>
            <div>{{ result.verify.counts?.user_accounts }}</div>

            <div>конструкции (сохранено)</div>
            <div>{{ result.verify.preserved?.constructions }}</div>
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Закрыть" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
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
      ...(options.headers || {}),
      ...authHeaders()
    }
  })

  const contentType = response.headers.get('content-type') || ''

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

  if (contentType.includes('text/plain')) {
    return response.text()
  }

  return response.json()
}

const backups = ref([])
const loading = ref(false)
const creating = ref(false)
const error = ref('')
const lastRestore = ref(null)

const busyName = ref(null)
const busyOpen = ref(false)
const confirmOpen = ref(false)
const confirmName = ref('')
const resultOpen = ref(false)
const result = ref(null)

const REASON_LABELS = {
  manual: 'вручную',
  auto: 'авто',
  'before-restore': 'перед восстановлением'
}

function reasonLabel(reason) {
  return REASON_LABELS[reason] || reason || '—'
}

function formatDateTime(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  const pad = n => String(n).padStart(2, '0')

  return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.`
    + `${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadBackups() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/base/site-backups')
    backups.value = data.backups || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

async function loadRestoreInfo() {
  try {
    const data = await request('/api/admin/base/restore-info?kind=site')
    lastRestore.value = data.last_restore || null
  } catch (exc) {
    /* не критично */
  }
}

async function createBackup() {
  creating.value = true
  error.value = ''

  try {
    await request('/api/admin/base/site-backups', { method: 'POST' })
    await loadBackups()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    creating.value = false
  }
}

function askRestore(name) {
  confirmName.value = name
  confirmOpen.value = true
}

async function runRestore(name, dryRun) {
  busyName.value = name

  if (!dryRun) {
    confirmOpen.value = false
    busyOpen.value = true
  }

  error.value = ''

  try {
    const query = dryRun ? '?dry_run=true' : ''
    const data = await request(
      `/api/admin/base/site-backups/${name}/restore${query}`,
      { method: 'POST' }
    )

    result.value = data
    resultOpen.value = true

    await loadBackups()
    await loadRestoreInfo()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    busyName.value = null
    busyOpen.value = false
  }
}

function dryRun(name) {
  runRestore(name, true)
}

function restore() {
  runRestore(confirmName.value, false)
}

onMounted(() => {
  loadBackups()
  loadRestoreInfo()
})
</script>

<style scoped>
.administration-site {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.12em;
  color: #94a3b8;
  margin-bottom: 6px;
}

h1 {
  font-size: 26px;
  margin: 0 0 6px;
}

.page-header p {
  margin: 0;
  color: #64748b;
  max-width: 640px;
}

.error-text {
  color: #b91c1c;
  background: #fee2e2;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
}

.restore-note {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 18px;
  font-size: 14px;
}

.restore-note-label {
  font-weight: 600;
  margin-right: 6px;
}

.restore-note-time {
  color: #047857;
}

.section-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.section-hint {
  color: #64748b;
  font-size: 14px;
  margin-bottom: 16px;
}

.backups-toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.archive-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
}

.archive-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.archive-key {
  font-weight: 600;
}

.archive-meta {
  color: #64748b;
  font-size: 13px;
  margin-top: 2px;
}

.archive-chips {
  display: flex;
  gap: 6px;
}

.chip {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}

.chip-blue {
  background: #dbeafe;
  color: #1e40af;
}

.chip-orange {
  background: #ffedd5;
  color: #9a3412;
}

.chip-red {
  background: #fee2e2;
  color: #b91c1c;
}

.archive-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}

.empty-text {
  color: #94a3b8;
  padding: 8px 0;
}

.dialog-card {
  min-width: 460px;
  max-width: 620px;
  padding: 8px;
}

.dialog-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
}

.dialog-text {
  color: #475569;
  line-height: 1.5;
}

.result-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  padding: 4px 0;
}

.result-name {
  font-weight: 600;
  min-width: 210px;
}

.result-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 16px;
  margin-top: 12px;
  font-size: 14px;
}

@media (max-width: 760px) {
  .administration-site {
    padding: 16px;
  }

  .dialog-card {
    min-width: 0;
    width: 100%;
  }
}
</style>
