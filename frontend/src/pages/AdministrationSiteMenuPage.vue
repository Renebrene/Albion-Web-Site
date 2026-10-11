<template>
  <q-page class="administration-site-menu">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Меню и подвал</h1>
        <p>Пункты верхнего меню и подвала сайта</p>
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

    <div v-if="error" class="error-text">{{ error }}</div>
    <div v-if="saved" class="ok-text">Сохранено.</div>

    <section class="section-card">
      <div class="section-head">
        <div class="section-title">Верхнее меню</div>
        <div class="inline-actions">
          <q-btn
            flat
            no-caps
            icon="add"
            label="Пункт"
            @click="addItem('main')"
          />
        </div>
      </div>

      <div class="menu-panel">
        <div
          v-for="(item, index) in mainItems"
          :key="'main' + index"
          class="menu-row"
        >
          <div class="row-handle">⠿</div>

          <q-input v-model="item.label" dense outlined label="Название" />
          <q-input
            v-model="item.url"
            dense
            outlined
            label="Адрес"
            class="url-input"
          />
          <MediaSourceButtons
            dense
            @pick="p => (item.url = p.url)"
            @notify="onMediaNotify"
          />
          <q-toggle v-model="item.is_active" label="" class="row-toggle" />

          <div class="row-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveItem(mainItems, index, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="index === mainItems.length - 1"
              @click="moveItem(mainItems, index, 1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="mainItems.splice(index, 1)"
            />
          </div>
        </div>

        <div v-if="!mainItems.length" class="empty-text"> Пунктов нет. </div>
      </div>
    </section>

    <section class="section-card">
      <div class="section-head">
        <div class="section-title">Подвал</div>
        <div class="inline-actions">
          <q-btn
            flat
            no-caps
            icon="add"
            label="Ссылка"
            @click="addItem('footer')"
          />
        </div>
      </div>

      <p class="section-hint">
        Ссылку можно выбрать из медиатеки или загрузить документ — текстовый и
        табличный: txt, md, csv, rtf, doc, docx, odt, xls, xlsx, ods, pdf.
      </p>

      <div class="menu-panel">
        <div
          v-for="(item, index) in footerItems"
          :key="'footer' + index"
          class="menu-row"
        >
          <div class="row-handle">⠿</div>

          <q-input v-model="item.label" dense outlined label="Название" />
          <q-input
            v-model="item.url"
            dense
            outlined
            label="Адрес"
            class="url-input"
          />
          <div class="media-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="photo_library"
              label="Медиатека"
              class="media-btn"
              @click="openPicker(item)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="upload_file"
              label="Загрузить"
              class="media-btn"
              :loading="item.__uploading === true"
              @click="triggerUpload(item)"
            />
          </div>
          <q-toggle v-model="item.is_active" label="" class="row-toggle" />

          <div class="row-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveItem(footerItems, index, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="index === footerItems.length - 1"
              @click="moveItem(footerItems, index, 1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="footerItems.splice(index, 1)"
            />
          </div>
        </div>

        <div v-if="!footerItems.length" class="empty-text"> Ссылок нет. </div>
      </div>
    </section>

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

    <!-- Скрытый input для загрузки документов в подвал -->
    <input
      ref="fileInput"
      type="file"
      class="hidden-file"
      :accept="DOC_ACCEPT"
      @change="onFileChange"
    />

    <MediaPicker v-model="pickerOpen" @select="onMediaPicked" />
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import MediaPicker from '../components/admin/MediaPicker.vue'
import MediaSourceButtons from '../components/admin/MediaSourceButtons.vue'

const router = useRouter()

const pickerOpen = ref(false)
const pickerTarget = ref(null)

/* Сообщения от полей выбора медиа: ошибки — в баннер, успех — тихо. */
function onMediaNotify(message, type = 'success') {
  error.value = type === 'error' ? message : ''
}

function openPicker(item) {
  pickerTarget.value = item
  pickerOpen.value = true
}

function onMediaPicked(media) {
  if (pickerTarget.value && media?.url) {
    pickerTarget.value.url = media.url
  }
  pickerOpen.value = false
}

/*
 * Загрузка документа для ссылки подвала. Файл уходит в медиатеку
 * (/api/admin/media, документы сохраняются как есть), а в ссылку
 * подставляется его адрес /storage/...
 */
const DOC_ACCEPT = '.txt,.md,.csv,.rtf,.doc,.docx,.odt,.xls,.xlsx,.ods,.pdf'
const ALLOWED_DOC_EXTENSIONS = DOC_ACCEPT.split(',')

const fileInput = ref(null)
const uploadTarget = ref(null)

/* id раздела медиатеки «Документы» — ищем по имени, а не хардкодим. */
const docCategoryId = ref(null)

