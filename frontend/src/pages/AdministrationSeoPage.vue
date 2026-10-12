<template>
  <q-page class="administration-seo">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>SEO</h1>
        <p>
          Заголовки, описания и ключевые слова для поисковых систем. Значения
          применяются на публичных страницах сайта.
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

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <div v-else>
      <div v-if="error" class="error-text">{{ error }}</div>
      <div v-if="notice" class="notice-text">{{ notice }}</div>

      <!-- ============ ОБЩИЕ ============ -->
      <section class="section-card">
        <div class="section-title">Общие настройки</div>

        <div class="form-grid">
          <div class="field">
            <label>Название сайта</label>
            <q-input v-model="form.site_name" dense outlined />
          </div>

          <div class="field">
            <label>Адрес сайта (домен)</label>
            <q-input
              v-model="form.site_url"
              dense
              outlined
              placeholder="https://albion.ru"
              hint="Нужен для canonical и sitemap.xml"
            />
          </div>

          <div class="field field-wide">
            <label>
              Заголовок по умолчанию
              <span class="counter">{{
                (form.default_title || '').length
              }}</span>
            </label>
            <q-input v-model="form.default_title" dense outlined />
          </div>

          <div class="field field-wide">
            <label>
              Описание по умолчанию
              <span class="counter">{{
                (form.default_description || '').length
              }}</span>
            </label>
            <q-input
              v-model="form.default_description"
              dense
              outlined
              autogrow
              type="textarea"
              hint="Оптимально 120–160 символов"
            />
          </div>

          <div class="field field-wide">
            <label>
              Ключевые слова по умолчанию
              <span class="counter">{{
                (form.default_keywords || '').length
              }}</span>
            </label>
            <q-input
              v-model="form.default_keywords"
              dense
              outlined
              autogrow
              type="textarea"
              hint="Через запятую"
            />
          </div>

          <div class="field field-wide">
            <label>Картинка для соцсетей (og:image)</label>
            <q-input
              v-model="form.og_image"
              dense
              outlined
              placeholder="/storage/..."
            />
          </div>
        </div>
      </section>

      <!-- ============ СТРАНИЦЫ ============ -->
      <section class="section-card">
        <div class="section-title">Страницы сайта</div>

        <div v-for="page in pages" :key="page.path" class="page-card">
          <div class="page-card-head">
            <span class="page-label">{{ page.label }}</span>
            <code class="page-path">{{ page.path }}</code>
            <span v-if="!page.index" class="page-badge"> не в sitemap </span>
          </div>

          <div class="form-grid">
            <div class="field field-wide">
              <label>
                Заголовок
                <span class="counter">{{
                  ((form.pages[page.path] || {}).title || '').length
                }}</span>
              </label>
              <q-input
                v-model="form.pages[page.path].title"
                dense
                outlined
                :placeholder="form.default_title"
              />
            </div>

            <div class="field field-wide">
              <label>
                Описание
                <span class="counter">{{
                  ((form.pages[page.path] || {}).description || '').length
                }}</span>
              </label>
              <q-input
                v-model="form.pages[page.path].description"
                dense
                outlined
                autogrow
                type="textarea"
                :placeholder="form.default_description"
              />
            </div>

            <div class="field field-wide">
              <label>
                Ключевые слова
                <span class="counter">{{
                  ((form.pages[page.path] || {}).keywords || '').length
                }}</span>
              </label>
              <q-input
                v-model="form.pages[page.path].keywords"
                dense
                outlined
                autogrow
                type="textarea"
                :placeholder="form.default_keywords"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- ============ СЛУЖЕБНЫЕ ФАЙЛЫ ============ -->
      <section class="section-card">
        <div class="section-title">Служебные файлы для поисковиков</div>

        <p class="hint-text">
          Генерируются автоматически из этих настроек. Домен для ссылок берётся
          из поля «Адрес сайта».
        </p>

        <div class="links-row">
          <a class="link-item" href="/robots.txt" target="_blank">
            /robots.txt
          </a>
          <a class="link-item" href="/sitemap.xml" target="_blank">
            /sitemap.xml
          </a>
        </div>
      </section>

      <div class="actions-row">
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Сохранить"
          :loading="saving"
          @click="save"
        />

        <q-btn
          flat
          no-caps
          color="grey-8"
          label="Сбросить к значениям по умолчанию"
          :loading="resetting"
          @click="reset"
        />
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { adminAuthHeaders } from '../services/adminMedia'

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const resetting = ref(false)
const error = ref('')
const notice = ref('')
const pages = ref([])

