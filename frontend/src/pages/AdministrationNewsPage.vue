<template>
  <q-page class="administration-news">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Новости</h1>
        <p>Публикации и категории новостей</p>
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

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <div v-else-if="error" class="error-text">{{ error }}</div>

    <div v-else>
      <div v-if="message" :class="messageClass">{{ message }}</div>

      <!-- ============ КАТЕГОРИИ ============ -->
      <section class="section-card">
        <div class="section-title">Категории</div>

        <div v-if="!categories.length" class="empty-text">
          Категорий пока нет.
        </div>

        <div v-else class="chips-list">
          <button
            v-for="category in categories"
            :key="category.id"
            type="button"
            class="chip"
            :class="{ 'is-active': isCategorySelected(category) }"
            :title="
              isCategorySelected(category)
                ? 'Снять фильтр'
                : `Показать только «${category.name}»`
            "
            @click="toggleCategory(category)"
          >
            {{ category.name }}
            <span class="chip-slug">{{ category.slug }}</span>
          </button>
        </div>

        <div class="category-form">
          <q-input
            v-model="newCategoryName"
            outlined
            dense
            label="Новая категория"
            @keyup.enter="addCategory"
          />
          <q-btn
            color="primary"
            no-caps
            label="Добавить категорию"
            :loading="saving"
            @click="addCategory"
          />
        </div>
      </section>

      <!-- ============ НОВОСТИ ============ -->
      <section class="section-card">
        <div class="section-title">
          Публикации
          <q-btn
            color="primary"
            no-caps
            label="+ Новость"
            @click="newNews"
          />
        </div>

        <div v-if="!news.length" class="empty-text">
          Новостей пока нет.
        </div>

        <div v-else-if="!visibleNews.length" class="filter-empty">
          В категории «{{ selectedCategoryName }}» публикаций нет.
          <button type="button" class="link-btn" @click="clearCategoryFilter">
            Показать все
          </button>
        </div>

        <div v-if="selectedCategoryId !== null" class="filter-note">
          Фильтр: «{{ selectedCategoryName }}» — {{ visibleNews.length }} из {{ news.length }}
          <button type="button" class="link-btn" @click="clearCategoryFilter">
            Сбросить
          </button>
        </div>

        <article
          v-for="item in visibleNews"
          :key="item.id"
          class="mini-card"
        >
          <div class="mini-card-info">
            <div class="mini-card-title">
              {{ item.title }}
              <span
                class="status-badge"
                :class="item.is_published ? 'is-published' : 'is-draft'"
              >
                {{ item.is_published ? 'опубликовано' : 'черновик' }}
              </span>
              <span v-if="item.is_featured" class="status-badge is-featured">
                на главной
              </span>
            </div>
            <div class="mini-card-meta">
              {{ formatDate(item.published_at) || 'без даты' }}
              <template v-if="item.category">
                <button
                  type="button"
                  class="category-badge"
                  :class="{ 'is-active': item.category.id === selectedCategoryId }"
                  title="Показать только эту категорию"
                  @click="toggleCategory(item.category)"
                >
                  {{ item.category.name }}
                </button>
              </template>
              · /{{ item.slug }}
            </div>
          </div>

          <div class="mini-card-actions">
            <q-btn flat dense no-caps icon="edit" @click="editNews(item)" />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="deleteNews(item)"
            />
          </div>
        </article>
      </section>
    </div>

    <!-- ============ ДИАЛОГ РЕДАКТИРОВАНИЯ ============ -->
    <q-dialog v-model="editOpen" persistent>
      <q-card class="editor-dialog">
        <q-card-section>
          <div class="dialog-title">
            {{ editing.id ? 'Редактирование новости' : 'Новая новость' }}
          </div>
        </q-card-section>

        <q-card-section class="editor-body">
          <div class="field">
            <label>Заголовок</label>
            <q-input v-model="editing.title" outlined dense />
          </div>

          <div class="field">
            <label>Адрес (slug)</label>
            <q-input
              v-model="editing.slug"
              outlined
              dense
              placeholder="оставьте пустым — сгенерируется из заголовка"
            />
          </div>

          <div class="field">
            <label>Категория</label>
            <q-select
              v-model="editing.category_id"
              :options="categoryOptions"
              option-value="id"
              option-label="name"
              emit-value
              map-options
              clearable
              outlined
              dense
            />
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Дата публикации</label>
              <q-input v-model="editing.published_at" type="date" outlined dense />
            </div>

            <div class="field toggles">
              <div class="toggle-row">
                <q-toggle v-model="editing.is_published" label="Опубликовано" />
              </div>
              <div class="toggle-row">
                <q-toggle v-model="editing.is_featured" label="На главной" />
              </div>
            </div>
          </div>

          <div class="field">
            <label>Краткое описание (excerpt)</label>
            <q-input
              v-model="editing.excerpt"
              outlined
              dense
              type="textarea"
              autogrow
            />
          </div>

          <div class="field">
            <label>Текст новости</label>
            <q-input
              v-model="editing.content"
              outlined
              dense
              type="textarea"
              autogrow
              style="min-height: 160px"
            />
          </div>

          <div class="field">
            <label>Медиа (фото, видео, GIF)</label>
            <NewsMediaField
              v-model="editing.media"
              v-model:cover-id="editing.cover_id"
              @notify="notify"
            />
          </div>

          <div class="field">
            <label>SEO заголовок</label>
            <q-input v-model="editing.seo_title" outlined dense />
          </div>

          <div class="field">
            <label>SEO описание</label>
            <q-input
              v-model="editing.seo_description"
              outlined
              dense
              type="textarea"
              autogrow
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
            @click="saveNews"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import NewsMediaField from '../components/admin/NewsMediaField.vue'

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

