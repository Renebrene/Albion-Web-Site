<template>
  <q-page class="info-page">
    <div class="info-shell">
      <header class="info-head">
        <div class="info-kicker">ALBION</div>
        <h1>Информация</h1>
      </header>

      <nav v-if="tabs.length" class="info-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          class="info-tab"
          :class="{ 'is-active': activeTab && activeTab.id === tab.id }"
          :aria-selected="activeTab && activeTab.id === tab.id"
          @click="selectTab(tab)"
        >
          {{ tab.title }}
        </button>
      </nav>

      <div v-if="loading" class="info-state">
        <q-spinner size="28px" />
      </div>

      <div v-else-if="!tabs.length" class="info-state">
        Раздел находится в разработке.
      </div>

      <section v-else class="info-body" role="tabpanel">
        <!-- Города и районы: слева список, справа описание из базы -->
        <div v-if="activeTab.kind === 'geo'" class="geo-layout">
          <aside class="geo-list" aria-label="Города и районы">
            <button
              v-for="location in geoLocations"
              :key="location.id"
              type="button"
              class="geo-item"
              :class="{
                'is-active':
                  selectedLocation && selectedLocation.id === location.id
              }"
              @click="selectedLocation = location"
            >
              {{ location.label }}
            </button>

            <div v-if="!geoLocations.length" class="geo-empty">
              Городов и районов пока нет.
            </div>
          </aside>

          <!-- Карточка направления — как открытая карточка колоды на главной -->
          <article class="geo-card">
            <template v-if="selectedLocation">
              <div
                class="geo-card-photo"
                :style="
                  selectedLocation.cover
                    ? {
                        backgroundImage: `url('${selectedLocation.cover.url}')`
                      }
                    : undefined
                "
              >
                <span v-if="!selectedLocation.cover" class="geo-card-nophoto">
                  {{ selectedLocation.label }}
                </span>
              </div>

              <div class="geo-card-body">
                <h2 class="geo-card-title">{{ selectedLocation.label }}</h2>

                <div
                  v-if="selectedLocation.description"
                  class="geo-card-text"
                  >{{ selectedLocation.description }}</div
                >
                <p v-else class="geo-card-text geo-card-text--muted">
                  Описание этого направления скоро появится.
                </p>

                <div
                  v-if="
                    selectedLocation.stats &&
                    selectedLocation.stats.constructions
                  "
                  class="geo-card-stats"
                >
                  <div class="geo-card-stats-total">
                    <b>{{ selectedLocation.stats.constructions }}</b>
                    <span>конструкций в направлении</span>
                  </div>
                  <div class="geo-card-formats">
                    <span
                      v-for="f in selectedLocation.stats.formats"
                      :key="f.name"
                      class="geo-card-format"
                      ><b>{{ f.count }}</b> {{ f.name }}</span
                    >
                  </div>
                </div>

                <a
                  v-if="selectedLocation.map_href || selectedLocation.href"
                  class="geo-card-mapbtn"
                  :href="selectedLocation.map_href || selectedLocation.href"
                  >Перейти на интерактивную карту</a
                >

                <div v-if="selectedLocation.cover" class="geo-card-credit">
                  <span class="geo-card-credit-name">
                    {{ selectedLocation.cover.attraction_title }}
                  </span>
                  <span v-if="selectedLocation.cover.source_name">
                    · фото: {{ selectedLocation.cover.source_name }}
                  </span>
                  <a
                    v-if="selectedLocation.cover.source_url"
                    :href="selectedLocation.cover.source_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    >источник</a
                  >
                  <span v-if="selectedLocation.cover.license">
                    · {{ selectedLocation.cover.license }}
                  </span>
                </div>
              </div>
            </template>

            <p v-else class="geo-card-text geo-card-text--muted geo-card-empty">
              Выберите город или район в списке слева.
            </p>
          </article>
        </div>

        <!-- Обычная закладка: текст из админки либо заглушка -->
        <div v-else class="text-layout">
          <p v-if="tabContent" class="text-content">{{ tabContent }}</p>
          <div v-else class="info-state info-state--inline">
            Раздел находится в разработке.
          </div>
        </div>
      </section>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = ref([])
