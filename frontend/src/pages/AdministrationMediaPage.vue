<template>
  <q-page class="media-page">
    <div class="media-container">
      <header class="media-header">
        <div>
          <!-- Логотип как на публичном сайте; клик — переход на сайт -->
          <RouterLink
            to="/"
            class="media-brand"
            title="Перейти на сайт"
            aria-label="Albion — перейти на сайт"
          >
            <img src="/logo.png" alt="Albion" class="media-brand-logo" />
          </RouterLink>
        </div>

        <q-btn
          flat
          no-caps
          label="← Администрирование"
          @click="router.push('/administration/dashboard')"
        />
      </header>

      <q-card flat bordered class="media-card">
        <q-card-section class="form-section">
          <!-- Нативный выбор файлов: label[for] открывает системное окно
               без программного click(), который в Chrome/Linux зависает. -->
          <input
            id="media-file-input"
            type="file"
            multiple
            accept=".jpg,.jpeg,.jfif,.jpe,.png,.webp,.heic,.heif,.tif,.tiff,.bmp,.psd,.gif,.mp4,.mov,.webm,.avi,.mkv,.m4v,.mpeg,.mpg,.pdf,.doc,.docx,.odt,.rtf,.txt,.md,.xls,.xlsx,.ods,.csv,.ppt,.pptx,.odp, image/*, video/*, application/pdf"
            class="file-input-hidden"
            :disabled="uploading"
            @change="onNativeFilesPicked"
          />

          <div class="upload-main-action">
            <label
              class="upload-button"
              for="media-file-input"
              title="Изображения автоматически подготавливаются в нужных вариантах, видео — в MP4 с превью, документы сохраняются как есть."
            >
              Загрузка медиафайла
            </label>
          </div>

          <div class="formats-hint">
            Допустимые форматы — изображения: JPG, PNG, WEBP, HEIC/HEIF, TIFF,
            BMP, PSD, GIF · видео: MP4, MOV, WebM, AVI, MKV, MPEG · документы:
            PDF, DOC/DOCX, ODT, RTF, TXT, MD, XLS/XLSX, ODS, CSV, PPT/PPTX, ODP
          </div>
        </q-card-section>
      </q-card>

      <q-dialog v-model="uploadDialog" persistent>
        <q-card class="upload-queue-dialog">
          <q-card-section>
            <div class="section-title">Добавление медиафайлов</div>
            <div class="section-description">
              Подготовьте параметры файлов перед добавлением в хранилище.
            </div>
          </q-card-section>

          <q-card-section>
            <q-linear-progress
              :value="uploadProgress / 100"
              size="8px"
              rounded
              class="q-mb-md"
            />

            <div class="upload-progress-text">
              {{ Math.round(uploadProgress) }}%
            </div>

            <div class="upload-queue-list">
              <div
                v-for="(item, index) in uploadQueue"
                :key="`${item.file.name}-${index}`"
                class="upload-queue-item"
              >
                <div class="upload-queue-preview">
                  <video
                    v-if="item.file.type.startsWith('video/')"
                    :src="queuePreviewUrl(item)"
                    muted
                  />
                  <div
                    v-else-if="isDocumentFile(item.file)"
                    class="upload-queue-preview-doc"
                  >
                    <span>{{ documentExtension(item.file.name) }}</span>
                  </div>
                  <img v-else :src="queuePreviewUrl(item)" />
                </div>

                <div class="upload-queue-fields">
                  <q-input
                    v-model="item.name"
                    outlined
                    dense
                    label="Имя файла"
                    :disable="uploading || item.status !== 'pending'"
                  />

                  <q-input
                    v-model="item.alt"
                    outlined
                    dense
                    label="Описание"
                    :disable="uploading || item.status !== 'pending'"
                  />

                  <div class="category-select-wrap">
                    <q-select
                      v-model="item.categoryId"
                      multiple
                      use-chips
                      outlined
                      dense
                      emit-value
                      map-options
                      label="Категория"
                      :options="
                        mediaCategories.map(category => ({
                          label: category.name,
                          value: category.id
                        }))
                      "
                      :disable="uploading || item.status !== 'pending'"
                    />

                    <q-btn
                      outline
                      square
                      icon="add"
                      aria-label="Добавить категорию"
                      title="Добавить категорию"
                      :disable="uploading"
                      @click="openCategoryDialog"
                    />
                  </div>
                </div>

                <div class="upload-queue-status">
                  <q-spinner v-if="item.status === 'uploading'" size="20px" />
                  <q-icon
                    v-else-if="item.status === 'success'"
                    name="check_circle"
                    color="positive"
                  />
                  <q-icon
                    v-else-if="item.status === 'excluded'"
                    name="remove_circle"
                    color="grey-6"
                  />
                  <q-icon
                    v-else-if="item.status === 'error'"
                    name="error"
                    color="negative"
                  />
                  <span v-if="item.status === 'error'">{{ item.error }}</span>
                </div>

                <div class="upload-queue-actions">
                  <q-btn
                    flat
                    round
                    icon="check"
                    color="positive"
                    aria-label="Добавить файл"
                    title="Добавить файл"
                    :disable="uploading || item.status !== 'pending'"
                    @click="uploadSingleQueue(item)"
                  />

                  <q-btn
                    flat
                    round
                    icon="close"
                    color="negative"
                    aria-label="Удалить из очереди"
                    title="Не добавлять файл"
                    :disable="uploading || item.status !== 'pending'"
                    @click="excludeUploadQueueItem(item)"
                  />
                </div>
              </div>
            </div>
          </q-card-section>

          <q-card-actions v-if="uploadQueue.length > 1" align="right">
            <q-btn
              flat
              no-caps
              label="ЗАКРЫТЬ"
              :disable="uploading"
              @click="uploadDialog = false"
            />

            <q-btn
              unelevated
              color="primary"
              no-caps
              label="ДОБАВИТЬ ВСЕ"
              @click="uploadAllQueue"
              :disable="
                uploading ||
                !uploadQueue.some(item => item.status === 'pending')
              "
            />
          </q-card-actions>
        </q-card>
      </q-dialog>

      <q-dialog v-model="categoryDialog">
        <q-card style="min-width: 360px; max-width: 90vw">
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
        <q-card style="min-width: 420px; max-width: 90vw">
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
              multiple
              use-chips
              outlined
              emit-value
              map-options
              label="Категория"
              :options="
                mediaCategories.map(category => ({
                  label: category.name,
                  value: category.id,
                  disable:
                    lockedCategoryIds.includes(category.id) &&
                    editCategoryId.includes(category.id)
                }))
              "
              :loading="loadingCategories"
              :disable="savingMedia"
            />

            <!--
              Раздел, где файл реально используется, снять нельзя —
              добавлять другие теги при этом можно.
            -->
            <p
              v-if="editingMedia && editingMedia.used_sections?.length"
              class="edit-usage-note"
            >
              Используется: <b>{{ editingMedia.used_sections.join(', ') }}</b
              >. Этот раздел снять нельзя, остальные теги — можно менять.
            </p>
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
                <span> {{ variant.width }} × {{ variant.height }} </span>
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

              <q-select
                v-model="filterCategoryId"
                multiple
                use-chips
                outlined
                dense
                clearable
                emit-value
                map-options
                label="Раздел хранения"
                :options="
                  mediaCategories.map(category => ({
                    label: category.name,
                    value: category.id
                  }))
                "
                :loading="loadingCategories"
              />

              <q-select
                v-model="filterMediaType"
                outlined
                dense
                emit-value
                map-options
                label="Тип медиа"
                :options="[
                  { label: 'ВСЕ', value: 'all' },
                  { label: 'ФОТО', value: 'photo' },
                  { label: 'ВИДЕО', value: 'video' },
                  { label: 'ДОКУМЕНТЫ', value: 'document' }
                ]"
              />
            </div>

            <div class="catalog-toolbar">
              <div class="catalog-count">
                Найдено файлов: <strong>{{ mediaTotal }}</strong>
                <span v-if="mediaItems.length < mediaTotal">
                  · показано {{ mediaItems.length }}
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

        <q-card v-if="catalogError" flat class="result-card result-error">
          <q-card-section>
            <div class="result-title">Ошибка</div>
            <div>{{ catalogError }}</div>
          </q-card-section>
        </q-card>

        <q-card
          v-else-if="!loadingMedia && mediaTotal === 0"
          flat
          bordered
          class="empty-card"
        >
          <q-card-section>
            {{
              hasActiveFilters
                ? 'По заданным фильтрам медиафайлы не найдены.'
                : 'Пока нет загруженных медиафайлов.'
            }}
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
          ref="mediaGridRef"
          :class="['media-grid', `media-grid--${viewMode}`]"
          @scroll.passive="handleMediaGridScroll"
          :style="
            viewMode === 'small'
              ? { '--media-small-columns': smallColumns }
              : undefined
          "
        >
          <q-card
            v-for="item in filteredMediaItems"
            :key="item.id"
            flat
            bordered
            class="media-item"
          >
            <div class="media-thumbnail-wrap">
              <video
                v-if="
                  viewMode === 'medium' && item.mime_type?.startsWith('video/')
                "
                :src="storageUrl(item.storage_path)"
                :poster="thumbnailUrl(item)"
                class="media-thumbnail media-thumbnail--video"
                controls
                preload="metadata"
                playsinline
              />

              <img
                v-else-if="!isDocument(item) && thumbnailUrl(item)"
                :src="thumbnailUrl(item)"
                :alt="item.alt || item.original_name"
                class="media-thumbnail"
                loading="lazy"
              />

              <div
                v-else-if="isDocument(item)"
                class="media-thumbnail-empty media-thumbnail-document"
              >
                <span class="media-document-icon">▤</span>
                <span class="media-document-ext">
                  {{ documentExtension(item.original_name) }}
                </span>
              </div>

              <div v-else class="media-thumbnail-empty"> Нет превью </div>
            </div>

            <q-card-section class="media-item-content">
              <div class="media-item-path">
                {{ (item.category_name || 'Разное').toUpperCase() }}
              </div>

              <div class="media-item-name" :title="item.original_name">
                <span
                  class="media-type-icon"
                  :class="{
                    'media-type-icon--video':
                      item.mime_type?.startsWith('video/'),
                    'media-type-icon--document': isDocument(item)
                  }"
                >
                  {{ mediaTypeSymbol(item) }}
                </span>
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

                <!-- Действия стоят в одной строке с чипом статуса -->
                <div class="media-item-actions">
                  <q-btn
                    flat
                    round
                    dense
                    icon="open_in_new"
                    aria-label="Открыть в новой вкладке"
                    :href="storageUrl(item.storage_path)"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <q-tooltip>Открыть в новой вкладке</q-tooltip>
                  </q-btn>

                  <q-btn
                    flat
                    round
                    dense
                    icon="edit"
                    aria-label="Редактировать"
                    @click="openEditMedia(item)"
                  >
                    <q-tooltip>Редактировать</q-tooltip>
                  </q-btn>

                  <q-btn
                    flat
                    round
                    dense
                    icon="delete"
                    color="negative"
                    aria-label="Удалить"
                    :disable="item.used_in_news || item.used_in_pages"
                    :loading="deletingId === item.id"
                    @click="deleteMedia(item)"
                  >
                    <q-tooltip>
                      {{
                        item.used_in_news || item.used_in_pages
                          ? 'Файл используется — удалить нельзя'
                          : 'Удалить'
                      }}
                    </q-tooltip>
                  </q-btn>
                </div>
              </div>
            </q-card-section>
          </q-card>
        </div>
        <div v-if="mediaStats" class="media-stats">
          <div class="media-stats__item">
            <span class="media-stats__label">ФАЙЛЫ</span>
            <strong>{{ mediaStats.overview.total_files }}</strong>
            <span
              >{{ mediaStats.overview.used_files }} используется ·
              {{ formatStatsBytes(mediaStats.overview.size_bytes) }}</span
            >
          </div>
          <div class="media-stats__item">
            <span class="media-stats__label">ХРАНИЛИЩЕ</span>
            <strong>{{
              formatStatsPercent(mediaStats.storage.free_percent)
            }}</strong>
            <span
              >{{ formatStatsBytes(mediaStats.storage.used_bytes) }} из
              {{ formatStatsBytes(mediaStats.storage.total_bytes) }}</span
            >
          </div>
          <div class="media-stats__item">
            <span class="media-stats__label">CPU СЕРВЕРА</span>
            <strong>{{ formatStatsPercent(mediaStats.cpu_percent) }}</strong>
            <span>текущая загрузка</span>
          </div>

          <div class="media-stats__item media-stats__item--wide">
            <span class="media-stats__label">КАТЕГОРИИ</span>
            <div
              v-for="category in mediaStats.categories"
              :key="category.id"
              class="media-stats__row"
            >
              <span>{{ category.name }}</span>
              <span
                >{{ category.total_files }} / {{ category.used_files }} ·
                {{ formatStatsBytes(category.size_bytes) }}</span
              >
            </div>
          </div>

          <div class="media-stats__item media-stats__item--wide">
            <span class="media-stats__label">ТИПЫ</span>
            <div class="media-stats__row">
              <span>Фото</span>
              <span
                >{{ mediaStats.types.photos.total_files }} ·
                {{ formatStatsBytes(mediaStats.types.photos.size_bytes) }}</span
              >
            </div>
            <div class="media-stats__row">
              <span>Видео</span>
              <span
                >{{ mediaStats.types.videos.total_files }} ·
                {{ formatStatsBytes(mediaStats.types.videos.size_bytes) }}</span
              >
            </div>
            <div class="media-stats__row">
              <span>Другое</span>
              <span
                >{{ mediaStats.types.other.total_files }} ·
                {{ formatStatsBytes(mediaStats.types.other.size_bytes) }}</span
              >
            </div>
            <div
              v-for="extension in mediaStats.types.extensions"
              :key="extension.extension"
              class="media-stats__row"
            >
              <span>.{{ extension.extension }}</span>
              <span
                >{{ extension.total_files }} ·
                {{ formatStatsBytes(extension.size_bytes) }}</span
              >
            </div>
          </div>
        </div>
      </section>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const uploading = ref(false)
