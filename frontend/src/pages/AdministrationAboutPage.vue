<template>
  <q-page class="administration-about">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>О компании</h1>
        <p>Тексты, блоки, статистика и элементы сети страницы «О компании»</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
        <q-btn
          color="primary"
          no-caps
          icon="save"
          label="Сохранить"
          :loading="saving"
          :disable="loading || Boolean(error)"
          @click="saveAll"
        />
      </div>
    </div>

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <div v-else-if="error" class="error-text">{{ error }}</div>

    <div v-else>
      <div v-if="notice" class="notice-text">{{ notice }}</div>

      <!-- ============ СТРАНИЦА (SEO) ============ -->
      <section class="section-card">
        <div class="section-title">Страница и SEO</div>

        <div class="field">
          <label>Заголовок (title)</label>
          <q-input v-model="page.title" outlined dense />
        </div>

        <div class="field">
          <label>SEO title</label>
          <q-input v-model="page.seo_title" outlined dense />
        </div>

        <div class="field">
          <label>SEO description</label>
          <q-input
            v-model="page.seo_description"
            outlined
            dense
            type="textarea"
            autogrow
          />
        </div>

        <div class="field">
          <q-toggle v-model="page.is_published" label="Опубликована" />
        </div>
      </section>

      <!-- ============ БЛОКИ ============ -->
      <section class="section-card">
        <div class="section-title">
          Блоки

          <div class="inline-actions">
            <q-btn
              flat
              no-caps
              color="primary"
              label="Добавить блок"
              @click="addBlock"
            />
          </div>
        </div>

        <div v-if="!blocks.length" class="empty-text">Блоков пока нет.</div>

        <article
          v-for="(block, index) in blocks"
          :key="block.id ?? `new-${index}`"
          class="editor-card"
        >
          <div class="editor-card-head">
            <div class="editor-card-title">
              {{ block.title || block.block_key || 'Новый блок' }}
              <span v-if="block.id === null" class="badge">новый</span>
            </div>
            <div class="inline-actions">
              <q-toggle v-model="block.is_active" dense label="Активен" />
              <q-btn
                v-if="block.id === null"
                flat
                dense
                no-caps
                icon="delete"
                color="negative"
                @click="removeBlock(index)"
              />
            </div>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Ключ блока (block_key)</label>
              <q-input v-model="block.block_key" outlined dense />
            </div>
            <div class="field">
              <label>Тип (block_type)</label>
              <q-input v-model="block.block_type" outlined dense />
            </div>
            <div class="field">
              <label>Eyebrow</label>
              <q-input v-model="block.eyebrow" outlined dense />
            </div>
            <div class="field">
              <label>Заголовок</label>
              <q-input v-model="block.title" outlined dense />
            </div>
            <div class="field">
              <label>Подзаголовок</label>
              <q-input v-model="block.subtitle" outlined dense />
            </div>
            <div class="field">
              <label>Порядок</label>
              <q-input
                v-model.number="block.sort_order"
                outlined
                dense
                type="number"
              />
            </div>
          </div>

          <div class="field">
            <label>Текст (body)</label>
            <q-input
              v-model="block.body"
              outlined
              dense
              type="textarea"
              autogrow
            />
          </div>

          <div class="field">
            <label>Content (JSON)</label>
            <q-input
              v-model="block.contentText"
              outlined
              dense
              type="textarea"
              autogrow
              class="mono-input"
              placeholder="{}"
            />
          </div>

          <div class="field">
            <label>Фото блока</label>
            <NewsMediaField
              v-model="block.media"
              v-model:cover-id="block.coverId"
              @notify="onMediaNotify"
            />
          </div>
        </article>
      </section>

      <!-- ============ СТАТИСТИКА ============ -->
      <section class="section-card">
        <div class="section-title">
          Статистика

          <div class="inline-actions">
            <q-btn
              flat
              no-caps
              color="primary"
              label="Добавить показатель"
              @click="addStat"
            />
          </div>
        </div>

        <div v-if="!stats.length" class="empty-text">Показателей пока нет.</div>

        <div
          v-for="(stat, index) in stats"
          :key="stat.id ?? `new-${index}`"
          class="row-card"
        >
          <q-input
            v-model="stat.value"
            outlined
            dense
            label="Значение"
            class="row-card-value"
          />
          <q-input v-model="stat.label" outlined dense label="Подпись" />
          <q-input
            v-model.number="stat.sort_order"
            outlined
            dense
            type="number"
            label="Порядок"
            class="row-card-order"
          />
          <q-toggle v-model="stat.is_active" dense />
          <q-btn
            v-if="stat.id === null"
            flat
            dense
            no-caps
            icon="delete"
            color="negative"
            @click="stats.splice(index, 1)"
          />
        </div>
      </section>

      <!-- ============ СЕТЬ ============ -->
      <section class="section-card">
        <div class="section-title">
          Сеть

          <div class="inline-actions">
            <q-btn
              flat
              no-caps
              color="primary"
              label="Добавить элемент"
              @click="addNetwork"
            />
          </div>
        </div>

        <div v-if="!network.length" class="empty-text">Элементов пока нет.</div>

        <div
          v-for="(item, index) in network"
          :key="item.id ?? `new-${index}`"
          class="row-card"
        >
          <q-select
            v-model="item.item_type"
            :options="networkTypeOptions"
            emit-value
            map-options
            outlined
            dense
            label="Тип"
            class="row-card-type"
          />
          <q-input v-model="item.title" outlined dense label="Название" />
          <q-input
            v-model.number="item.sort_order"
            outlined
            dense
            type="number"
            label="Порядок"
            class="row-card-order"
          />
          <q-toggle v-model="item.is_active" dense />
          <q-btn
            v-if="item.id === null"
            flat
            dense
            no-caps
            icon="delete"
            color="negative"
            @click="network.splice(index, 1)"
          />
        </div>
      </section>

      <div class="save-row">
        <q-btn
          color="primary"
          no-caps
          icon="save"
          label="Сохранить"
          :loading="saving"
          @click="saveAll"
        />
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import NewsMediaField from '../components/admin/NewsMediaField.vue'