const activeTab = ref(null)
const geo = ref({ locations: [], attractions: [] })
const selectedLocation = ref(null)
const loading = ref(true)

const geoLocations = computed(() => geo.value.locations || [])

const tabContent = computed(() => {
  const content = activeTab.value?.content || ''
  return content.trim()
})

/* По умолчанию открывается Ростов-на-Дону (он же первый в списке). */
function defaultGeoLocation() {
  const list = geoLocations.value

  if (!list.length) {
    return null
  }

  const rostov = list.find(location =>
    String(location.label || '')
      .trim()
      .toLowerCase()
      .startsWith('ростов-на-дону')
  )

  return rostov || list[0]
}

function syncGeoSelection() {
  selectedLocation.value =
    activeTab.value?.kind === 'geo' ? defaultGeoLocation() : null
}

function selectTab(tab) {
  activeTab.value = tab
  syncGeoSelection()
}

/* Открыть закладку по ссылке вида /informaciya?tab=<id|название>. */
function applyQueryTab() {
  const wanted = String(route.query.tab || '')
    .trim()
    .toLowerCase()

  if (!wanted || !tabs.value.length) return

  const match =
    tabs.value.find(tab => String(tab.id) === wanted) ||
    tabs.value.find(
      tab =>
        String(tab.title || '')
          .trim()
          .toLowerCase() === wanted
    ) ||
    tabs.value.find(tab =>
      String(tab.title || '')
        .trim()
        .toLowerCase()
        .includes(wanted)
    )

  if (match) {
    activeTab.value = match
    syncGeoSelection()
  }
}

async function load() {
  loading.value = true

  try {
    const response = await fetch('/api/info')

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const data = await response.json()

    tabs.value = Array.isArray(data.tabs) ? data.tabs : []
    geo.value = data.geo || { locations: [], attractions: [] }
    activeTab.value = tabs.value[0] || null
    syncGeoSelection()
    applyQueryTab()
  } catch (exc) {
    console.warn('Не удалось загрузить страницу «Информация»:', exc)
    tabs.value = []
    activeTab.value = null
  } finally {
    loading.value = false
  }
}

watch(() => route.query.tab, applyQueryTab)

onMounted(load)
</script>

<style scoped>
.info-page {
  /* Общая высота панелей: список слева и карточка справа совпадают.
     Считается от доступного места (экран минус шапка/подвал и «шапка»
     страницы), поэтому закладка «Города и районы» влезает без прокрутки. */
  --info-panel-h: clamp(
    280px,
    calc(
      100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px) -
        220px
    ),
    620px
  );

  /* Гасим min-height от Quasar q-page (он проставляет её инлайном) — иначе
     страница всегда выше экрана и появляется прокрутка. */
  min-height: auto !important;

  background: #f3f5f6;
}

.info-shell {
  width: min(1720px, 96%);
  margin: 0 auto;
  padding: 34px 0 44px;
}

.info-head {
  text-align: center;
  margin-bottom: 22px;
}

.info-kicker {
  color: var(--albion-accent);
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1.6px;
}

.info-head h1 {
  margin: 8px 0 0;
  color: #17212b;
  font-size: 30px;
  line-height: 1.05;
  font-weight: 900;
}

/* ---- Закладки ---- */

.info-tabs {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px 26px;
  border-bottom: 1px solid #dfe4e7;
  margin-bottom: 22px;
}

.info-tab {
  position: relative;
  padding: 0 2px 12px;
  border: 0;
  background: transparent;
  color: #5b6873;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.18s ease;
}

.info-tab::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: var(--albion-accent);
  transform: scaleX(0);
  transition: transform 0.18s ease;
}

.info-tab:hover {
  color: #17212b;
}

.info-tab.is-active {
  color: #17212b;
}

.info-tab.is-active::after {
  transform: scaleX(1);
}

/* ---- Состояния ---- */

.info-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #5b6873;
  font-size: 14px;
  text-align: center;
}

.info-state--inline {
  padding: 60px 20px;
}

/* ---- Текстовая закладка ---- */

.text-layout {
  max-width: 820px;
  margin: 0 auto;
}

.text-content {
  margin: 0;
  color: #3a4750;
  font-size: 16px;
  line-height: 1.75;
  white-space: pre-line;
}