const error = ref('')
const result = ref(null)
const uploadQueue = ref([])
const uploadDialog = ref(false)
const uploadProgress = ref(0)
const uploadCurrentIndex = ref(-1)

const mediaItems = ref([])
const mediaGridRef = ref(null)
const mediaPageSize = 30
const mediaOffset = ref(0)
const mediaTotal = ref(0)
let mediaRequestGeneration = 0
let mediaFilterTimer = null
const mediaHasMore = ref(true)
const loadingMoreMedia = ref(false)
const loadingMedia = ref(false)
const catalogError = ref('')
const deletingId = ref(null)
const mediaStats = ref(null)
const loadingMediaStats = ref(false)
const mediaStatsError = ref('')
const mediaStatsTimer = ref(null)

const mediaCategories = ref([])
const loadingCategories = ref(false)
const uploadCategoryId = ref([1])
const filterCategoryId = ref([])
const filterMediaType = ref('all')

const categoryDialog = ref(false)
const newCategoryName = ref('')
const creatingCategory = ref(false)

/* Открыть диалог создания категории с пустым полем. */
function openCategoryDialog() {
  newCategoryName.value = ''
  categoryDialog.value = true
}
const editDialog = ref(false)
const editingMedia = ref(null)
const editOriginalName = ref('')
const editCategoryId = ref([])

