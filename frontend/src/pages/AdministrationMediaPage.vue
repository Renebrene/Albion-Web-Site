<template>
  <q-page class="media-page">
    <div class="media-container">
      <header class="media-header">
        <div>
          <div class="media-brand">ALBION</div>
          <h1>Медиа</h1>
          <p>Загрузка и управление изображениями сайта</p>
        </div>

        <q-btn
          flat
          no-caps
          label="← Администрирование"
          @click="router.push('/administration/dashboard')"
        />
      </header>

      <q-card flat bordered class="media-card">
        <q-card-section>
          <div class="section-title">Загрузка изображения</div>
          <div class="section-description">
            После загрузки система автоматически создаст необходимые варианты
            изображения.
          </div>
        </q-card-section>

        <q-card-section class="form-section">
          <q-file
            v-model="file"
            outlined
            clearable
            accept=".jpg,.jpeg,.jfif,.jpe,.png,.webp,.heic,.heif,.tif,.tiff,.bmp,.psd,.gif,image/*"
            label="Файл изображения"
            hint="JPEG, JFIF, JPE, PNG, WEBP, HEIC, TIFF, BMP, PSD или GIF"
            :disable="uploading"
          />

          <div class="metadata-grid">
            <q-input
              v-model="alt"
              outlined
              label="Alt"
              placeholder="Описание изображения"
              :disable="uploading"
            />

            <q-input
              v-model="title"
              outlined
              label="Title"
              placeholder="Заголовок изображения"
              :disable="uploading"
            />


            <div class="category-select-wrap">
              <q-select
                v-model="uploadCategoryId"
                outlined
                emit-value
                map-options
                label="Раздел хранения"
                :options="mediaCategories.map((category) => ({ label: category.name, value: category.id }))"
                :disable="uploading"
              />

              <q-btn
                outline
                square
                icon="add"
                aria-label="Добавить раздел"
                @click="newCategoryName = ''; categoryDialog = true"
                title="Добавить раздел"
                :disable="uploading"
              />
            </div>

          </div>

          <div v-if="previewUrl" class="preview-wrap">
            <div class="preview-label">Предпросмотр</div>
            <img
              :src="previewUrl"
              alt="Предпросмотр"
              class="preview-image"
            />
          </div>

          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Загрузить"
            :loading="uploading"
            :disable="!file"
            class="upload-button"
            @click="uploadMedia"
          />
        </q-card-section>
      </q-card>

      <q-dialog v-model="categoryDialog">
        <q-card style="min-width: 360px; max-width: 90vw;">
          <q-card-section>
            <div class="section-title">Новая категория</div>
          </q-card-section>

          <q-card-section>
            <q-input
              v-model="newCategoryName"
              outlined
              autofocus
              label="Название категории"
              :disable="creatingCategory"
              @keyup.enter="createCategory"
            />
          </q-card-section>

          <q-card-actions align="right">
            <q-btn
              flat
              no-caps
              label="Отмена"
              :disable="creatingCategory"
              @click="categoryDialog = false"
            />

            <q-btn
              unelevated
              color="primary"
              no-caps
              label="Создать"
              :loading="creatingCategory"
              :disable="!newCategoryName.trim()"
              @click="createCategory"
            />
          </q-card-actions>
        </q-card>
      </q-dialog>

      <q-dialog v-model="editDialog">
        <q-card style="min-width: 420px; max-width: 90vw;">
          <q-card-section>
            <div class="section-title">Редактирование изображения</div>
          </q-card-section>

          <q-card-section class="q-gutter-md">
            <q-input
              v-model="editOriginalName"
              outlined
              label="Название файла"
              :disable="savingMedia"
              @keyup.enter="saveMediaEdit"
            />

            <q-select
              v-model="editCategoryId"
              outlined
              emit-value
              map-options
              label="Категория"
              :options="mediaCategories.map((category) => ({
                label: category.name,
                value: category.id
              }))"
              :loading="loadingCategories"
              :disable="savingMedia"
            />
          </q-card-section>

          <q-card-actions align="right">
            <q-btn
              flat
              no-caps
              label="Отмена"
              :disable="savingMedia"
              @click="editDialog = false"
            />

            <q-btn
              unelevated
              color="primary"
              no-caps
              label="Сохранить"
              :loading="savingMedia"
              :disable="!editOriginalName.trim() || editCategoryId === null"
              @click="saveMediaEdit"
            />
          </q-card-actions>
        </q-card>
      </q-dialog>

      <q-card v-if="error" flat bordered class="result-card result-error">
        <q-card-section>
          <div class="result-title">Ошибка</div>
          <div>{{ error }}</div>
        </q-card-section>
      </q-card>

      <q-card v-if="result" flat bordered class="result-card">
        <q-card-section>
          <div class="result-title">Изображение загружено</div>

          <div class="result-grid">
            <div>
              <span class="result-label">ID</span>
              <strong>{{ result.id }}</strong>
            </div>

            <div>
              <span class="result-label">Файл</span>
              <strong>{{ result.original_name }}</strong>
            </div>

            <div>
              <span class="result-label">Размер</span>
              <strong>{{ result.width }} × {{ result.height }}</strong>
            </div>

            <div>
              <span class="result-label">Тип</span>
              <strong>{{ result.mime_type }}</strong>
            </div>
          </div>

          <div v-if="result.storage_path" class="result-path">
            {{ result.storage_path }}
          </div>

          <div v-if="result.variants?.length" class="variants-section">
            <div class="variants-title">Варианты</div>

            <div
              v-for="variant in result.variants"
              :key="variant.id"
              class="variant-row"
            >
              <div>
                <strong>{{ variant.variant }}</strong>
                <span>
                  {{ variant.width }} × {{ variant.height }}
                </span>
              </div>

              <a
                :href="storageUrl(variant.storage_path)"
                target="_blank"
                rel="noopener noreferrer"
              >
                Открыть
              </a>
            </div>
          </div>

          <div v-if="result.storage_path" class="main-file-link">
            <a
              :href="storageUrl(result.storage_path)"
              target="_blank"
              rel="noopener noreferrer"
            >
              Открыть основное изображение
            </a>
          </div>
        </q-card-section>
      </q-card>

      <section class="catalog-section">
        <div class="catalog-header">
          <div>
            <div class="section-title">Каталог изображений</div>
            <div class="section-description">
              Все загруженные изображения и созданные для них варианты.
            </div>
          </div>

          <q-btn
            outline
            no-caps
            label="Обновить"
            :loading="loadingMedia"
            @click="loadMedia"
          />
        </div>

        <q-card flat bordered class="catalog-filters">
          <q-card-section>
            <div class="filters-grid">
              <q-input
                v-model="searchQuery"
                outlined
                dense
                clearable
                label="Поиск"
                placeholder="Имя файла, Alt или Title"
              />

              <q-select
                v-model="filterCategoryId"
                outlined
                dense
                clearable
                emit-value
                map-options
                label="Раздел хранения"
                :options="mediaCategories.map((category) => ({ label: category.name, value: category.id }))"
                :loading="loadingCategories"
              />

              <q-input
                v-model="dateFrom"
                outlined
                dense
                clearable
                type="date"
                label="Дата от"
              />

              <q-input
                v-model="dateTo"
                outlined
                dense
                clearable
                type="date"
                label="Дата до"
              />
            </div>

            <div class="catalog-toolbar">
              <div class="catalog-count">
                Найдено файлов: <strong>{{ filteredMediaItems.length }}</strong>
                <span v-if="filteredMediaItems.length !== mediaItems.length">
                  из {{ mediaItems.length }}
                </span>
              </div>

              <div class="catalog-toolbar-actions">
                <q-btn
                  flat
                  no-caps
                  label="Сбросить фильтры"
                  :disable="!hasActiveFilters"
                  @click="resetFilters"
                />

                <q-btn-toggle
                  v-model="viewMode"
                  unelevated
                  toggle-color="primary"
                  no-caps
                  :options="viewModeOptions"
                />
                <q-select
                  v-if="viewMode === 'small'"
                  v-model="smallColumns"
                  :options="smallColumnsOptions"
                  dense
                  outlined
                  emit-value
                  map-options
                  style="width: 90px"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>

        <q-card
          v-if="catalogError"
          flat
          class="result-card result-error"
        >
          <q-card-section>
            <div class="result-title">Ошибка</div>
            <div>{{ catalogError }}</div>
          </q-card-section>
        </q-card>

        <q-card
          v-else-if="!loadingMedia && mediaItems.length === 0"
          flat
          bordered
          class="empty-card"
        >
          <q-card-section>
            Пока нет загруженных изображений.
          </q-card-section>
        </q-card>

        <q-card
          v-else-if="!loadingMedia && filteredMediaItems.length === 0"
          flat
          bordered
          class="empty-card"
        >
          <q-card-section>
            По заданным фильтрам изображения не найдены.
          </q-card-section>
        </q-card>

        <div
          v-else
          :class="['media-grid', `media-grid--${viewMode}`]"
          :style="viewMode === 'small' ? { '--media-small-columns': smallColumns } : undefined"
        >
          <q-card
            v-for="item in filteredMediaItems"
            :key="item.id"
            flat
            bordered
            class="media-item"
          >
            <div class="media-thumbnail-wrap">
              <img
                v-if="thumbnailUrl(item)"
                :src="thumbnailUrl(item)"
                :alt="item.alt || item.original_name"
                class="media-thumbnail"
                loading="lazy"
              />

              <div v-else class="media-thumbnail-empty">
                Нет превью
              </div>
            </div>

            <q-card-section class="media-item-content">
              <div class="media-item-path">
                {{ (item.category_name || 'Разное').toUpperCase() }}
              </div>

              <div class="media-item-name" :title="item.original_name">
                {{ item.original_name }}
              </div>

              <div v-if="item.alt || item.title" class="media-item-description">
                <span v-if="item.alt">{{ item.alt }}</span>
                <span v-if="item.alt && item.title"> · </span>
                <span v-if="item.title">{{ item.title }}</span>
              </div>

              <div class="media-item-date">
                {{ formatDate(item.created_at) }}
              </div>

              <div class="media-item-meta">
                <span>{{ item.width }} × {{ item.height }} px</span>
                <span>{{ formatFileSize(item.file_size) }}</span>
                <span>ID {{ item.id }}</span>
              </div>

              <div class="usage-row">
                <q-chip
                  v-if="item.used_in_news"
                  dense
                  size="sm"
                  color="blue-grey-1"
                  text-color="blue-grey-9"
                >
                  Используется в новостях
                </q-chip>

                <q-chip
                  v-if="item.used_in_pages"
                  dense
                  size="sm"
                  color="blue-grey-1"
                  text-color="blue-grey-9"
                >
                  Используется на страницах
                </q-chip>

                <q-chip
                  v-if="!item.used_in_news && !item.used_in_pages"
                  dense
                  size="sm"
                  color="grey-2"
                  text-color="grey-8"
                >
                  Не используется
                </q-chip>
              </div>
            </q-card-section>

            <div class="media-item-actions">
              <q-btn
                flat
                round
                dense
                icon="open_in_new"
                aria-label="Открыть"
                title="Открыть"
                :href="storageUrl(item.storage_path)"
                target="_blank"
                rel="noopener noreferrer"
              />

              <q-btn
                flat
                round
                dense
                icon="edit"
                aria-label="Редактировать"
                title="Редактировать"
                @click="openEditMedia(item)"
              />

              <q-btn
                flat
                round
                dense
                icon="delete"
                color="negative"
                aria-label="Удалить"
                title="Удалить"
                :disable="item.used_in_news || item.used_in_pages"
                :loading="deletingId === item.id"
                @click="deleteMedia(item)"
              />
            </div>
          </q-card>
        </div>
      </section>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const file = ref(null)
