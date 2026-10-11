<template>
  <q-page class="administration-base">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>ОБНОВЛЕНИЕ БАЗЫ</h1>
        <p>Excel → staging → медиа → превью → PostgreSQL → архив</p>
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

    <!-- ============ ЗАГРУЗКА ФАЙЛА ============ -->
    <div class="section-card">
      <div class="section-title">1. Загрузить Excel</div>
      <div class="section-hint">
        Файл может лежать где угодно — попадёт в папку
        <code>input/</code>. В ней всегда один файл: предыдущий уходит в архив
        после успешного обновления.
      </div>

      <div class="upload-row">
        <q-file
          v-model="selectedFile"
          label="Выберите файл .xlsx / .xls"
          accept=".xlsx,.xls"
          outlined
          dense
          class="upload-input"
        />

        <q-btn
          color="primary"
          no-caps
          label="Загрузить"
          :disable="!selectedFile || updateRunning"
          :loading="uploading"
          @click="uploadFile"
        />
      </div>

      <div v-if="uploadedFile" class="ok-text">
        Сохранён файл: <b>{{ uploadedFile.filename }}</b> ({{
          (uploadedFile.size / 1024).toFixed(1)
        }}
        KB)
        <span v-if="uploadedFile.moved_previous">
          · предыдущий → .previous (архивируется после обновления)
        </span>
      </div>

      <!-- Файл, ожидающий обновления в input/ (виден и после перезагрузки). -->
      <div v-if="updateState.input_pending" class="pending-file">
        <span class="pending-file-label">Файл к обновлению:</span>
        <b :class="updateState.input_pending.valid ? 'file-ok' : 'file-bad'">
          {{ updateState.input_pending.name }}
        </b>
        <span class="pending-file-meta">
          · загружен {{ formatDateTime(updateState.input_pending.mtime) }}
        </span>
        <span
          v-if="updateState.input_pending.size !== null"
          class="pending-file-meta"
        >
          · {{ (updateState.input_pending.size / 1024).toFixed(1) }} KB
        </span>
        <span
          v-if="
            !updateState.input_pending.valid &&
            updateState.input_pending.problem
          "
          class="pending-file-problem"
        >
          — {{ updateState.input_pending.problem }}
        </span>
      </div>
    </div>

    <!-- ============ ОБНОВЛЕНИЕ ============ -->
    <div class="section-card">
      <div class="section-title">2. Обновить базу</div>
      <div class="section-hint">
        Полное обновление: текстовая часть пересоздаётся целиком, медиа
        скачиваются только для изменённых ссылок, оригиналы не хранятся —
        создаются превью large/card/thumb.
      </div>

      <div class="section-hint">
        <b>Тестовый прогон (dry-run)</b> — безопасная проверка перед боевым
        обновлением. Разбирает Excel, строит staging и проверяет доступность
        ссылок на медиа <em>без скачивания</em>: видно, сколько фото придётся
        докачать и сколько ссылок недоступно. База, архивы и файлы при этом
        не меняются. Если dry-run проходит без ошибок — снимите галочку
        «Тестовый прогон» и запустите реальное обновление.
      </div>

      <div class="last-update-row">
        <span>
          Дата и время последнего обновления:
          <b>{{ formatDateTime(updateState.finished_at) }}</b>
        </span>
        <span>
          Текущий статус:
          <b>{{ statusLabel }}</b>
        </span>
      </div>

      <!-- Факт восстановления старой базы из архива. -->
      <div v-if="updateState.last_restore" class="restore-note">
        База восстановлена из архива
        <b>{{ updateState.last_restore.import_key }}</b>
        <template v-if="updateState.last_restore.base_date">
          — от
          {{
            (updateState.last_restore.base_date || '')
              .split('-')
              .reverse()
              .join('.')
          }}
        </template>
        · восстановление
        {{ formatDateTime(updateState.last_restore.restored_at) }}
      </div>

      <div class="upload-row">
        <q-checkbox
          v-model="dryRunMode"
          label="Тестовый прогон (без изменения PostgreSQL)"
          dense
          :disable="updateRunning || !inputReady || !inputValid"
        />

        <q-btn
          color="negative"
          no-caps
          label="Обновить"
          :disable="updateRunning || !inputReady || !inputValid"
          :loading="updateRunning"
          @click="startUpdate"
        />

        <q-btn
          v-if="updateRunning || stopping"
          color="warning"
          text-color="dark"
          no-caps
          icon="stop"
          label="Остановить"
          :loading="stopping"
          @click="stopUpdate"
        />
      </div>

      <div v-if="updateState.state === 'error'" class="error-text">
        Обновление завершилось с ошибкой (код
        {{ updateState.exit_code }}).
      </div>

      <div v-if="updateState.state === 'stopped'" class="stopped-text">
        Прогон остановлен пользователем.
      </div>

      <!-- индикаторы шагов -->
      <div v-if="updateState.state !== 'idle'" class="steps-row">
        <div
          v-for="step in updateState.steps"
          :key="step.num"
          class="step-chip"
          :class="'step-' + step.state"
        >
          <span class="step-num">{{ step.num }}</span>
          {{ step.name }}
        </div>
      </div>

      <!-- счётчики медиа -->
      <div
        v-if="
          updateState.state === 'running' || updateState.media.tasks !== null
        "
        class="media-row"
      >
        <span v-if="updateState.media.tasks !== null">
          Медиа задач: {{ updateState.media.tasks }}
        </span>
        <span v-if="updateState.media.download !== null">
          К скачиванию: {{ updateState.media.download }}
        </span>
        <span v-if="updateState.media.downloaded !== null">
          Скачано: {{ updateState.media.downloaded }}
          <template v-if="updateState.media.download">
            из {{ updateState.media.download }}
          </template>
        </span>
        <span v-if="updateState.media.reuse !== null">
          Пропущено (уже есть): {{ updateState.media.reuse }}
        </span>
        <span
          v-if="updateState.media.errors !== null"
          :class="{ warn: updateState.media.errors !== '0' }"
        >
          Ошибки: {{ updateState.media.errors }}
        </span>
        <span v-if="updateState.preview.ok !== null">
          Превью OK: {{ updateState.preview.ok }}
        </span>
        <span v-if="updateState.preview.errors !== null">
          Превью ERR: {{ updateState.preview.errors }}
        </span>
      </div>

      <!-- результат -->
      <div v-if="updateState.state === 'success'" class="ok-text">
        Обновление завершено.
        <template v-if="updateState.commit_key">
          Новая версия: <b>{{ updateState.commit_key }}</b
          >.
        </template>
      </div>
    </div>

    <!-- ============ ТЕКУЩИЙ ЛОГ ОБ ОШИБКАХ ============ -->
    <div class="section-card">
      <div class="section-title">3. Текущий лог об ошибках</div>

      <!-- общая информация об ошибках -->
      <div v-if="errorsText" class="errors-block">
        <div class="errors-header">
          <div class="errors-title"> Ошибки обновления </div>

          <div class="errors-actions">
            <q-btn
              flat
              dense
              no-caps
              class="action-secondary"
              label="Копировать"
              @click="copyText(errorsText)"
            />
          </div>
        </div>

        <pre class="scroll-field">{{ errorsText }}</pre>
      </div>
      <div v-else-if="updateState.state === 'error'" class="error-text">
        Прогон завершился с ошибкой — подробности в логе ниже.
      </div>
      <div v-else class="ok-text"> Ошибок не обнаружено. </div>

      <div class="log-actions-row">
        <q-btn
          flat
          no-caps
          class="action-secondary"
          label="Скачать текущий лог (.txt)"
          @click="downloadCurrentLog"
        />

        <q-btn
          flat
          no-caps
          class="action-secondary"
          label="Обновить список логов"
          :loading="logsLoading"
          @click="loadLogs"
        />
      </div>

      <div class="logs-header">Сохранённые логи</div>

      <div v-if="updateLogs.length" class="logs-scroll">
        <button
          v-for="log in updateLogs"
          :key="log.name"
          type="button"
          class="log-link"
          @click="downloadLog(log)"
        >
          <span class="log-file-icon">📄</span>
          <span class="log-link-label">{{ log.label }}</span>
          <span class="log-size">{{ (log.size / 1024).toFixed(1) }} KB</span>
        </button>
      </div>
      <div v-else class="empty-text"> Сохранённых логов пока нет. </div>
    </div>

    <!-- ============ АРХИВЫ ============ -->
    <div class="section-card">
      <div class="section-title"> 4. Архивы базы </div>

      <div class="archives-toolbar">
        <q-btn
          color="primary"
          outline
          no-caps
          icon="archive"
          label="Создать архив текущей базы"
          :loading="creating"
          :disable="creating || loading"
          @click="createArchive"
        />

        <q-btn
          color="primary"
          no-caps
          label="Обновить список архивов"
          :loading="loading"
          @click="loadArchives"
        />
      </div>

      <div v-if="notice" class="archives-notice">{{ notice }}</div>

      <div v-for="item in archives" :key="item.import_key" class="archive-card">
        <div class="archive-row">
          <div>
            <div class="archive-key">{{ item.import_key }}</div>
            <div class="archive-meta">
              {{ item.created_at }} · {{ item.size_mb }} MB
            </div>
          </div>

          <div class="archive-chips">
            <span v-if="item.source_exists" class="chip chip-green">Excel</span>
            <span v-if="item.database_exists" class="chip chip-blue">DB</span>
            <span v-if="item.media_exists" class="chip chip-orange">Media</span>
            <span v-if="!item.database_exists" class="chip chip-red"
              >без дампа</span
            >
          </div>
        </div>

        <div class="archive-actions">
          <q-btn
            flat
            dense
            no-caps
            class="action-secondary"
            label="Проверить (dry-run)"
            :disable="busyKey !== null"
            @click="dryRun(item.import_key)"
          />

          <q-btn
            color="negative"
            outline
            dense
            no-caps
            label="Восстановить"
            :disable="busyKey !== null || !item.database_exists"
            @click="askRestore(item.import_key)"
          />
        </div>
      </div>

      <div v-if="!archives.length && !loading" class="empty-text">
        Архивов пока нет.
      </div>
    </div>

    <!-- Подтверждение восстановления -->
    <q-dialog v-model="confirmOpen">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="dialog-title">Восстановить архив?</div>
          <div class="dialog-text">
            Версия <b>{{ confirmKey }}</b> заменит конструкции и их медиа
            данными из архива. Остальные разделы базы — новости, настройки,
            пользователи, контакты — не изменятся. Текущее состояние будет
            сохранено в архив <code>_safety</code> перед восстановлением.
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            color="negative"
            no-caps
            label="Восстановить"
            :loading="busyKey !== null"
            @click="restore(false)"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="busyOpen">
      <q-card class="dialog-card">
        <q-card-section>
          <div class="dialog-title">Восстановление...</div>
          <div class="dialog-text">
            Идёт восстановление версии <b>{{ busyKey }}</b
            >. Это может занять несколько минут.
          </div>
          <q-linear-progress indeterminate color="negative" class="q-mt-md" />
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Результаты (dry-run или restore) -->
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
              <span v-if="step.path" class="result-path">
                {{ step.path }}
              </span>
            </div>
          </template>

          <div v-if="result?.verify" class="result-grid">
            <div>constructions</div>
            <div>{{ result.verify.counts?.constructions }}</div>

            <div>surfaces</div>
            <div>{{ result.verify.counts?.surfaces }}</div>

            <div>construction_media</div>
            <div>{{ result.verify.counts?.construction_media }}</div>

            <div>новости (сохранено)</div>
            <div>{{ result.verify.preserved?.news }}</div>

            <div>пользователи (сохранено)</div>
            <div>{{ result.verify.preserved?.user_accounts }}</div>
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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