/*
 * Разделы, которые «держит» фактическое использование файла: их нельзя
 * снять (сервер тоже это проверяет), но можно добавить любые другие.
 */
const lockedCategoryIds = computed(() =>
  (editingMedia.value?.used_sections || [])
    .map(name => mediaCategories.value.find(item => item.name === name)?.id)
    .filter(id => id !== undefined)
)
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
  { label: '8', value: 8 }
]

const viewModeOptions = [
  { label: 'Таблица', value: 'table' },
  { label: 'Компакт', value: 'small' },
  { label: 'Полный', value: 'medium' }
]

function onNativeFilesPicked(event) {
  prepareUploadQueue(event.target.files)
  event.target.value = ''
}

function prepareUploadQueue(files) {
  const selectedFiles = Array.from(files || []).filter(
    item => item instanceof File
  )

  if (!selectedFiles.length) {
    return
  }

  revokeQueuePreviews()

  uploadQueue.value = selectedFiles.map(item => ({
    file: item,
    name: item.name,
    alt: '',
    categoryId: [1],
    status: 'pending',
    error: ''
  }))

  uploadProgress.value = 0
  uploadCurrentIndex.value = -1
  uploadDialog.value = true
}

function queuePreviewUrl(item) {
  if (!item.previewUrl) {
    item.previewUrl = URL.createObjectURL(item.file)
  }

  return item.previewUrl
}