const alt = ref('')
const title = ref('')
const uploading = ref(false)
const error = ref('')
const result = ref(null)
const previewUrl = ref('')
let previewObjectUrl = ''

const mediaItems = ref([])
const loadingMedia = ref(false)
const catalogError = ref('')
const deletingId = ref(null)

const mediaCategories = ref([])
const loadingCategories = ref(false)
const uploadCategoryId = ref(1)
const filterCategoryId = ref(null)

const categoryDialog = ref(false)
const newCategoryName = ref('')
const creatingCategory = ref(false)
const editDialog = ref(false)
const editingMedia = ref(null)
const editOriginalName = ref('' )
const editCategoryId = ref(null)
const savingMedia = ref(false)

const searchQuery = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const viewMode = ref('medium')
const smallColumns = ref(6)

const smallColumnsOptions = [
  { label: '4', value: 4 },
  { label: '5', value: 5 },
  { label: '6', value: 6 },
  { label: '7', value: 7 },
  { label: '8', value: 8 },
]


const viewModeOptions = [
  { label: 'Таблица', value: 'table' },
  { label: 'Мелкие', value: 'small' },
  { label: 'Средние', value: 'medium' },
]


watch(file, (newFile) => {
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl)
    previewObjectUrl = ''
  }

  previewUrl.value = ''

  const selectedFile = Array.isArray(newFile)
    ? newFile[0]
    : newFile

  if (selectedFile instanceof File) {
    previewObjectUrl = URL.createObjectURL(selectedFile)
    previewUrl.value = previewObjectUrl
  }
})


