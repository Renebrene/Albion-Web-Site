<template>
  <q-dialog v-model="open" @show="onShow">
    <q-card class="media-picker-card">
      <q-card-section class="media-picker-head">
        <div class="media-picker-title">Выбор из медиатеки</div>
        <q-btn flat round dense icon="close" aria-label="Закрыть" @click="open = false" />
      </q-card-section>

      <q-card-section class="media-picker-filters">
        <q-input
          v-model="search"
          outlined
          dense
          clearable
          autofocus
          label="Поиск по названию"
          placeholder="Имя файла"
        >
          <template #prepend>
            <q-icon name="search" />
          </template>
        </q-input>

        <q-select
          v-model="categoryIds"
          multiple
          use-chips
          outlined
          dense
          clearable
          emit-value
          map-options
          label="Раздел"
          :options="categoryOptions"
          :loading="loadingCategories"
        />
      </q-card-section>

      <q-separator />

      <q-card-section class="media-picker-body">
        <div v-if="loading" class="media-picker-state">
          <q-spinner size="24px" />
          <span>Загрузка…</span>
        </div>

        <div v-else-if="error" class="media-picker-state media-picker-state--error">
          {{ error }}
        </div>

        <div v-else-if="!filteredItems.length" class="media-picker-state">
          {{ items.length ? 'По заданным условиям файлы не найдены.' : 'В медиатеке пока нет файлов.' }}
        </div>

        <div v-else class="media-picker-grid">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="media-picker-item"
            :class="{ 'media-picker-item--selected': item.id === selectedId }"
            tabindex="0"
            @click="selectedId = item.id"
            @dblclick="confirm(item)"
            @keyup.enter="confirm(item)"
          >
            <div class="media-picker-thumb">
              <video
                v-if="item.mime_type?.startsWith('video/') && thumbnailUrl(item)"
                :src="storageUrl(item.storage_path)"
                :poster="thumbnailUrl(item)"
                muted
                preload="metadata"
              />
              <img
                v-else-if="thumbnailUrl(item)"
                :src="thumbnailUrl(item)"
                :alt="item.original_name"
                loading="lazy"
              >
              <div v-else class="media-picker-thumb-empty">Нет превью</div>
            </div>

            <div class="media-picker-item-name" :title="item.original_name">
              {{ item.original_name }}
            </div>
            <div class="media-picker-item-category">
              {{ (item.category_name || 'Разное').toUpperCase() }}
            </div>
          </div>
        </div>

        <div v-if="hasMore && !loading" class="media-picker-more">
          <q-btn
            flat
            no-caps
            :loading="loadingMore"
            label="Показать ещё"
            @click="loadMore"
          />
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn flat no-caps label="Отмена" @click="open = false" />
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Выбрать"
          :disable="!selectedItem"
          @click="confirm(selectedItem)"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'select'])

const PAGE_SIZE = 30

const open = ref(props.modelValue)

watch(() => props.modelValue, (value) => {
  open.value = value
})

watch(open, (value) => {
  emit('update:modelValue', value)
})

const items = ref([])
const categories = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const loadingCategories = ref(false)
const hasMore = ref(false)
const offset = ref(0)
const error = ref('')
const search = ref('')
const categoryIds = ref([])
const selectedId = ref(null)
let loadedOnce = false

const categoryOptions = computed(() =>
  categories.value.map((category) => ({ label: category.name, value: category.id }))
)

const filteredItems = computed(() => {
  const query = search.value.trim().toLowerCase()

  return items.value.filter((item) => {
    if (query && !(item.original_name || '').toLowerCase().includes(query)) {
      return false
    }

    if (
      categoryIds.value.length &&
      !categoryIds.value.some((id) => item.category_id?.includes(id))
    ) {
      return false
    }

    return true
  })
})

const selectedItem = computed(
  () => items.value.find((item) => item.id === selectedId.value) || null
)

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

function storageUrl(path) {
  return `/storage/${path}`
}

function thumbnailUrl(item) {
  if (item.mime_type?.startsWith('video/') && item.preview_path) {
    return storageUrl(item.preview_path)
  }

  const thumb = item.variants?.find((variant) => variant.variant === 'thumb')
  return storageUrl(thumb?.storage_path || item.storage_path)
}

async function fetchMedia(limit, offsetValue) {
  const response = await fetch(
    `/api/admin/media?limit=${limit}&offset=${offsetValue}`,
    { headers: authHeaders() }
  )

  if (response.status === 401) {
    sessionStorage.removeItem('albion_admin_token')
    throw new Error('Сессия истекла. Войдите заново.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error(data?.detail || 'Не удалось загрузить медиатеку')
  }

  return {
    media: data?.media || [],
    hasMore: data?.has_more === true
  }
}

async function loadCategories() {
  loadingCategories.value = true
  try {
    const response = await fetch('/api/admin/media/categories', { headers: authHeaders() })
    const data = await response.json().catch(() => null)
    categories.value = response.ok ? (data?.categories || []) : []
  } catch {
    categories.value = []
  } finally {
    loadingCategories.value = false
  }
}

async function loadFirst() {
  loading.value = true
  error.value = ''
  selectedId.value = null
  try {
    const { media, hasMore: more } = await fetchMedia(PAGE_SIZE, 0)
    items.value = media
    offset.value = media.length
    hasMore.value = more
  } catch (exc) {
    error.value = String(exc.message || exc)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  try {
    const { media, hasMore: more } = await fetchMedia(PAGE_SIZE, offset.value)
    items.value = [...items.value, ...media]
    offset.value += media.length
    hasMore.value = more
  } catch (exc) {
    error.value = String(exc.message || exc)
  } finally {
    loadingMore.value = false
  }
}

function onShow() {
  if (loadedOnce) return
  loadedOnce = true
  loadFirst()
  loadCategories()
}

function confirm(item) {
  if (!item || !item.storage_path) return
  emit('select', {
    id: item.id,
    name: item.original_name,
    storage_path: item.storage_path,
    mime_type: item.mime_type,
    url: storageUrl(item.storage_path)
  })
  open.value = false
}
</script>

<style scoped>
.media-picker-card {
  width: min(900px, 94vw);
  max-width: 900px;
}

.media-picker-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 4px;
}

.media-picker-title {
  font-size: 18px;
  font-weight: 800;
}

.media-picker-filters {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px;
  padding-top: 4px;
}

.media-picker-body {
  max-height: 58vh;
  min-height: 220px;
  overflow-y: auto;
}

.media-picker-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 16px;
  color: #6b7280;
}

.media-picker-state--error {
  color: #c62828;
}

.media-picker-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.media-picker-item {
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  padding: 8px;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.media-picker-item:hover {
  border-color: #b9c0c8;
}

.media-picker-item--selected {
  border-color: var(--q-primary);
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.06);
}

.media-picker-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 7px;
  background: #f3f5f6;
}

.media-picker-thumb img,
.media-picker-thumb video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.media-picker-thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #9aa1a9;
  font-size: 12px;
}

.media-picker-item-name {
  margin-top: 7px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

.media-picker-item-category {
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #6b7280;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.media-picker-more {
  display: flex;
  justify-content: center;
  padding-top: 12px;
}

@media (max-width: 700px) {
  .media-picker-filters {
    grid-template-columns: 1fr;
  }

  .media-picker-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