/* Освобождаем все object URL превью очереди (иначе утечка Blob-памяти). */
function revokeQueuePreviews() {
  uploadQueue.value.forEach(item => {
    if (item.previewUrl) {
      URL.revokeObjectURL(item.previewUrl)
      item.previewUrl = ''
    }
  })
}

function storageUrl(path) {
  return `/storage/${path}`
}

const DOCUMENT_EXTENSIONS = new Set([
  'pdf',
  'doc',
  'docx',
  'odt',
  'rtf',
  'txt',
  'md',
  'xls',
  'xlsx',
  'ods',
  'csv',
  'ppt',
  'pptx',
  'odp'
])

const DOCUMENT_MIME_TYPES = new Set([
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.oasis.opendocument.text',
  'application/rtf',
  'text/plain',
  'text/markdown',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.oasis.opendocument.spreadsheet',
  'text/csv',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.oasis.opendocument.presentation'
])

function fileExtension(name) {
  const parts = String(name || '').split('.')

  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

function isDocumentFile(file) {
  return DOCUMENT_EXTENSIONS.has(fileExtension(file?.name))
}

function isDocument(item) {
  return DOCUMENT_MIME_TYPES.has(item?.mime_type)
}

function documentExtension(name) {
  const extension = fileExtension(name)

  return DOCUMENT_EXTENSIONS.has(extension) ? extension.toUpperCase() : 'DOC'
}

function mediaTypeSymbol(item) {
  if (item?.mime_type?.startsWith('video/')) {
    return '▶'
  }

  return isDocument(item) ? '▤' : '▣'
}

function thumbnailUrl(item) {
  if (item.mime_type?.startsWith('video/') && item.preview_path) {
    return storageUrl(item.preview_path)
  }

  const thumb = item.variants?.find(variant => variant.variant === 'thumb')

  return storageUrl(thumb?.storage_path || item.storage_path)
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—'
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function formatStatsBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return '—'
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function formatStatsPercent(value) {
  if (!Number.isFinite(value)) {
    return '—'
  }

  return `${value.toFixed(1)}%`
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

const filteredMediaItems = computed(() => mediaItems.value)

const hasActiveFilters = computed(() => {
  return Boolean(
    searchQuery.value ||
    filterCategoryId.value.length > 0 ||
    filterMediaType.value !== 'all' ||
    dateFrom.value ||
    dateTo.value
  )
})

function resetFilters() {
  searchQuery.value = ''
  filterCategoryId.value = []
  dateFrom.value = ''
  filterMediaType.value = 'all'
  dateTo.value = ''
}

watch(
  [searchQuery, dateFrom, dateTo, filterMediaType, filterCategoryId],
  () => {
    if (mediaFilterTimer) window.clearTimeout(mediaFilterTimer)
    mediaFilterTimer = window.setTimeout(() => loadMedia(), 250)
  },
  { deep: true }
)

function mediaFilterParams() {
  const params = new URLSearchParams()
  const search = searchQuery.value.trim()
  if (search) params.set('search', search)
  if (filterMediaType.value !== 'all') {
    params.set('media_type', filterMediaType.value)
  }
  if (dateFrom.value) params.set('date_from', dateFrom.value)
  if (dateTo.value) params.set('date_to', dateTo.value)
  if (filterCategoryId.value.length) {
    params.set('category_ids', filterCategoryId.value.join(','))
  }
  return params
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
      catalogError.value = data?.detail || 'Не удалось создать категорию'
      return
    }

    const category = data?.category

    if (category) {
      mediaCategories.value = [...mediaCategories.value, category].sort(
        (a, b) =>
          a.sort_order !== b.sort_order
            ? a.sort_order - b.sort_order
            : a.name.localeCompare(b.name, 'ru')
      )
      uploadCategoryId.value = [...uploadCategoryId.value, category.id]
    }

    newCategoryName.value = ''
    categoryDialog.value = false
  } catch {
    catalogError.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    creatingCategory.value = false
  }
}

function openEditMedia(item) {
  editingMedia.value = item
  editOriginalName.value = item.original_name || ''
  editCategoryId.value = Array.isArray(item.category_id)
    ? item.category_id
    : item.category_id != null
      ? [item.category_id]
      : [...uploadCategoryId.value]
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

  if (!editCategoryId.value.length) {
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
  editCategoryId.value.forEach(categoryId =>
    formData.append('category_id', String(categoryId))
  )

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
      catalogError.value = data?.detail || 'Не удалось сохранить изменения'
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
      catalogError.value = data?.detail || 'Не удалось загрузить категории'
      return
    }

    mediaCategories.value = data?.categories || []

    if (
      mediaCategories.value.length &&
      !mediaCategories.value.some(category =>
        uploadCategoryId.value.includes(category.id)
      )
    ) {
      uploadCategoryId.value = [mediaCategories.value[0].id]
    }
  } catch {
    catalogError.value = 'Не удалось загрузить категории'
  } finally {
    loadingCategories.value = false
  }
}