function storageUrl(path) {
  return `/storage/${path}`
}

function thumbnailUrl(item) {
  const thumb = item.variants?.find(
    (variant) => variant.variant === 'thumb'
  )

  return storageUrl(thumb?.storage_path || item.storage_path)
}



function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—'
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function formatDate(value) {
  if (!value) {
    return 'Дата неизвестна'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const filteredMediaItems = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()

  return mediaItems.value.filter((item) => {
    if (query) {
      const haystack = [
        item.original_name,
        item.alt,
        item.title
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      if (!haystack.includes(query)) {
        return false
      }
    }

    if (filterCategoryId.value !== null && item.category_id !== filterCategoryId.value) {
      return false
    }

    if (dateFrom.value || dateTo.value) {
      const timestamp = new Date(item.created_at).getTime()

      if (Number.isNaN(timestamp)) {
        return false
      }

      if (dateFrom.value) {
        const from = new Date(`${dateFrom.value}T00:00:00`).getTime()

        if (timestamp < from) {
          return false
        }
      }

      if (dateTo.value) {
        const to = new Date(`${dateTo.value}T23:59:59.999`).getTime()

        if (timestamp > to) {
          return false
        }
      }
    }

    return true
  })
})

const hasActiveFilters = computed(() => {
  return Boolean(
    searchQuery.value ||
    filterCategoryId.value !== null ||
    dateFrom.value ||
    dateTo.value
  )
})

function resetFilters() {
  searchQuery.value = ''
  filterCategoryId.value = null
  dateFrom.value = ''
  dateTo.value = ''
}

async function getAdminToken() {
  const token = sessionStorage.getItem('albion_admin_token')

  if (!token) {
    await router.replace('/administration')
    return null
  }

  return token
}

async function createCategory() {
  const name = newCategoryName.value.trim()

  if (!name) {
    return
  }

  const token = await getAdminToken()

  if (!token) {
    return
  }

  creatingCategory.value = true
  catalogError.value = ''

  const formData = new FormData()
  formData.append('name', name)

  try {
    const response = await fetch('/api/admin/media/categories', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: formData
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось создать категорию'
      return
    }

    const category = data?.category

    if (category) {
      mediaCategories.value = [...mediaCategories.value, category].sort((a, b) => a.sort_order !== b.sort_order ? a.sort_order - b.sort_order : a.name.localeCompare(b.name, "ru"))
      uploadCategoryId.value = category.id
    }

    newCategoryName.value = ""
    categoryDialog.value = false
  } catch {
    catalogError.value = "Не удалось выполнить запрос к серверу"
  } finally {
    creatingCategory.value = false
  }
}

function openEditMedia(item) {
  editingMedia.value = item
  editOriginalName.value = item.original_name || ''
  editCategoryId.value = item.category_id ?? uploadCategoryId.value ?? mediaCategories.value[0]?.id ?? null
  catalogError.value = ''
  editDialog.value = true
}

async function saveMediaEdit() {
  if (!editingMedia.value) {
    return
  }

  const name = editOriginalName.value.trim()

  if (!name) {
    catalogError.value = 'Название файла не может быть пустым'
    return
  }

  if (editCategoryId.value === null || editCategoryId.value === undefined) {
    catalogError.value = 'Выберите категорию'
    return
  }

  const token = await getAdminToken()

  if (!token) {
    return
  }

  savingMedia.value = true
  catalogError.value = ''

  const formData = new FormData()
  formData.append('original_name', name)
  formData.append('category_id', String(editCategoryId.value))

  try {
    const response = await fetch(`/api/admin/media/${editingMedia.value.id}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: formData
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось сохранить изменения'
      return
    }

    editDialog.value = false
    editingMedia.value = null
    await loadMedia()
  } catch {
    catalogError.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    savingMedia.value = false
  }
}

async function loadMediaCategories() {
  const token = await getAdminToken()

  if (!token) {
    return
  }

  loadingCategories.value = true

  try {
    const response = await fetch('/api/admin/media/categories', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось загрузить категории'
      return
    }

    mediaCategories.value = data?.categories || []

    if (
      mediaCategories.value.length &&
      !mediaCategories.value.some(
        (category) => category.id === uploadCategoryId.value
      )
    ) {
      uploadCategoryId.value = mediaCategories.value[0].id
    }
  } catch {
    catalogError.value = 'Не удалось загрузить категории'
  } finally {
    loadingCategories.value = false
  }
}

async function loadMedia() {
  const token = await getAdminToken()

  if (!token) {
    return
  }

  loadingMedia.value = true
  catalogError.value = ''

  try {
    const response = await fetch('/api/admin/media', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось загрузить каталог медиа'
      return
    }

    mediaItems.value = data?.media || []
  } catch {
    catalogError.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    loadingMedia.value = false
  }
}

async function uploadMedia() {
  if (!file.value) {
    return
  }

  const token = await getAdminToken()

  if (!token) {
    return
  }

  uploading.value = true
  error.value = ''
  result.value = null

  const formData = new FormData()
  formData.append('file', file.value)
  formData.append('category_id', String(uploadCategoryId.value))

  if (alt.value.trim()) {
    formData.append('alt', alt.value.trim())
  }

  if (title.value.trim()) {
    formData.append('title', title.value.trim())
  }

  try {
    const response = await fetch('/api/admin/media', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: formData
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      error.value = data?.detail || 'Не удалось загрузить изображение'
      return
    }

    result.value = data.media

    file.value = null
    alt.value = ''
    title.value = ''

    await loadMedia()
  } catch {
    error.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    uploading.value = false
  }
}

async function deleteMedia(item) {
  if (item.used_in_news || item.used_in_pages) {
    return
  }

  const confirmed = window.confirm(
    `Удалить изображение «${item.original_name}»?\n\nБудут удалены оригинал и созданные варианты.`
  )

  if (!confirmed) {
    return
  }

  const token = await getAdminToken()

  if (!token) {
    return
  }

  deletingId.value = item.id
  catalogError.value = ''

  try {
    const response = await fetch(`/api/admin/media/${item.id}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось удалить изображение'
      return
    }

    mediaItems.value = mediaItems.value.filter(
      (media) => media.id !== item.id
    )

    if (result.value?.id === item.id) {
      result.value = null
    }
  } catch {
    catalogError.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  loadMediaCategories()
  loadMedia()
})

onBeforeUnmount(() => {
  if (previewObjectUrl) {
    URL.revokeObjectURL(previewObjectUrl)
  }
})
</script>

<style scoped>
.media-page {
  min-height: 100vh;
  padding: 32px 24px;
}

.media-container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.media-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
}