const form = reactive({
  site_name: '',
  site_url: '',
  default_title: '',
  default_description: '',
  default_keywords: '',
  og_image: '',
  pages: {}
})

function fill(current, pageList) {
  form.site_name = current.site_name || ''
  form.site_url = current.site_url || ''
  form.default_title = current.default_title || ''
  form.default_description = current.default_description || ''
  form.default_keywords = current.default_keywords || ''
  form.og_image = current.og_image || ''

  const source = current.pages || {}
  const next = {}

  for (const page of pageList || []) {
    const values = source[page.path] || {}
    next[page.path] = {
      title: values.title || '',
      description: values.description || '',
      keywords: values.keywords || ''
    }
  }

  form.pages = next
  pages.value = pageList || []
}

async function load() {
  loading.value = true
  error.value = ''

  try {
    const response = await fetch('/api/admin/seo', {
      headers: adminAuthHeaders()
    })

    if (response.status === 401) {
      error.value = 'Сессия истекла. Войдите заново.'
      return
    }

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data?.detail || 'Не удалось загрузить настройки')
    }

    fill(data.current || {}, data.pages || [])
  } catch (exc) {
    error.value = String(exc?.message || exc)
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''

  try {
    const response = await fetch('/api/admin/seo', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...adminAuthHeaders() },
      body: JSON.stringify({ ...form })
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error(data?.detail || 'Не удалось сохранить')
    }

    fill(data.current || {}, data.pages || [])
    notice.value = 'Сохранено.'
  } catch (exc) {
    error.value = String(exc?.message || exc)
  } finally {
    saving.value = false
  }
}

async function reset() {
  resetting.value = true
  error.value = ''
  notice.value = ''

  try {
    const response = await fetch('/api/admin/seo/reset', {
      method: 'POST',
      headers: adminAuthHeaders()
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error(data?.detail || 'Не удалось сбросить')
    }

    fill(data.current || {}, data.pages || [])
    notice.value = 'Вернули значения по умолчанию.'
  } catch (exc) {
    error.value = String(exc?.message || exc)
  } finally {
    resetting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.administration-seo {
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
  color: #8b8b8b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.page-header h1 {
  margin: 6px 0 6px;
  font-size: 28px;
  font-weight: 800;
}

.page-header p {
  margin: 0;
  max-width: 640px;
  color: #6b6b6b;
  font-size: 14px;
  line-height: 1.5;
}

.loading-block {
  display: flex;
  justify-content: center;
  padding: 40px;
}

.error-text,
.notice-text {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
}

.error-text {
  border: 1px solid #e57373;
  background: #fdecea;
  color: #c62828;
}

.notice-text {
  border: 1px solid #a5d6a7;
  background: #e8f5e9;
  color: #2e7d32;
}

.section-card {
  margin-bottom: 18px;
  padding: 20px;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  background: #fff;
}

.section-title {
  margin-bottom: 14px;
  color: #8b8b8b;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.field-wide {
  grid-column: 1 / -1;
}

.field label {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
  color: #444;
  font-size: 13px;
  font-weight: 600;
}

.counter {
  color: #9aa0a6;
  font-size: 11px;
  font-weight: 600;
}

.page-card {
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid #eef0f3;
  border-radius: 12px;
  background: #fafbfc;
}

.page-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.page-label {
  font-weight: 700;
  color: #333;
}

.page-path {
  color: #7b8794;
  font-size: 12px;
}

.page-badge {
  padding: 1px 8px;
  border-radius: 999px;
  background: #eceff1;
  color: #78909c;
  font-size: 11px;
}

.hint-text {
  margin: 0 0 10px;
  color: #6b6b6b;
  font-size: 13px;
}

.links-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.link-item {
  padding: 6px 12px;
  border: 1px solid #cfe0f5;
  border-radius: 999px;
  background: #eef5fd;
  color: #1c5fa8;
  font-size: 13px;
  text-decoration: none;
}

.actions-row {
  display: flex;
  gap: 12px;
  align-items: center;
  padding-bottom: 32px;
}

@media (max-width: 800px) {
  .administration-seo {
    padding: 18px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
