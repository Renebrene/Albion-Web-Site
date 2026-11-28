<template>
  <q-page class="administration-info">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Информация</h1>
        <p>Закладки страницы «Информация» (адрес /informaciya).</p>
      </div>

      <div class="header-actions">
        <q-btn
          unelevated
          color="primary"
          no-caps
          label="Сохранить"
          :loading="saving"
          @click="save"
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

    <div v-if="error" class="error-text">{{ error }}</div>
    <div v-if="saved" class="ok-text">Сохранено.</div>

    <div class="toolbar">
      <q-btn
        color="primary"
        no-caps
        icon="add"
        label="Добавить закладку"
        @click="addTab"
      />
      <span class="hint">
        Порядок закладок — сверху вниз. Закладка «Города и районы» берёт города,
        районы и описания из раздела «Главная страница».
      </span>
    </div>

    <div v-if="loading" class="loading-row">
      <q-spinner size="28px" />
    </div>

    <template v-else>
      <section v-for="(tab, index) in tabs" :key="tab._key" class="tab-card">
        <div class="tab-head">
          <span class="tab-order">#{{ index + 1 }}</span>

          <span
            class="badge"
            :class="tab.is_active ? 'badge-on' : 'badge-off'"
            >{{ tab.is_active ? 'видна' : 'скрыта' }}</span
          >

          <span class="tab-head-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveTab(index, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="index === tabs.length - 1"
              @click="moveTab(index, 1)"
            />
            <q-btn
              flat
              dense
              color="negative"
              no-caps
              label="Удалить"
              @click="removeTab(index)"
            />
          </span>
        </div>

        <div class="grid">
          <label class="field">
            <span>Название закладки</span>
            <q-input
              v-model="tab.title"
              dense
              outlined
              placeholder="НАЗВАНИЕ"
            />
          </label>

          <label class="field">
            <span>Тип содержимого</span>
            <q-select
              v-model="tab.kind"
              :options="KIND_OPTIONS"
              dense
              outlined
              emit-value
              map-options
            />
          </label>

          <label class="field field--toggle">
            <span>Показывать</span>
            <q-toggle v-model="tab.is_active" />
          </label>
        </div>

        <label v-if="tab.kind === 'text'" class="field field--full">
          <span>Текст закладки (пусто — «Раздел находится в разработке»)</span>
          <q-input
            v-model="tab.content"
            dense
            outlined
            type="textarea"
            autogrow
          />
        </label>

        <div v-else-if="tab.kind === 'geo'" class="geo-note">
          Города, районы и описания редактируются в разделе «Главная страница» →
          «Города, районы и достопримечательности».
        </div>

        <div
          v-else-if="tab.kind === 'traffic-light'"
          class="traffic-light-editor"
        >
          <!-- Изображение светофора -->
          <div class="tl-field">
            <label>Изображение светофора</label>
            <div class="tl-image-upload">
              <div v-if="tab.tlData.image_url" class="tl-image-preview">
                <img :src="tab.tlData.image_url" alt="Светофор" />
                <q-btn
                  flat
                  round
                  dense
                  icon="delete"
                  color="negative"
                  @click="tab.tlData.image_url = null"
                />
              </div>
              <div v-else class="tl-image-upload-btn">
                <input
                  type="file"
                  accept="image/*"
                  class="tl-file-input"
                  @change="onImageUpload($event, tab)"
                />
                <q-btn
                  unelevated
                  color="primary"
                  dense
                  label="Загрузить изображение"
                />
              </div>
            </div>
          </div>

          <!--
            Кастомный блок вместо картинки светофора: можно вставить
            HTML-код (картинка, видео, SVG, iframe) — он заменит блок
            изображения на публичной странице.
          -->
          <div class="tl-field tl-field--full">
            <label>
              HTML-код блока (заменяет изображение светофора; если заполнено —
              показывается вместо картинки)
            </label>
            <q-input
              v-model="tab.tlData.custom_html"
              dense
              outlined
              type="textarea"
              autogrow
              rows="4"
              class="tl-html-input"
              placeholder='&lt;div style="..."&gt;...&lt;/div&gt;'
            />
            <div class="tl-html-hint">
              Пример:
              <code
                >&lt;img src=&quot;/storage/...&quot;
                alt=&quot;Светофор&quot;&gt;</code
              >
              или подключение отдельного Vue-элемента через HTML-разметку.
            </div>
          </div>

          <!-- Текст контента -->
          <div class="tl-field tl-field--full">
            <label
              >Текст (объединённый, простым текстом; переносы строк сохраняются;
              переключения годов нет)</label
            >
            <q-input
              v-model="tab.tlData.text"
              dense
              outlined
              type="textarea"
              autogrow
              rows="12"
              placeholder="Заказчик: ДАД и ОДД г. Ростова-на-Дону&#10;2012. ООО «ПКФ Альбион». Установка светофорных объектов — 11 шт. Адреса: …"
            />
          </div>

          <!-- Фотогалерея -->
          <div class="tl-field tl-field--full">
            <div class="tl-photo-header">
              <label>Фотографии (галерея внизу страницы)</label>
              <div class="tl-photo-actions">
                <q-btn
                  flat
                  dense
                  no-caps
                  icon="add"
                  label="Добавить фото"
                  @click="addPhoto(tab)"
                />
              </div>
            </div>

            <div class="tl-photo-list">
              <div
                v-for="(photo, photoIndex) in tab.tlData.photos"
                :key="photoIndex"
                class="tl-photo-item"
              >
                <div class="tl-photo-preview">
                  <img :src="photo.url" :alt="photo.label || 'Фото'" />
                  <q-btn
                    flat
                    round
                    dense
                    icon="delete"
                    color="negative"
                    @click="removePhoto(tab, photoIndex)"
                  />
                </div>

                <q-input
                  v-model="photo.label"
                  dense
                  outlined
                  label="Подпись"
                  class="tl-photo-label"
                />

                <q-input
                  v-model="photo.url"
                  dense
                  outlined
                  label="URL изображения"
                  class="tl-photo-url"
                />
              </div>

              <div v-if="!tab.tlData.photos.length" class="tl-photo-empty">
                Фотографий пока нет. Добавьте их через кнопку «Добавить фото».
              </div>
            </div>
          </div>
        </div>
      </section>

      <div v-if="!tabs.length" class="empty-text">
        Закладок нет. Добавьте первую.
      </div>
    </template>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { adminFetch, adminRequest as request } from '../services/adminApi'

