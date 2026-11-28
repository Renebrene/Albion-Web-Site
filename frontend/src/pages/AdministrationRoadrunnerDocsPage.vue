<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-roadrunner-docs">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>ДОКУМЕНТАЦИЯ ROADRUNNER</h1>
        <p>
          API, сценарии, промпт для AI-агентов и справочник функций программной
          дороги «АЛЬБИОН».
        </p>
      </div>

      <div class="header-actions">
        <q-btn
          color="primary"
          no-caps
          label="Скачать PDF"
          icon="download"
          @click="downloadPdf"
        />
        <q-btn
          v-if="!embedded"
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <div class="content">
      <iframe
        src="/api/roadrunner/api-documentation.html"
        class="docs-iframe"
        title="Roadrunner API документация"
      ></iframe>
    </div>

    <div v-if="error" class="error-text">{{ error }}</div>
  </component>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()
const error = ref('')

async function downloadPdf() {
  try {
    const response = await fetch('/api/roadrunner/api-documentation.pdf')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'roadrunner-api.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (exc) {
    error.value = `Не удалось скачать PDF: ${exc}`
  }
}
</script>

<style scoped>
.admin-roadrunner-docs {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
}

.eyebrow {
  margin-bottom: 6px;
  color: #94a3b8;
  font-size: 12px;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0 0 6px;
  font-size: 26px;
}

.page-header p {
  margin: 0;
  color: #64748b;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.content {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.docs-iframe {
  width: 100%;
  height: 80vh;
  border: 0;
  border-radius: 8px;
}

.error-text {
  padding: 10px 14px;
  margin-top: 16px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
}

@media (max-width: 768px) {
  .admin-roadrunner-docs {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .docs-iframe {
    height: 60vh;
  }
}
</style>
