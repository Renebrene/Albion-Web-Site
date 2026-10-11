<template>
  <div class="news-media-field">
    <div class="nmf-toolbar">
      <div class="nmf-summary">
        <span class="nmf-count">Медиа: {{ items.length }}</span>
        <span v-if="items.length" class="nmf-hint"
          >Порядок = порядок карусели</span
        >
      </div>

      <div class="nmf-toolbar-actions">
        <q-btn
          outline
          no-caps
          icon="photo_library"
          label="Добавить из медиатеки"
          :disable="uploading"
          @click="pickerOpen = true"
        />

        <!-- label[for] открывает системное окно без программного click() -->
        <label
          class="nmf-upload-btn"
          :class="{ 'nmf-upload-btn--disabled': uploading }"
          :for="fileInputId"
        >
          <q-icon name="upload" class="q-mr-xs" />
          {{ uploading ? 'Загрузка…' : 'Загрузить файлы' }}
        </label>

        <input
          :id="fileInputId"
          ref="fileInput"
          type="file"
          multiple
          accept="image/*,video/*,.gif"
          class="nmf-file-input"
          :disabled="uploading"
          @change="onFilesPicked"
        />
      </div>
    </div>

    <div v-if="!items.length" class="nmf-empty">
      Файлов пока нет. Добавьте фото, видео или GIF из медиатеки либо загрузите
      новые.
    </div>

    <div v-else class="nmf-grid">
      <div
        v-for="(item, index) in items"
        :key="item.id"
        class="nmf-item"
        :class="{ 'nmf-item--cover': item.id === coverId }"
      >
        <div class="nmf-thumb">
          <video
            v-if="isVideo(item)"
            :src="storageUrl(item.storage_path)"
            :poster="posterUrl(item) || undefined"
            muted
            preload="metadata"
          />
          <img
            v-else-if="thumbUrl(item)"
            :src="thumbUrl(item)"
            :alt="item.original_name || ''"
            loading="lazy"
            decoding="async"
          />
          <div v-else class="nmf-thumb-empty">Нет превью</div>

          <span class="nmf-type">{{ typeLabel(item) }}</span>
          <span v-if="item.id === coverId" class="nmf-cover-badge"
            >Обложка</span
          >
        </div>

        <div class="nmf-name" :title="item.original_name">
          {{ item.original_name || `Файл #${item.id}` }}
        </div>

        <div class="nmf-item-actions">
          <q-btn
            flat
            round
            dense
            icon="chevron_left"
            aria-label="Влево"
            :disable="index === 0"
            @click="move(index, -1)"
          >
            <q-tooltip>Влево</q-tooltip>
          </q-btn>

          <q-btn
            flat
            round
            dense
            icon="chevron_right"
            aria-label="Вправо"
            :disable="index === items.length - 1"
            @click="move(index, 1)"
          >
            <q-tooltip>Вправо</q-tooltip>
          </q-btn>

          <q-btn
            flat
            round
            dense
            icon="star"
            :color="item.id === coverId ? 'amber-8' : 'grey-7'"
            aria-label="Сделать обложкой"
            :disable="item.id === coverId"
            @click="setCover(item.id)"
          >
            <q-tooltip>Сделать обложкой</q-tooltip>
          </q-btn>

          <q-btn
            flat
            round
            dense
            icon="delete"
            color="negative"
            aria-label="Убрать"
            @click="remove(index)"
          >
            <q-tooltip>Убрать</q-tooltip>
          </q-btn>
        </div>
      </div>
    </div>

    <MediaPicker v-model="pickerOpen" multiple @select-many="onSelectMany" />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

import MediaPicker from './MediaPicker.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  coverId: { type: [Number, String], default: null }
})

const emit = defineEmits(['update:modelValue', 'update:coverId', 'notify'])

const fileInputId = `news-media-upload-${Date.now()}-${Math.floor(Math.random() * 1e6)}`

const pickerOpen = ref(false)
const uploading = ref(false)

/* Источник правды — prop от родителя; компонент только эмитит изменения. */
const items = computed(() =>
  Array.isArray(props.modelValue) ? props.modelValue : []
)

/* ---------- нормализация / helpers ---------- */

function normalize(media) {
  if (!media || media.id == null) return null
  return {
    id: media.id,
    original_name: media.original_name || media.name || '',
    storage_path: media.storage_path || '',
    mime_type: media.mime_type || '',
    preview_path: media.preview_path || null,
    variants: Array.isArray(media.variants) ? media.variants : []
  }
}

function storageUrl(path) {
  return path ? `/storage/${path}` : ''
}

function isVideo(item) {
  return String(item?.mime_type || '').startsWith('video/')
}

function isGif(item) {
  const mime = String(item?.mime_type || '').toLowerCase()
  if (mime === 'image/gif') return true
  return /\.gif$/i.test(item?.original_name || '')
}

function typeLabel(item) {
  if (isVideo(item)) return 'Видео'
  if (isGif(item)) return 'GIF'
  return 'Фото'
}

function posterUrl(item) {
  if (item?.preview_path) return storageUrl(item.preview_path)
  return ''
}