.media-brand {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}

.media-header h1 {
  margin: 0;
  font-size: 32px;
  line-height: 1.15;
}

.media-header p {
  margin: 8px 0 0;
  color: #6b7280;
}

.media-card,
.result-card,
.empty-card,
.media-item {
  border-radius: 16px;
  background: #fff;
}

.media-item-content {
  display: grid;
  gap: 7px;
  flex: 1;
  padding: 14px 16px 10px;
}

.media-item-path {
  color: #6b7280;
  font-size: 12px;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.media-item-name {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.media-item-description {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
  line-height: 1.4;
}

.media-item-date {
  color: #6b7280;
  font-size: 13px;
}

.media-item-meta {
  display: grid;
  gap: 3px;
  color: #4b5563;
  font-size: 13px;
}

.media-item-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 4px;
  padding: 6px 10px 10px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
}

.section-description {
  margin-top: 6px;
  color: #6b7280;
  line-height: 1.5;
}

.form-section {
  display: grid;
  gap: 12px;
}

.metadata-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 0.9fr;
  gap: 12px;
}

.preview-wrap {
  padding-top: 0;
}

.preview-label,
.variants-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 700;
}

.preview-image {
  display: block;
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  border-radius: 12px;
  background: #f3f5f6;
}

.upload-button {
  min-height: 42px;
}