const router = useRouter()

const KIND_OPTIONS = [
  { label: 'Текст', value: 'text' },
  { label: 'Города и районы (из базы)', value: 'geo' },
  { label: 'Светофорные объекты', value: 'traffic-light' }
]

const tabs = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const saved = ref(false)

let keyCounter = 0

function toEditorTab(tab) {
  const tlData = {
    image_url: null,
    custom_html: '',
    text: '',
    photos: []
  }

  // Парсим JSON контент для traffic-light.
  if (tab.kind === 'traffic-light' && tab.content) {
    try {
      const parsed = JSON.parse(tab.content)
      if (typeof parsed === 'object' && parsed !== null) {
        tlData.image_url = parsed.image_url || null
        tlData.custom_html = parsed.custom_html || ''
        tlData.text = parsed.text || ''
        tlData.photos = (parsed.photos || []).filter(p => p && p.url)
      }
    } catch (e) {
      // Если не JSON — игнорируем.
    }
  }

  return {
    _key: `tab-${++keyCounter}`,
    id: tab.id || null,
    title: tab.title || '',
    kind: tab.kind || 'text',
    content: tab.content || '',
    is_active: tab.is_active !== false,
    tlData
  }
}

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/info/tabs')
    tabs.value = (data.tabs || []).map(toEditorTab)
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function addTab() {
  tabs.value.push({
    _key: `tab-${++keyCounter}`,
    id: null,
    title: 'НОВАЯ ЗАКЛАДКА',
    kind: 'text',
    content: '',
    is_active: true,
    tlData: { image_url: null, custom_html: '', text: '', photos: [] }
  })
}

function moveTab(index, delta) {
  const target = index + delta
  if (target < 0 || target >= tabs.value.length) return

  const list = tabs.value
  const tmp = list[index]
  list[index] = list[target]
  list[target] = tmp
}

function removeTab(index) {
  tabs.value.splice(index, 1)
}

/* ---- Загрузка изображения ---- */