async function loadDocumentCategory() {
  try {
    const data = await request('/api/admin/media/categories')
    const found = (data.categories || []).find(
      item => item.name === 'Документы'
    )
    docCategoryId.value = found ? found.id : null
  } catch {
    docCategoryId.value = null
  }
}

function triggerUpload(item) {
  uploadTarget.value = item

  if (fileInput.value) {
    // Сбрасываем значение: иначе повторный выбор того же файла не сработает.
    fileInput.value.value = ''
    fileInput.value.click()
  }
}

async function onFileChange(event) {
  const file = event.target.files && event.target.files[0]
  const item = uploadTarget.value
  uploadTarget.value = null

  if (!file || !item) return

  const extension = `.${(file.name.split('.').pop() || '').toLowerCase()}`

  if (!ALLOWED_DOC_EXTENSIONS.includes(extension)) {
    error.value = `Формат «${extension}» не поддерживается. Разрешены: ${DOC_ACCEPT}`
    return
  }

  item.__uploading = true
  error.value = ''
  saved.value = false

  try {
    const form = new FormData()
    form.append('file', file)
    form.append('original_name', file.name)

    // Документы из подвала складываем в раздел медиатеки «Документы».
    if (docCategoryId.value) {
      form.append('category_id', String(docCategoryId.value))
    }

    const response = await fetch('/api/admin/media', {
      method: 'POST',
      headers: authHeaders(),
      body: form
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error((data && data.detail) || 'Не удалось загрузить документ')
    }

    const media = data && data.media

    if (!media || !media.storage_path) {
      throw new Error('Сервер не вернул файл')
    }

    item.url = `/storage/${media.storage_path}`

    if (!item.label) {
      item.label = file.name.replace(/\.[^.]+$/, '')
    }
  } catch (exc) {
    error.value = String(exc.message || exc)
  } finally {
    item.__uploading = false
  }
}

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

  return response.json()
}

const mainItems = ref([])
const footerItems = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await request('/api/admin/site/menu')
    mainItems.value = (data.main || []).map(item => ({
      key: item.key,
      label: item.label,
      url: item.url,
      sort_order: item.sort_order,
      is_active: item.is_active
    }))
    footerItems.value = (data.footer || []).map(item => ({
      key: item.key,
      label: item.label,
      url: item.url,
      sort_order: item.sort_order,
      is_active: item.is_active
    }))
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function addItem(section) {
  const list = section === 'main' ? mainItems.value : footerItems.value
  list.push({ key: null, label: '', url: '#', sort_order: 0, is_active: true })
}

function moveItem(list, index, delta) {
  const target = index + delta
  if (target < 0 || target >= list.length) return
  const tmp = list[index]
  list[index] = list[target]
  list[target] = tmp
}

function toPayload(items) {
  return items.map((item, index) => ({
    key: item.key || undefined,
    label: item.label,
    url: item.url,
    is_active: item.is_active,
    sort_order: (index + 1) * 10
  }))
}

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    await request('/api/admin/site/menu', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        main: toPayload(mainItems.value),
        footer: toPayload(footerItems.value)
      })
    })
    saved.value = true
    setTimeout(() => {
      saved.value = false
    }, 2500)
    await load()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadDocumentCategory()
})
</script>

<style scoped>
.administration-site-menu {
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

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-title {
  font-size: 17px;
  font-weight: 800;
}

.menu-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.menu-row {
  display: grid;
  grid-template-columns:
    20px minmax(160px, 1fr) minmax(150px, 1fr)
    auto 40px auto;
  align-items: center;
  gap: 10px;
}

.media-btn {
  font-size: 12px;
}

.media-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.hidden-file {
  display: none;
}

.section-hint {
  margin: 0 0 14px;
  color: #777;
  font-size: 13px;
}

.row-handle {
  color: #c0c6cb;
  text-align: center;
  cursor: grab;
}

.row-actions {
  display: flex;
  gap: 2px;
}

.url-input {
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 12px;
}

.empty-text {
  color: #8b8b8b;
  padding: 16px;
}

.save-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 6px;
}

@media (max-width: 760px) {
  .menu-row {
    grid-template-columns: 20px minmax(0, 1fr) auto auto;
  }

  .row-handle {
    grid-row: 1 / span 3;
  }

  .row-toggle {
    grid-column: 3;
    grid-row: 1;
  }

  .row-actions {
    grid-column: 4;
    grid-row: 1;
  }

  .url-input {
    grid-column: 2 / -1;
    grid-row: 2;
  }

  .media-actions {
    grid-column: 2 / -1;
    grid-row: 3;
    justify-self: start;
  }
}
</style>