.result-card {
  margin-top: 20px;
}

.result-error {
  color: #c62828;
}

.result-title {
  margin-bottom: 16px;
  font-size: 18px;
  font-weight: 700;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.result-grid > div {
  display: grid;
  gap: 4px;
}

.result-label {
  color: #6b7280;
  font-size: 13px;
}

.result-path {
  margin-top: 18px;
  padding: 12px;
  overflow-wrap: anywhere;
  font-family: monospace;
  font-size: 13px;
  background: #f3f5f6;
  border-radius: 8px;
}

.variants-section {
  margin-top: 22px;
}

.variant-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-top: 1px solid #e5e7eb;
}

.variant-row div {
  display: flex;
  gap: 12px;
  align-items: baseline;
}

.variant-row span {
  color: #6b7280;
  font-size: 13px;
}

.variant-row a,
.main-file-link a {
  color: inherit;
  font-weight: 600;
}

.main-file-link {
  margin-top: 18px;
}

.catalog-section {
  margin-top: 40px;
}

.catalog-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
}

.catalog-filters {
  margin-bottom: 18px;
  border-radius: 16px;
}

.filters-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  gap: 12px;
}

.catalog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
}

.catalog-count {
  color: #6b7280;
  font-size: 14px;
}

.catalog-count strong {
  color: #111827;
}