const news = ref([])
const categories = ref([])

/* Фильтр публикаций по категории: null — показывать все. */
const selectedCategoryId = ref(null)

function categoryIdOf(item) {
  return item?.category?.id ?? null
}

function isCategorySelected(category) {
  return (
    selectedCategoryId.value !== null &&
    category?.id === selectedCategoryId.value
  )
}

/* Клик по категории: включить фильтр либо снять, если уже включён. */
function toggleCategory(category) {
  const id = category?.id ?? null

  selectedCategoryId.value = isCategorySelected(category) ? null : id
}

function clearCategoryFilter() {
  selectedCategoryId.value = null
}

const selectedCategoryName = computed(() => {
  const found = categories.value.find(
    category => category.id === selectedCategoryId.value
  )

  return found ? found.name : ''
})

const visibleNews = computed(() => {
  if (selectedCategoryId.value === null) {
    return news.value
  }

  return news.value.filter(
    item => categoryIdOf(item) === selectedCategoryId.value
  )
})
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')
const messageType = ref('ok')

const editOpen = ref(false)
const editing = ref(emptyNews())
const newCategoryName = ref('')

const categoryOptions = computed(() => categories.value)

const messageClass = computed(() =>
  messageType.value === 'error' ? 'error-text' : 'ok-text'
)

function emptyNews() {
  return {
    id: null,
    title: '',
    slug: '',
    excerpt: '',
    content: '',
    category_id: null,
    published_at: '',
    is_published: false,
    is_featured: false,
    seo_title: '',
    seo_description: '',
    media: [],
    cover_id: null
  }
}

function mapNewsMedia(item) {
  const raw = Array.isArray(item?.media) ? item.media : []
  return raw.map((media) => ({
    id: media.id,
    original_name: media.original_name || '',
    storage_path: media.storage_path || '',
    mime_type: media.mime_type || '',
    preview_path: media.preview_path || null,
    variants: Array.isArray(media.variants) ? media.variants : []
  }))
}

function coverIdOf(item) {
  const raw = Array.isArray(item?.media) ? item.media : []
  const cover = raw.find((media) => media.is_cover)
  if (cover) return cover.id
  return raw.length ? raw[0].id : null
}

function notify(text, type = 'ok') {
  message.value = text
  messageType.value = type
  window.setTimeout(() => {
    if (message.value === text) message.value = ''
  }, 4000)
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('ru-RU')
}

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const result = await request('/api/admin/news')
    news.value = result.news || []
    categories.value = result.categories || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

/* ============================================================
   КАТЕГОРИИ
   ============================================================ */