const archives = ref([])
const creating = ref(false)
const notice = ref('')
const loading = ref(false)
const error = ref('')

// --- загрузка файла ---
const selectedFile = ref(null)
const uploading = ref(false)
const uploadedFile = ref(null)

// --- обновление ---
const dryRunMode = ref(true)
const updateRunning = ref(false)
const stopping = ref(false)
const updateState = ref({
  state: 'idle',
  steps: [],
  media: {},
  preview: {},
  errors: []
})

const idleStatus = {
  state: 'idle',
  steps: [],
  media: {},
  preview: {},
  errors: []
}

/*
 * Готовность к обновлению базы: true, только когда в input/ есть ровно
 * один Excel (приходит из статуса). После успешного обновления файл
 * уходит в архив → до загрузки нового файла кнопка «Обновить» неактивна.
 */
const inputReady = ref(false)

/*
 * Пригодность файла в input/: false — пришла проверка «невалиден»
 * (нет листов / не распознаётся шапка). Пока файла нет — считаем true,
 * но кнопка всё равно заблокирована через inputReady.
 */
const inputValid = computed(() => {
  const pending = updateState.value.input_pending
  return !pending || pending.valid !== false
})

let pollTimer = null

const errorsText = computed(() => {
  const errors = updateState.value.errors || []

  if (!errors.length) return ''

  return errors.join('\n')
})