async function loadMedia() {
  const generation = ++mediaRequestGeneration
  const token = await getAdminToken()

  if (!token || generation !== mediaRequestGeneration) return

  loadingMedia.value = true
  loadingMoreMedia.value = false
  catalogError.value = ''
  mediaOffset.value = 0
  mediaHasMore.value = true

  try {
    const params = mediaFilterParams()
    params.set('limit', String(mediaPageSize))
    params.set('offset', '0')
    const response = await fetch(`/api/admin/media?${params}`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)
    if (generation !== mediaRequestGeneration) return
    if (!response.ok) {
      catalogError.value = data?.detail || 'Не удалось загрузить каталог медиа'
      return
    }

    mediaItems.value = data?.media || []
    mediaTotal.value = Number(data?.total ?? mediaItems.value.length)
    mediaOffset.value = mediaItems.value.length
    mediaHasMore.value = data?.has_more === true
  } catch {
    if (generation === mediaRequestGeneration) {
      catalogError.value = 'Не удалось выполнить запрос к серверу'
    }
  } finally {
    if (generation === mediaRequestGeneration) loadingMedia.value = false
  }
}
async function loadMediaStats() {
  const token = await getAdminToken()

  if (!token) {
    return
  }

  loadingMediaStats.value = true
  mediaStatsError.value = ''

  try {
    const response = await fetch('/api/admin/media/stats', {
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
      mediaStatsError.value =
        data?.detail || 'Не удалось загрузить статистику медиа'
      return
    }

    mediaStats.value = data
  } catch {
    mediaStatsError.value = 'Не удалось загрузить статистику медиа'
  } finally {
    loadingMediaStats.value = false
  }
}

async function loadMoreMedia() {
  if (loadingMedia.value || loadingMoreMedia.value || !mediaHasMore.value) {
    return
  }

  const generation = mediaRequestGeneration
  const token = await getAdminToken()

  if (!token || generation !== mediaRequestGeneration) return

  loadingMoreMedia.value = true

  try {
    const params = mediaFilterParams()
    params.set('limit', String(mediaPageSize))
    params.set('offset', String(mediaOffset.value))
    const response = await fetch(`/api/admin/media?${params}`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.status === 401) {
      sessionStorage.removeItem('albion_admin_token')
      await router.replace('/administration')
      return
    }

    const data = await response.json().catch(() => null)
    if (generation !== mediaRequestGeneration) return

    if (!response.ok) {
      catalogError.value =
        data?.detail || 'Не удалось загрузить следующие файлы'
      return
    }

    const newItems = data?.media || []
    mediaItems.value = [...mediaItems.value, ...newItems]
    mediaOffset.value += newItems.length
    mediaTotal.value = Number(data?.total ?? mediaTotal.value)
    mediaHasMore.value = data?.has_more === true
  } catch {
    if (generation === mediaRequestGeneration) {
      catalogError.value = 'Не удалось выполнить запрос к серверу'
    }
  } finally {
    if (generation === mediaRequestGeneration) loadingMoreMedia.value = false
  }
}

function handleMediaGridScroll(event) {
  const element = event.currentTarget
  if (!element) return

  const remaining =
    element.scrollHeight - element.scrollTop - element.clientHeight
  if (remaining < 600) loadMoreMedia()
}

async function uploadQueueItem(item) {
  const token = await getAdminToken()

  if (!token) {
    return false
  }

  item.status = 'uploading'
  item.error = ''

  const formData = new FormData()
  formData.append('file', item.file)
  formData.append('original_name', item.name.trim() || item.file.name)
  item.categoryId.forEach(categoryId =>
    formData.append('category_id', String(categoryId))
  )

  if (item.alt.trim()) {
    formData.append('alt', item.alt.trim())
  }

  if (item.title?.trim()) {
    formData.append('title', item.title.trim())
  }

  if (item.file.type.startsWith('video/') && item.previewTime > 0) {
    formData.append('preview_time', String(item.previewTime))
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
      return false
    }

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      item.status = 'error'
      item.error = data?.detail || 'Не удалось загрузить файл'
      return false
    }

    item.status = 'success'
    item.result = data?.media || null
    return true
  } catch {
    item.status = 'error'
    item.error = 'Не удалось выполнить запрос к серверу'
    return false
  }
}
function excludeUploadQueueItem(item) {
  if (uploading.value || item?.status !== 'pending') return
  item.status = 'excluded'
  item.error = ''
}

