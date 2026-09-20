<template>
  <q-page class="media-page">
    <div class="media-container">
      <header class="media-header">
        <div>
          <div class="media-brand">ALBION</div>
          <h1>Медиа</h1>
          <p>Загрузка изображений для сайта</p>
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
            accept=".jpg,.jpeg,.png,.webp,.heic,.heif,.tif,.tiff,.bmp,.psd,.gif,image/*"
            label="Файл изображения"
            hint="JPEG, PNG, WEBP, HEIC, TIFF, BMP, PSD или GIF"
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

            <q-select
              v-model="storageSubdir"
              outlined
              emit-value
              map-options
              label="Раздел хранения"
              :options="storageOptions"
              :disable="uploading"
            />
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
              <strong>
                {{ result.width }} × {{ result.height }}
              </strong>
            </div>

            <div>
              <span class="result-label">Тип</span>
              <strong>{{ result.mime_type }}</strong>
            </div>
          </div>

          <div
            v-if="result.storage_path"
            class="result-path"
          >
            {{ result.storage_path }}
          </div>

          <div
            v-if="result.variants?.length"
            class="variants-section"
          >
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
    </div>
  </q-page>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const file = ref(null)
const alt = ref('')
const title = ref('')
const storageSubdir = ref('news')
const uploading = ref(false)
const error = ref('')
const result = ref(null)
const previewUrl = ref('')
let previewObjectUrl = ''

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

const storageOptions = [
  {
    label: 'Новости',
    value: 'news'
  },
  {
    label: 'О компании',
    value: 'about'
  },
  {
    label: 'Контакты',
    value: 'contacts'
  },
  {
    label: 'Сотрудники',
    value: 'employees'
  },
  {
    label: 'Конструкции',
    value: 'constructions'
  },
  {
    label: 'Прочее',
    value: 'misc'
  }
]

function storageUrl(path) {
  return `/storage/${path}`
}

async function uploadMedia() {
  if (!file.value) {
    return
  }

  const token = sessionStorage.getItem('albion_admin_token')

  if (!token) {
    await router.replace('/administration')
    return
  }

  uploading.value = true
  error.value = ''
  result.value = null

  const formData = new FormData()
  formData.append('file', file.value)
  formData.append('storage_subdir', storageSubdir.value)

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
  } catch {
    error.value = 'Не удалось выполнить запрос к серверу'
  } finally {
    uploading.value = false
  }
}

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
  max-width: 960px;
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
.result-card {
  border-radius: 16px;
  background: #fff;
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

@media (max-width: 600px) {
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

  .result-grid {
    grid-template-columns: 1fr;
  }

  .variant-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