/* ---- Города и районы ---- */

.geo-layout {
  display: grid;
  grid-template-columns: minmax(260px, 360px) minmax(0, 1fr);
  gap: 28px;
  align-items: start;
}

.geo-list {
  display: flex;
  flex-direction: column;
  max-height: var(--info-panel-h);
  overflow-y: auto;
  border-top: 1px solid #dfe4e7;
}

.geo-item {
  padding: 11px 14px;
  border: 0;
  border-bottom: 1px solid #e7ecee;
  background: transparent;
  color: #17212b;
  font-size: 13px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.16s ease,
    color 0.16s ease,
    padding 0.16s ease;
}

.geo-item:hover {
  padding-left: 18px;
  background: #f4f6f7;
}

.geo-item.is-active {
  padding-left: 18px;
  background: #fff;
  color: var(--albion-accent);
  box-shadow: inset 3px 0 0 var(--albion-accent);
}

.geo-empty {
  padding: 16px;
  color: #89949b;
  font-size: 13px;
}

/* Карточка направления — как открытая карточка колоды на главной. */

.geo-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  height: var(--info-panel-h);
  border-radius: 18px;
  overflow: hidden;
  background: #182127;
  color: #fff;
  text-align: left;
  box-shadow: 0 30px 70px -36px rgba(0, 0, 0, 0.6);
}

.geo-card-photo {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  background: #0e1519 center/cover no-repeat;
}

.geo-card-nophoto {
  padding: 18px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 13px;
  text-align: center;
}

.geo-card-body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 26px 30px 22px;
}

.geo-card-title {
  flex: 0 0 auto;
  margin: 0 0 10px;
  color: #fff;
  font-size: clamp(20px, 2vw, 28px);
  line-height: 1.08;
  font-weight: 900;
}

/* Текст занимает свободное место; при нехватке — прокручивается,
   а блок статистики и кнопка остаются на месте. */
.geo-card-text {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  color: rgba(255, 255, 255, 0.85);
  font-size: 13.5px;
  line-height: 1.6;
  white-space: pre-line;
}

.geo-card-text--muted {
  color: rgba(255, 255, 255, 0.55);
}

.geo-card-empty {
  grid-column: 1 / -1;
  align-self: center;
  margin: 0;
  padding: 48px 24px;
  text-align: center;
}

.geo-card-stats {
  flex: 0 0 auto;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
}

.geo-card-stats-total {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.geo-card-stats-total b {
  font-size: 19px;
  font-weight: 900;
  line-height: 1;
}

.geo-card-stats-total span {
  color: rgba(255, 255, 255, 0.6);
  font-size: 11px;
}

.geo-card-formats {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 12px;
  margin-top: 6px;
}

.geo-card-format {
  color: rgba(255, 255, 255, 0.8);
  font-size: 11px;
}

.geo-card-format b {
  font-weight: 800;
}

.geo-card-mapbtn {
  flex: 0 0 auto;
  align-self: flex-start;
  margin-top: 12px;
  padding: 9px 16px;
  border-radius: 999px;
  background: var(--albion-accent, #ff4d3d);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  text-decoration: none;
  transition: filter 0.15s ease;
}

.geo-card-mapbtn:hover {
  filter: brightness(1.08);
}

.geo-card-credit {
  flex: 0 0 auto;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.5);
  font-size: 10px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.geo-card-credit-name {
  color: rgba(255, 255, 255, 0.72);
  font-weight: 700;
}

.geo-card-credit a {
  margin: 0 4px;
  color: rgba(255, 255, 255, 0.75);
}

@media (max-width: 820px) {
  .info-shell {
    padding: 36px 0 60px;
  }

  .info-tabs {
    gap: 4px 20px;
  }

  .info-tab {
    font-size: 11px;
  }

  .geo-layout {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .geo-list {
    max-height: 300px;
  }

  .geo-card {
    grid-template-columns: 1fr;
    height: auto;
  }

  .geo-card-photo {
    min-height: 220px;
  }

  .geo-card-body {
    padding: 24px 20px;
  }

  /* На мобильном карточка растёт по контенту — прокрутка текста не нужна. */
  .geo-card-text {
    flex: none;
    overflow: visible;
  }
}
</style>