async function uploadSingleQueue(item) {
  uploading.value = true
  uploadProgress.value = 0
  uploadCurrentIndex.value = uploadQueue.value.indexOf(item)

  try {
    const success = await uploadQueueItem(item)
    uploadProgress.value = success ? 100 : 0

    if (success) {
      await loadMedia()

      if (uploadQueue.value.length === 1) {
        uploadDialog.value = false
      }
    }
  } finally {
    uploading.value = false
    uploadCurrentIndex.value = -1
  }
}

async function uploadAllQueue() {
  const items = uploadQueue.value.filter(item => item.status === 'pending')

  if (!items.length) {
    return
  }

  items.forEach(item => {
    item.status = 'pending'
    item.error = ''
  })

  uploading.value = true
  uploadProgress.value = 0
  uploadCurrentIndex.value = -1

  let completed = 0
  let allUploaded = true

  try {
    for (let index = 0; index < items.length; index += 1) {
      uploadCurrentIndex.value = uploadQueue.value.indexOf(items[index])
      const success = await uploadQueueItem(items[index])

      if (!success) {
        allUploaded = false
      }

      completed += 1
      uploadProgress.value = (completed / items.length) * 100
    }

    await loadMedia()

    if (allUploaded) {
      uploadDialog.value = false
    }
  } finally {
    uploading.value = false
    uploadCurrentIndex.value = -1
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
      catalogError.value = data?.detail || 'Не удалось удалить изображение'
      return
    }

    mediaItems.value = mediaItems.value.filter(media => media.id !== item.id)
    mediaTotal.value = Math.max(0, mediaTotal.value - 1)

    if (result.value?.id === item.id) {
      result.value = null
    }

    await loadMediaStats()
  } catch {
    catalogError.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  loadMediaCategories()
  loadMedia()
  loadMediaStats()

  mediaStatsTimer.value = window.setInterval(() => {
    loadMediaStats()
  }, 30000)
})