const router = useRouter()

const networkTypeOptions = [
  { label: 'Город', value: 'city' },
  { label: 'Трасса', value: 'highway' }
]

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

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const page = ref({
  title: '',
  seo_title: '',
  seo_description: '',
  is_published: true
})
const blocks = ref([])
const stats = ref([])
const network = ref([])

function blockFromApi(block) {
  const media = Array.isArray(block.media) ? block.media : []
  const cover = media.find(item => item.is_cover)

  return {
    id: block.id,
    block_key: block.block_key || '',
    block_type: block.block_type || '',
    eyebrow: block.eyebrow || '',
    title: block.title || '',
    subtitle: block.subtitle || '',
    body: block.body || '',
    contentText: JSON.stringify(block.content || {}, null, 2),
    sort_order: block.sort_order ?? 0,
    is_active: block.is_active !== false,
    media,
    coverId: cover ? cover.id : (media[0]?.id ?? null)
  }
}

function onMediaNotify(message, type = 'success') {
  if (type === 'error') {
    error.value = message
    notice.value = ''
  } else {
    notice.value = message
    error.value = ''
  }
}

async function loadData() {
  loading.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await request('/api/admin/about')
    page.value = {
      title: result.page.title || '',
      seo_title: result.page.seo_title || '',
      seo_description: result.page.seo_description || '',
      is_published: result.page.is_published !== false
    }
    blocks.value = (result.blocks || []).map(blockFromApi)
    stats.value = (result.stats || []).map(stat => ({
      id: stat.id,
      value: stat.value || '',
      label: stat.label || '',
      sort_order: stat.sort_order ?? 0,
      is_active: stat.is_active !== false
    }))
    network.value = (result.network || []).map(item => ({
      id: item.id,
      item_type: item.item_type || 'city',
      title: item.title || '',
      sort_order: item.sort_order ?? 0,
      is_active: item.is_active !== false
    }))
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function addBlock() {
  const nextOrder = blocks.value.reduce(
    (max, b) => Math.max(max, Number(b.sort_order) || 0),
    0
  ) + 10
  blocks.value.push({
    id: null,
    block_key: '',
    block_type: 'text',
    eyebrow: '',
    title: '',
    subtitle: '',
    body: '',
    contentText: '{}',
    sort_order: nextOrder,
    is_active: true,
    media: [],
    coverId: null
  })
}

function removeBlock(index) {
  blocks.value.splice(index, 1)
}

function addStat() {
  const nextOrder = stats.value.reduce(
    (max, s) => Math.max(max, Number(s.sort_order) || 0),
    0
  ) + 10
  stats.value.push({
    id: null,
    value: '',
    label: '',
    sort_order: nextOrder,
    is_active: true
  })
}

function addNetwork() {
  const nextOrder = network.value.reduce(
    (max, n) => Math.max(max, Number(n.sort_order) || 0),
    0
  ) + 10
  network.value.push({
    id: null,
    item_type: 'city',
    title: '',
    sort_order: nextOrder,
    is_active: true
  })
}

function buildBlockPayload(block) {
  let content
  try {
    const raw = (block.contentText || '').trim()
    content = raw ? JSON.parse(raw) : {}
  } catch (exc) {
    throw new Error(`Блок «${block.title || block.block_key}»: некорректный JSON`)
  }
  if (content === null || typeof content !== 'object' || Array.isArray(content)) {
    throw new Error(`Блок «${block.title || block.block_key}»: content должен быть объектом`)
  }

  return {
    id: block.id,
    block_key: block.block_key,
    block_type: block.block_type,
    eyebrow: block.eyebrow,
    title: block.title,
    subtitle: block.subtitle,
    body: block.body,
    content,
    sort_order: block.sort_order,
    is_active: block.is_active,
    media_ids: (block.media || []).map(item => item.id),
    cover_media_id: block.coverId ?? null
  }
}

async function saveAll() {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const payload = {
      page: {
        title: page.value.title,
        seo_title: page.value.seo_title,
        seo_description: page.value.seo_description,
        is_published: page.value.is_published
      },
      blocks: blocks.value.map(buildBlockPayload),
      stats: stats.value.map(stat => ({
        id: stat.id,
        value: stat.value,
        label: stat.label,
        sort_order: stat.sort_order,
        is_active: stat.is_active
      })),
      network: network.value.map(item => ({
        id: item.id,
        item_type: item.item_type,
        title: item.title,
        sort_order: item.sort_order,
        is_active: item.is_active
      }))
    }

    await request('/api/admin/about', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    await loadData()
    notice.value = 'Изменения сохранены'
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.administration-about {
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

.notice-text {
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

.inline-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

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

.mono-input :deep(textarea) {
  font-family: monospace;
  font-size: 12px;
}

/* карточки блоков */
.editor-card {
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 14px;
}

.editor-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
}

.editor-card-title {
  font-weight: 700;
  font-size: 15px;
}

.badge {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 8px;
  border-radius: 8px;
  background: #e3f2fd;
  color: #1565c0;
  font-size: 11px;
  font-weight: 700;
  vertical-align: middle;
}

/* строки статистики / сети */
.row-card {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.row-card-value {
  width: 140px;
  flex: 0 0 140px;
}

.row-card-order {
  width: 110px;
  flex: 0 0 110px;
}

.row-card-type {
  width: 160px;
  flex: 0 0 160px;
}

.row-card .q-input,
.row-card .q-select {
  flex: 1 1 auto;
}

.save-row {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  padding-bottom: 24px;
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .row-card {
    flex-wrap: wrap;
  }
}
</style>