async function onImageUpload(event, tab) {
  const file = event.target.files[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)
  formData.append('original_name', file.name)

  try {
    const response = await adminFetch('/api/admin/media', {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('Не удалось загрузить изображение')
    }

    const data = await response.json()
    const media = data?.media || {}

    // Берём card-вариант или оригинал.
    const variant = media.variants?.find(v => v.variant === 'card')
    tab.tlData.image_url = variant
      ? `/storage/${variant.storage_path}`
      : `/storage/${media.storage_path}`
  } catch (exc) {
    error.value = String(exc)
  }

  event.target.value = ''
}

/* ---- Управление фотографиями ---- */

function addPhoto(tab) {
  tab.tlData.photos.push({
    url: '',
    label: ''
  })
}

function removePhoto(tab, index) {
  tab.tlData.photos.splice(index, 1)
}

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''

  try {
    const payload = {
      tabs: tabs.value.map((tab, index) => {
        const result = {
          id: tab.id || null,
          title: tab.title,
          kind: tab.kind,
          is_active: tab.is_active,
          sort_order: (index + 1) * 10
        }

        if (tab.kind === 'text') {
          result.content = tab.content
        } else if (tab.kind === 'traffic-light') {
          const photos = tab.tlData.photos
            .filter(p => p.url)
            .map(p => ({
              url: p.url,
              label: p.label || ''
            }))

          // Собираем JSON контент.
          const content = {
            image_url: tab.tlData.image_url || '',
            custom_html: tab.tlData.custom_html || '',
            text: tab.tlData.text || '',
            photos
          }
          result.content = JSON.stringify(content, null, 2)

          // Дублируем полями — сервер пересобирает content из них.
          result.image_url = tab.tlData.image_url
          result.custom_html = tab.tlData.custom_html
          result.text = tab.tlData.text
          result.photos = photos
        } else {
          result.content = ''
        }

        return result
      })
    }

    const data = await request('/api/admin/info/tabs', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    tabs.value = (data.tabs || []).map(toEditorTab)
    saved.value = true
    setTimeout(() => {
      saved.value = false
    }, 2500)
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.administration-info {
  max-width: 1000px;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.hint {
  color: #8b8b8b;
  font-size: 12px;
}

.loading-row {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.tab-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 18px 20px;
  margin-bottom: 16px;
}

.tab-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.tab-order {
  color: #a2adb4;
  font-size: 12px;
  font-weight: 800;
}

.tab-head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.badge-on {
  background: #e7f5ea;
  color: #2e7d32;
}

.badge-off {
  background: #f0f1f3;
  color: #8b8b8b;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1.4fr) auto;
  gap: 14px;
  align-items: end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > span {
  color: #6b7680;
  font-size: 12px;
  font-weight: 700;
}

.field--toggle {
  align-items: flex-start;
}

.field--full {
  margin-top: 14px;
}

.geo-note {
  margin-top: 14px;
  padding: 12px 14px;
  background: #f4f6f7;
  border-radius: 10px;
  color: #6b7680;
  font-size: 13px;
}

.empty-text {
  color: #8b8b8b;
  padding: 16px;
}

/* ---- Traffic-light редактор ---- */

.traffic-light-editor {
  margin-top: 14px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e4e6ea;
}

.tl-field {
  margin-bottom: 16px;
}

.tl-field > label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #6b7680;
  margin-bottom: 6px;
}

.tl-field--full {
  margin-top: 14px;
}

.tl-image-upload {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.tl-image-preview {
  position: relative;
  width: 150px;
  height: 200px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #dfe4e7;
}

.tl-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #fff;
}

.tl-image-preview .q-btn {
  position: absolute;
  top: 4px;
  right: 4px;
}

.tl-image-upload-btn {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tl-html-input :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}

.tl-html-hint {
  margin-top: 6px;
  color: #8b8b8b;
  font-size: 11px;
  line-height: 1.5;
}

.tl-html-hint code {
  padding: 1px 4px;
  border-radius: 4px;
  background: #eef1f3;
  color: #455a64;
  font-size: 11px;
}

.tl-file-input {
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.tl-photo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.tl-photo-header label {
  margin: 0;
}

.tl-photo-actions {
  display: flex;
  gap: 4px;
}

.tl-photo-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tl-photo-item {
  display: grid;
  grid-template-columns: 120px 1fr 1fr;
  gap: 10px;
  align-items: start;
  padding: 10px;
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 8px;
}

.tl-photo-preview {
  position: relative;
  width: 120px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  background: #f3f5f6;
}

.tl-photo-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.tl-photo-preview .q-btn {
  position: absolute;
  top: 2px;
  right: 2px;
}

.tl-photo-label,
.tl-photo-url {
  margin-top: 0;
}

.tl-photo-empty {
  color: #89949b;
  font-size: 13px;
  padding: 16px;
  text-align: center;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #dfe4e7;
}

@media (max-width: 760px) {
  .administration-info {
    padding: 20px;
  }

  .page-header {
    flex-direction: column;
  }

  .grid {
    grid-template-columns: 1fr;
  }

  .tl-photo-item {
    grid-template-columns: 1fr;
  }

  .tl-photo-preview {
    width: 100%;
    height: 150px;
  }
}
</style>