onBeforeUnmount(() => {
  if (mediaStatsTimer.value) {
    window.clearInterval(mediaStatsTimer.value)
    mediaStatsTimer.value = null
  }
  if (mediaFilterTimer) {
    window.clearTimeout(mediaFilterTimer)
    mediaFilterTimer = null
  }
  mediaRequestGeneration += 1

  revokeQueuePreviews()
})
</script>

<style scoped>
.edit-usage-note {
  margin: 10px 0 0;
  color: #6b6b6b;
  font-size: 12px;
  line-height: 1.45;
}

.edit-usage-note b {
  color: #b0325c;
}

.media-page {
  min-height: 100vh;
  padding: 32px 24px;
}

/* upload queue */
.upload-queue-dialog {
  width: min(1100px, 94vw);
  max-width: 1100px;
}

.upload-queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}

.upload-queue-item {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--q-separator-color);
  border-radius: 8px;
}

.upload-queue-preview {
  width: 180px;
  height: 110px;
  overflow: hidden;
  border-radius: 6px;
  background: #f3f3f3;
}

.upload-queue-preview img,
.upload-queue-preview video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.upload-queue-preview-doc {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #4b5563;
}

.upload-queue-fields {
  min-width: 0;
}

.upload-queue-status {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  max-width: 180px;
  font-size: 12px;
  color: var(--q-negative);
}