function thumbUrl(item) {
  if (item?.preview_path && isVideo(item)) return storageUrl(item.preview_path)
  const thumb = (item?.variants || []).find(
    variant => variant.variant === 'thumb'
  )
  return storageUrl(thumb?.storage_path || item?.storage_path)
}

/* ---------- изменение состава / порядка ---------- */

function commit(nextItems, nextCover = props.coverId) {
  emit('update:modelValue', nextItems)
  emit('update:coverId', nextCover)
}

function firstId(list) {
  return list.length ? list[0].id : null
}

function move(index, delta) {
  const target = index + delta
  if (target < 0 || target >= items.value.length) return
  const next = items.value.slice()
  const [moved] = next.splice(index, 1)
  next.splice(target, 0, moved)
  commit(next)
}

function remove(index) {
  const next = items.value.slice()
  const [removed] = next.splice(index, 1)
  let nextCover = props.coverId
  if (removed && removed.id === props.coverId) {
    nextCover = firstId(next)
  }
  if (!next.length) nextCover = null
  commit(next, nextCover)
}

function setCover(id) {
  commit(items.value.slice(), id)
}

function onSelectMany(ids, chosen) {
  const list =
    Array.isArray(chosen) && chosen.length
      ? chosen
      : (Array.isArray(ids) ? ids : []).map(id => ({ id }))

  const existing = new Set(items.value.map(item => item.id))
  const additions = []
  for (const raw of list) {
    const item = normalize(raw)
    if (!item || existing.has(item.id)) continue
    existing.add(item.id)
    additions.push(item)
  }

  if (!additions.length) return

  const next = [...items.value, ...additions]
  let nextCover = props.coverId
  if (nextCover == null) nextCover = firstId(next)
  commit(next, nextCover)
}

/* ---------- загрузка файлов ---------- */

function onFilesPicked(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  uploadFiles(files)
}

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function uploadFiles(files) {
  const list = files.filter(file => file instanceof File)
  if (!list.length) return

  uploading.value = true
  const additions = []
  let errors = 0

  try {
    for (const file of list) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('original_name', file.name)

      try {
        const response = await fetch('/api/admin/media', {
          method: 'POST',
          headers: authHeaders(),
          body: formData
        })

        if (response.status === 401) {
          sessionStorage.removeItem('albion_admin_token')
          emit('notify', 'Сессия истекла. Войдите заново.', 'error')
          break
        }

        const data = await response.json().catch(() => null)

        if (!response.ok) {
          errors += 1
          emit(
            'notify',
            data?.detail || `Не удалось загрузить «${file.name}»`,
            'error'
          )
          continue
        }

        const normalized = normalize(data?.media)
        if (normalized) additions.push(normalized)
      } catch (exc) {
        errors += 1
        emit('notify', `Не удалось загрузить «${file.name}»`, 'error')
      }
    }
  } finally {
    uploading.value = false
  }

  if (additions.length) {
    const existing = new Set(items.value.map(item => item.id))
    const fresh = additions.filter(item => !existing.has(item.id))
    const next = [...items.value, ...fresh]
    let nextCover = props.coverId
    if (nextCover == null) nextCover = firstId(next)
    commit(next, nextCover)
    emit('notify', `Загружено файлов: ${additions.length}`)
  } else if (errors) {
    /* ошибки уже показаны через notify */
  }
}
</script>

<style scoped>
.news-media-field {
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  padding: 12px;
  background: #fbfcfd;
}

.nmf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.nmf-summary {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.nmf-count {
  font-size: 13px;
  font-weight: 700;
  color: #37474f;
}

.nmf-hint {
  color: #90a4ae;
  font-size: 11px;
}

.nmf-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.nmf-upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 6px;
  border: 1px solid var(--q-primary);
  color: var(--q-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
}

.nmf-upload-btn:hover {
  background: rgba(0, 0, 0, 0.03);
}

.nmf-upload-btn--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.nmf-file-input {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
}

.nmf-empty {
  padding: 18px;
  color: #78909c;
  font-size: 13px;
  text-align: center;
}

.nmf-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}

.nmf-item {
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  padding: 6px;
  background: #fff;
}

.nmf-item--cover {
  border-color: #ffb300;
  box-shadow: 0 0 0 2px rgba(255, 179, 0, 0.18);
}

.nmf-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 7px;
  background: #f3f5f6;
}

.nmf-thumb img,
.nmf-thumb video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.nmf-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9aa1a9;
  font-size: 12px;
}

.nmf-type {
  position: absolute;
  left: 4px;
  bottom: 4px;
  padding: 1px 6px;
  border-radius: 5px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.nmf-cover-badge {
  position: absolute;
  top: 4px;
  left: 4px;
  padding: 1px 7px;
  border-radius: 5px;
  background: #ffb300;
  color: #3e2723;
  font-size: 10px;
  font-weight: 800;
}

.nmf-name {
  margin-top: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: #37474f;
}

.nmf-item-actions {
  display: flex;
  justify-content: space-between;
  gap: 2px;
  margin-top: 4px;
}
</style>