const statusLabel = computed(() => {
  switch (updateState.value.state) {
    case 'running':
      return 'Обновление выполняется'
    case 'success':
      return 'Завершено успешно'
    case 'error':
      return 'Ошибка'
    case 'stopped':
      return 'Остановлено'
    default:
      return 'Ожидание'
  }
})

function formatDateTime(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  const pad = n => String(n).padStart(2, '0')

  return (
    `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.` +
    `${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

// --- восстановление из архивов ---
const busyKey = ref(null)
const busyOpen = ref(false)
const confirmOpen = ref(false)
const confirmKey = ref('')
const resultOpen = ref(false)
const result = ref(null)

// --- логи обновлений ---
const updateLogs = ref([])
const logsLoading = ref(false)

/* ========================================================================
   ЗАГРУЗКА EXCEL
   ======================================================================== */

async function uploadFile() {
  const file = selectedFile.value

  if (!file) return

  uploading.value = true
  error.value = ''
  uploadedFile.value = null

  try {
    const body = new FormData()
    body.append('file', file)

    uploadedFile.value = await request('/api/admin/base/upload', {
      method: 'POST',
      body
    })

    selectedFile.value = null

    // Новый файл в input/ — обновляем статус, чтобы включить «Обновить».
    await pollStatus()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    uploading.value = false
  }
}

/* ========================================================================
   ОБНОВЛЕНИЕ БАЗЫ
   ======================================================================== */

async function startUpdate() {
  error.value = ''
  updateState.value = { ...idleStatus, state: 'running' }
  updateRunning.value = true

  try {
    const query = dryRunMode.value ? '?dry_run=true' : ''
    await request(`/api/admin/base/update${query}`, {
      method: 'POST'
    })

    pollTimer = window.setInterval(pollStatus, 2000)
    await pollStatus()
  } catch (exc) {
    error.value = String(exc)
    updateRunning.value = false
    updateState.value = { ...idleStatus }
  }
}

async function stopUpdate() {
  stopping.value = true

  try {
    await request('/api/admin/base/update/stop', { method: 'POST' })
  } catch (exc) {
    error.value = String(exc)
  } finally {
    stopping.value = false
    // Статус станет «stopped» после того, как монитор допишет его —
    // активный интервал опроса подхватит это; дополнительно опросим сейчас.
    await pollStatus()
  }
}

async function pollStatus() {
  try {
    const status = await request('/api/admin/base/update/status')

    // медиа-счётчики копируем целиком
    updateState.value = {
      ...updateState.value,
      ...status
    }

    inputReady.value = Boolean(status.input_ready)

    if (status.state === 'running') {
      return
    }

    // завершилось
    window.clearInterval(pollTimer)
    pollTimer = null
    updateRunning.value = false

    await loadArchives()
    await loadLogs()
  } catch (exc) {
    window.clearInterval(pollTimer)
    pollTimer = null
    updateRunning.value = false
    error.value = String(exc)
  }
}

/* ========================================================================
   ЛОГ / ОШИБКИ
   ======================================================================== */

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch (exc) {
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
}

function saveText(text, filename) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function loadLogs() {
  logsLoading.value = true
  try {
    const data = await request('/api/admin/base/update/logs')
    updateLogs.value = data.logs || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    logsLoading.value = false
  }
}

async function downloadCurrentLog() {
  try {
    const text = await request('/api/admin/base/update/log')
    saveText(text, 'update_log.txt')
  } catch (exc) {
    error.value = String(exc)
  }
}

async function downloadLog(log) {
  try {
    const text = await request(log.url)
    saveText(text, log.name)
  } catch (exc) {
    error.value = String(exc)
  }
}

/* ========================================================================
   АРХИВЫ / ВОССТАНОВЛЕНИЕ
   ======================================================================== */

async function loadArchives() {
  loading.value = true
  error.value = ''
  try {
    const data = await request('/api/admin/base/archives')
    archives.value = data.archives || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

/* Создать архив текущей базы (дамп + медиа с превью). */
async function createArchive() {
  creating.value = true
  error.value = ''
  notice.value = ''

  try {
    const data = await request('/api/admin/base/archives', { method: 'POST' })

    archives.value = data.archives || archives.value

    const removed = data.archive?.removed || []

    notice.value =
      `Архив создан: ${data.archive?.import_key || ''}` +
      (removed.length ? ` · удалено старых: ${removed.length}` : '')
  } catch (exc) {
    error.value = String(exc)
  } finally {
    creating.value = false
  }
}

function askRestore(importKey) {
  confirmKey.value = importKey
  confirmOpen.value = true
}

async function runRestore(importKey, dryRun) {
  busyKey.value = importKey

  if (!dryRun) {
    confirmOpen.value = false
    busyOpen.value = true
  }

  error.value = ''
  try {
    const query = dryRun ? '?dry_run=true' : ''
    const data = await request(
      `/api/admin/base/archives/${importKey}/restore${query}`,
      { method: 'POST' }
    )

    result.value = data
    resultOpen.value = true

    await loadArchives()

    if (!dryRun) {
      // После восстановления: ошибка прошлого прогона сбрасывается,
      // а «Дата и время последнего обновления» показывает дату базы.
      await pollStatus()
    }
  } catch (exc) {
    error.value = String(exc)
  } finally {
    busyKey.value = null
    busyOpen.value = false
  }
}

function dryRun(importKey) {
  runRestore(importKey, true)
}

function restore() {
  runRestore(confirmKey.value, false)
}

/* ======================================================================== */

onMounted(() => {
  loadArchives()
  loadLogs()
  pollStatus()
})

onBeforeUnmount(() => {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.administration-base {
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
  margin: 4px 0 4px;
  font-size: 30px;
  line-height: 1.1;
  font-weight: 800;
}

.page-header p {
  margin: 0;
  color: #777;
}

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
}

.ok-text {
  color: #2e7d32;
  background: #f1f8f1;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  margin-top: 10px;
}

.stopped-text {
  color: #b26a00;
  background: #fff6e5;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-top: 10px;
}

/* Файл, ожидающий обновления в input/ */
.pending-file {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #eef4fb;
  color: #1f3a5f;
  font-size: 14px;
}

.pending-file-label {
  color: #68757e;
  font-weight: 700;
}

.pending-file-meta {
  color: #52606a;
}

/* Имя файла: зелёный — пригоден, красный — без нужных данных. */
.file-ok {
  color: #2e7d32;
}

.file-bad {
  color: #c62828;
}

.pending-file-problem {
  color: #c62828;
}

/* Факт восстановления базы из архива */
.restore-note {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fff8e6;
  border: 1px solid #e6c77a;
  color: #8a5a00;
  font-size: 14px;
}

.warn {
  color: #c62828;
  font-weight: 700;
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
  margin-bottom: 6px;
}

.section-hint {
  color: #777;
  font-size: 13px;
  margin-bottom: 12px;
}

.last-update-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #546e7a;
}

.last-update-row b {
  color: #17212b;
}

.upload-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.upload-input {
  min-width: 280px;
  flex: 1;
}

/* шаги обновления */
.steps-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.step-chip {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #d9dce1;
  background: #f6f7f9;
  color: #666;
}

.step-num {
  font-weight: 800;
  margin-right: 4px;
}

.step-done {
  background: #e8f5e9;
  border-color: #a5d6a7;
  color: #2e7d32;
}

.step-current {
  background: #fff8e1;
  border-color: #ffd54f;
  color: #b26a00;
  font-weight: 700;
}

/* медиа-счётчики */
.media-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 12px;
  font-size: 13px;
  color: #444;
}

/* поле ошибок/лога */
.errors-block {
  margin-top: 14px;
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  overflow: hidden;
}

.errors-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e6ea;
}

.errors-title {
  font-weight: 800;
  font-size: 14px;
}

.errors-actions {
  display: flex;
  gap: 6px;
}

.scroll-field {
  margin: 0;
  padding: 12px 14px;
  max-height: 420px;
  overflow: auto;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  color: #333;
  background: #fff;
}

.log-open-row {
  margin-top: 10px;
}

.log-dialog {
  max-width: 900px;
  width: 90vw;
}

.archives-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.archives-notice {
  margin-bottom: 12px;
  color: #1f7a44;
  font-size: 13px;
  font-weight: 600;
}

.archive-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 14px;
}

.archive-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.archive-key {
  font-weight: 700;
  font-size: 17px;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
}

.archive-meta {
  color: #8b8b8b;
  font-size: 13px;
}

.archive-chips {
  display: flex;
  gap: 6px;
}

.chip {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 8px;
}

.chip-green {
  background: #2e7d32;
  color: #fff;
}
.chip-blue {
  background: #1565c0;
  color: #fff;
}
.chip-orange {
  background: #ef6c00;
  color: #fff;
}
.chip-red {
  background: #c62828;
  color: #fff;
}

.archive-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.action-secondary {
  color: #546e7a;
}

.empty-text {
  color: #777;
  padding: 24px;
}

/* блок «Текущий лог об ошибках» */
.log-actions-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  margin-bottom: 10px;
}

.logs-header {
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 6px;
  color: #37474f;
}

.logs-scroll {
  max-height: 260px;
  overflow-y: auto;
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  background: #fafafa;
}

.log-link {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 12px;
  border: 0;
  border-bottom: 1px solid #eceef1;
  background: transparent;
  text-align: left;
  color: #17212b;
  cursor: pointer;
}

.log-link:last-child {
  border-bottom: 0;
}

.log-link:hover {
  background: #eef2f6;
}

.log-file-icon {
  font-size: 15px;
}

.log-link-label {
  flex: 1;
  font-weight: 600;
  text-align: left;
}

.log-size {
  color: #8b8b8b;
  font-size: 12px;
}

.dialog-card {
  max-width: 560px;
}

.dialog-title {
  font-size: 18px;
  font-weight: 800;
}

.dialog-text {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.result-line {
  font-size: 13px;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
}

.result-name {
  font-weight: 700;
}

.result-path {
  color: #546e7a;
  font-size: 11px;
}

.result-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  font-size: 13px;
}
</style>