.catalog-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.media-grid {
  display: grid;
  gap: 18px;
}

.media-grid--small {
  grid-template-columns: repeat(var(--media-small-columns, 6), minmax(0, 1fr));

}

.media-grid--small .media-item {
  overflow: hidden;
}

.media-grid--small .media-thumbnail-wrap {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  background: #f3f5f6;
}

.media-grid--small .media-thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.media-grid--small .media-item-content {
  display: block;
  padding: 8px 10px 10px;
}

.media-grid--small .media-item-path,
.media-grid--small .media-item-description,
.media-grid--small .media-item-meta,
.media-grid--small .usage-row,
.media-grid--small .media-item-actions {
  display: none;
}

.media-grid--small .media-item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
}

.media-grid--small .media-item-date {
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  line-height: 1.25;
}
.media-grid--medium {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}


.media-grid--table {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
}

.media-grid--table .media-item {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  align-items: center;
  min-height: 62px;
  overflow: hidden;
}

.media-grid--table .media-thumbnail-wrap {
  width: 50px;
  height: 38px;
  aspect-ratio: auto;
  overflow: hidden;
  background: #f3f5f6;
}

.media-grid--table .media-thumbnail {
  width: 50px;
  height: 38px;
  object-fit: contain;
}

.media-grid--table .media-item-content {
  min-width: 0;
  padding: 5px 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  align-content: center;
  gap: 3px 10px;
  line-height: 1.25;
}

.media-grid--table .media-item-name {
  flex: 0 1 auto;
  min-width: 120px;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

.media-grid--table .media-item-meta {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
  font-size: 11px;
  line-height: 1.25;
  white-space: nowrap;
}

.media-grid--table .media-item-path {
  flex: 0 0 auto;
  padding: 1px 5px;
  font-size: 11px;
  white-space: nowrap;
}

.media-grid--table .media-item-field {
  flex: 0 1 180px;
  min-width: 0;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.media-grid--table .media-item-date {
  flex: 0 0 auto;
  font-size: 11px;
  white-space: nowrap;
}

.media-grid--table .usage-row {
  display: flex;
  flex: 0 0 auto;
  gap: 2px;
  white-space: nowrap;
}

.media-grid--table .usage-row .q-chip {
  margin: 0;
}

.media-grid--table .media-item-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin: 0;
  padding: 0 8px 0 4px;
  white-space: nowrap;
}

.media-grid--table .media-item-actions .q-btn {
  min-height: 28px;
  padding: 0 6px;
}

.empty-card {
  margin-top: 16px;
}

@media (max-width: 1100px) {
  .filters-grid {
    grid-template-columns: 1fr 1fr;
  }


  .media-grid--medium {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {


  .catalog-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 600px) {
  .media-grid--table {
    grid-template-columns: 1fr;
  }

  .media-page {
    padding: 20px 16px;
  }

  .media-header {
    flex-direction: column;
    margin-bottom: 24px;
  }

  .media-header h1 {
    font-size: 28px;
  }

  .metadata-grid {
    grid-template-columns: 1fr;
  }

  .filters-grid {
    grid-template-columns: 1fr;
  }

  .catalog-toolbar-actions {
    align-items: stretch;
    flex-direction: column;
    width: 100%;
  }

  .catalog-toolbar-actions .q-btn-toggle {
    width: 100%;
  }

  .catalog-toolbar-actions .q-btn {
    width: 100%;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }

  .catalog-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .media-grid--small,
  .media-grid--medium,

  .media-grid--table .media-item {
    display: block;
  }

  .media-grid--table .media-thumbnail-wrap {
    min-height: 0;
    aspect-ratio: 16 / 10;
  }

  .variant-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