async function addCategory() {
  const name = newCategoryName.value.trim()
  if (!name) {
    notify('Укажите название категории', 'error')
    return
  }

  saving.value = true
  try {
    await request('/api/admin/news/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    newCategoryName.value = ''
    notify('Категория добавлена')
    await loadData()
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

/* ============================================================
   НОВОСТИ
   ============================================================ */

function newNews() {
  editing.value = emptyNews()
  editOpen.value = true
}

function editNews(item) {
  editing.value = {
    id: item.id,
    title: item.title || '',
    slug: item.slug || '',
    excerpt: item.excerpt || '',
    content: item.content || '',
    category_id: item.category_id,
    published_at: (item.published_at || '').slice(0, 10),
    is_published: !!item.is_published,
    is_featured: !!item.is_featured,
    seo_title: item.seo_title || '',
    seo_description: item.seo_description || '',
    media: mapNewsMedia(item),
    cover_id: coverIdOf(item)
  }
  editOpen.value = true
}

async function saveNews() {
  if (!editing.value.title.trim()) {
    notify('Укажите заголовок новости', 'error')
    return
  }

  saving.value = true
  try {
    const mediaList = Array.isArray(editing.value.media) ? editing.value.media : []
    const mediaIds = mediaList.map((media) => media.id)
    let coverMediaId = editing.value.cover_id
    if (coverMediaId == null || !mediaIds.includes(coverMediaId)) {
      coverMediaId = mediaIds.length ? mediaIds[0] : null
    }

    const payload = {
      title: editing.value.title,
      slug: editing.value.slug || null,
      excerpt: editing.value.excerpt,
      content: editing.value.content,
      category_id: editing.value.category_id,
      published_at: editing.value.published_at || null,
      is_published: editing.value.is_published,
      is_featured: editing.value.is_featured,
      seo_title: editing.value.seo_title,
      seo_description: editing.value.seo_description,
      media_ids: mediaIds,
      cover_media_id: coverMediaId
    }

    if (editing.value.id) {
      await request(`/api/admin/news/${editing.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    } else {
      await request('/api/admin/news', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }

    editOpen.value = false
    notify('Новость сохранена')
    await loadData()
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

async function deleteNews(item) {
  if (!confirm(`Удалить новость «${item.title}»?`)) return
  try {
    await request(`/api/admin/news/${item.id}`, { method: 'DELETE' })
    notify('Новость удалена')
    await loadData()
  } catch (exc) {
    notify(String(exc), 'error')
  }
}

onMounted(loadData)
</script>

<style scoped>
.administration-news {
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

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
}

.ok-text {
  color: #2e7d32;
  background: #eef7ee;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
}

.empty-text {
  color: #777;
  padding: 18px;
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
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

/* категории */
.chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #eef1f5;
  color: #37474f;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 13px;
}

.chip-slug {
  color: #90a4ae;
  font-size: 11px;
}

/* Чип категории работает как фильтр — это кнопка. */
.chip {
  border: 1px solid transparent;
  font-family: inherit;
  cursor: pointer;
  transition: .15s ease;
}

.chip:hover {
  background: #e2e8ef;
}

.chip.is-active {
  background: var(--albion-accent);
  border-color: var(--albion-accent);
  color: #fff;
}

.chip.is-active .chip-slug {
  color: rgba(255, 255, 255, .75);
}

/* Строка «Фильтр: … N из M» и пустой результат фильтра. */
.filter-note,
.filter-empty {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;

  margin-bottom: 12px;

  color: #52606a;
  font-size: 13px;
}

.link-btn {
  padding: 0;
  border: 0;

  background: none;
  color: var(--albion-accent);

  font-family: inherit;
  font-size: inherit;

  cursor: pointer;
  text-decoration: underline;
}

/* Категория в карточке публикации — выделена и кликабельна. */
.category-badge {
  display: inline-block;

  margin: 0 2px;
  padding: 2px 9px;

  border: 1px solid #dbe3ea;
  border-radius: 8px;

  background: #eef3f8;
  color: #39506b;

  font-family: inherit;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .2px;

  cursor: pointer;
  transition: .15s ease;
}

.category-badge:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

.category-badge.is-active {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
}

.category-form {
  display: flex;
  align-items: center;
  gap: 12px;
  max-width: 520px;
}

.category-form .q-input {
  flex: 1;
}

/* карточки */
.mini-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  margin-bottom: 10px;
}

.mini-card-info {
  min-width: 0;
}

.mini-card-title {
  font-weight: 700;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mini-card-meta {
  color: #8b8b8b;
  font-size: 12px;
  word-break: break-word;
}

.status-badge {
  display: inline-block;
  border-radius: 6px;
  padding: 1px 8px;
  font-size: 11px;
  font-weight: 700;
}

.status-badge.is-published {
  background: #e6f4ea;
  color: #2e7d32;
}

.status-badge.is-draft {
  background: #f0f0f0;
  color: #757575;
}

.status-badge.is-featured {
  background: #fff3e0;
  color: #ef6c00;
}

.mini-card-actions {
  display: flex;
  gap: 4px;
}

/* формы */
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.field {
  margin-bottom: 12px;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.toggles {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.toggle-row {
  margin-bottom: 4px;
}

/* диалог */
.editor-dialog {
  min-width: 640px;
  max-width: 96vw;
}

.editor-body {
  max-height: 70vh;
  overflow: auto;
}

.dialog-title {
  font-size: 18px;
  font-weight: 800;
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .editor-dialog {
    min-width: 0;
    width: 96vw;
  }
}
</style>