.upload-queue-status span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-queue-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

@media (max-width: 700px) {
  .upload-queue-item {
    grid-template-columns: 110px minmax(0, 1fr) auto;
  }

  .upload-queue-preview {
    width: 110px;
    height: 70px;
  }

  .upload-queue-status {
    grid-column: 2;
    justify-content: flex-start;
  }

  .upload-queue-actions {
    grid-column: 3;
    grid-row: 1 / span 2;
  }
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
  display: inline-flex;
  align-items: center;

  margin-bottom: 12px;
}

.media-brand-logo {
  display: block;

  width: auto;
  height: 42px;

  max-width: 150px;
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

/* Строка статуса: чипы слева, действия — прижаты вправо. */
.usage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.media-item-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 0;
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

.formats-hint {
  margin-top: 2px;
  color: #8b8b8b;
  font-size: 12px;
  line-height: 1.4;
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
  max-width: 100%;
  height: auto;
  max-height: 420px;
  object-fit: contain;
  border-radius: 12px;
  background: #f3f5f6;
}

.upload-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  padding: 0 18px;
  border-radius: 8px;
  background: var(--q-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  user-select: none;
}

.upload-button:hover {
  filter: brightness(0.95);
}

.file-input-hidden {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
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
  grid-template-columns: 2fr 1fr 1fr;
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

.media-type-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  margin-right: 5px;
  font-size: 11px;
  opacity: 0.7;
}

.media-type-icon--video {
  opacity: 1;
}

.media-type-icon--document {
  opacity: 1;
}

.media-thumbnail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #9ca3af;
  font-size: 13px;
}

.media-thumbnail-document {
  flex-direction: column;
  gap: 6px;
  color: #4b5563;
}

.media-document-icon {
  font-size: 28px;
  line-height: 1;
  opacity: 0.65;
}

.media-document-ext {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.media-grid {
  max-height: 70vh;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 6px;

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

.media-grid--medium .media-thumbnail-wrap {
  width: 100%;
  aspect-ratio: 4 / 3;
  overflow: hidden;
  background: #f3f5f6;
}

.media-grid--small .media-thumbnail,
.media-grid--medium .media-thumbnail {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
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

.media-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 18px;
  margin-top: 12px;
  padding: 8px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  font-size: 12px;
  line-height: 1.4;
}

.media-stats__item,
.media-stats__item--wide {
  display: inline-flex;
  align-items: center;
  flex: 0 1 auto;
  gap: 4px;
  min-width: 0;
}

.media-stats__label {
  margin-right: 2px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: #777;
}

.media-stats__item strong {
  font-size: 12px;
  font-weight: 600;
}

.media-stats__item > span:not(.media-stats__label) {
  font-size: 12px;
  color: #666;
}

.media-stats__row {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-right: 10px;
  font-size: 12px;
}

.media-stats__row span:last-child {
  white-space: nowrap;
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
