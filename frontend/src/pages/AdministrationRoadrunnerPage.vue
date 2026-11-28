<template>
  <q-page class="admin-roadrunner">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>ROADRUNNER</h1>
        <p>
          3D-баннер «Светофорные объекты»: код поведения, AI-сценарии,
          погода/пробки и документация — в одном разделе.
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

    <q-tabs
      v-model="tab"
      dense
      no-caps
      align="left"
      class="rr-tabs"
      active-color="primary"
      indicator-color="primary"
      outside-arrows
      mobile-arrows
    >
      <q-tab name="banner" icon="movie" label="Баннер" />
      <q-tab name="camera" icon="videocam" label="Камера и сцена" />
      <q-tab name="weather" icon="cloud" label="Погода" />
      <q-tab name="holidays" icon="park" label="Праздники" />
      <q-tab name="scenarios" icon="auto_awesome" label="Сценарии" />
      <q-tab name="ai-settings" icon="tune" label="Настройки АИ и источников" />
      <q-tab name="code-editor" icon="code" label="AI-редактор кода" />
      <q-tab
        name="docs"
        icon="menu_book"
        label="Документация/апи для агентов"
      />
    </q-tabs>

    <q-separator />

    <div class="rr-panel">
      <AdministrationBannerPage
        v-if="tab === 'banner'"
        embedded
        view="banner"
      />

      <AdministrationBannerPage
        v-else-if="['camera', 'weather', 'holidays'].includes(tab)"
        embedded
        view="projection"
        :active-projection-tab="tab"
        @open-ai-settings="tab = 'ai-settings'"
      />

      <AdministrationScenarioGeneratorPage
        v-else-if="tab === 'scenarios'"
        embedded
      />

      <AdministrationBannerPage
        v-else-if="tab === 'ai-settings'"
        embedded
        view="ai"
      />

      <AdministrationCodeEditorPage
        v-else-if="tab === 'code-editor'"
        embedded
      />

      <AdministrationRoadrunnerDocsPage v-else-if="tab === 'docs'" embedded />
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadRoadrunnerMode } from '../composables/useRoadrunnerMode'
import AdministrationBannerPage from './AdministrationBannerPage.vue'
import AdministrationCodeEditorPage from './AdministrationCodeEditorPage.vue'
import AdministrationRoadrunnerDocsPage from './AdministrationRoadrunnerDocsPage.vue'
import AdministrationScenarioGeneratorPage from './AdministrationScenarioGeneratorPage.vue'

const TABS = [
  'banner',
  'camera',
  'weather',
  'holidays',
  'scenarios',
  'ai-settings',
  'code-editor',
  'docs'
]

const route = useRoute()
const router = useRouter()

function fromQuery(value) {
  return TABS.includes(value) ? value : 'banner'
}

const tab = ref(fromQuery(route.query.tab))

onMounted(loadRoadrunnerMode)

watch(tab, value => {
  if (route.query.tab === value) return
  router.replace({
    path: '/administration/roadrunner',
    query: { ...route.query, tab: value }
  })
})

watch(
  () => route.query.tab,
  value => {
    const next = fromQuery(value)
    if (next !== tab.value) tab.value = next
  }
)
</script>

<style scoped>
.admin-roadrunner {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
}

.eyebrow {
  margin-bottom: 6px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.page-header h1 {
  margin: 0 0 8px;
  font-size: clamp(26px, 3vw, 38px);
  font-weight: 900;
  letter-spacing: 0.04em;
}

.page-header p {
  margin: 0;
  max-width: 780px;
  color: #475569;
  line-height: 1.5;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rr-tabs {
  color: #475569;
}

.rr-panel {
  padding-top: 18px;
}

/*
 * Встроенные страницы сохраняют свои классы и стили, но их собственные
 * q-page-отступы и заголовок в объединённом виде не нужны.
 */
.rr-panel :deep(.admin-banner),
.rr-panel :deep(.admin-scenario-generator),
.rr-panel :deep(.admin-roadrunner-docs) {
  max-width: none;
  margin: 0;
  padding: 0;
}

.rr-panel :deep(.page-header h1),
.rr-panel :deep(.page-header .eyebrow) {
  display: none;
}

@media (max-width: 760px) {
  .admin-roadrunner {
    padding: 18px 14px;
  }

  .page-header {
    flex-direction: column;
  }
}
</style>
