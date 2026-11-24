<template>
  <q-page class="info-page">
    <div class="info-shell">
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
        <!-- Traffic-light: оглавление + содержимое + фотогалерея -->
        <div
          v-if="activeTab.kind === 'traffic-light'"
          class="traffic-light-layout"
        >
          <div class="tl-layout">
            <!-- Колонка 1: светофор (кастомный HTML / картинка / 3D) -->
            <div class="tl-light">
              <div
                v-if="tlData.custom_html"
                class="tl-custom-html"
                v-html="tlData.custom_html"
              ></div>

              <img
                v-else-if="tlData.image_url"
                :src="tlData.image_url"
                alt="Светофор"
                class="tl-image"
              />

              <div v-else class="tl-image-placeholder">
                <TrafficLight3D
                  :height="280"
                  :auto-cycle="true"
                  :cycle-speed="1"
                />
              </div>
            </div>

            <!-- Колонка 2: оглавление (ОБЩЕЕ + годы) -->
            <nav class="tl-toc" aria-label="Оглавление">
              <button
                v-for="section in tlSections"
                :key="section.key"
                type="button"
                class="tl-toc-item"
                :class="{ 'is-active': selectedTlSection === section.key }"
                :aria-selected="selectedTlSection === section.key"
                @click="selectedTlSection = section.key"
              >
                {{ section.title }}
              </button>
            </nav>

            <!-- Колонка 3: содержимое выбранного пункта -->
            <article class="tl-content" role="tabpanel">
              <template v-if="currentTlSection">
                <div
                  v-for="(desc, i) in currentTlSection.descriptions"
                  :key="`d-${i}`"
                  class="tl-desc"
                >
                  {{ desc }}
                </div>

                <div
                  v-if="currentTlSection.addresses.length"
                  class="tl-addresses"
                >
                  {{ currentTlSection.addresses.join(' · ') }}
                </div>

                <div
                  v-if="
                    !currentTlSection.descriptions.length &&
                    !currentTlSection.addresses.length
                  "
                  class="tl-empty"
                >
                  Информация скоро появится.
                </div>
              </template>
            </article>
          </div>

          <!-- Нижняя часть: фотогалерея -->
          <div class="tl-photo-gallery">
            <button
              v-for="(photo, index) in tlData.photos"
              :key="index"
              type="button"
              class="tl-photo-thumb"
              :aria-label="photo.label || 'Открыть фото'"
              @click="openPhotoViewer(photo, index)"
            >
              <img :src="photo.url" :alt="photo.label || 'Фото светофора'" />
            </button>
            <div v-if="!tlData.photos.length" class="tl-photo-empty">
              Фотографии не добавлены.
            </div>
          </div>
        </div>

        <!-- Города и районы -->
        <div v-else-if="activeTab.kind === 'geo'" class="geo-layout">
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

        <!-- Обычная закладка: текст из админки -->
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
import TrafficLight3D from '@/components/common/TrafficLight3D.vue'
import { usePhotoViewer } from '@/composables/usePhotoViewer'

const route = useRoute()
const { openPhoto, setCurrent } = usePhotoViewer()

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

/* Данные traffic-light: разобраны из JSON в content. */
const tlData = ref({
  image_url: null,
  custom_html: '',
  text: '',
  photos: []
})

/* Выбранный пункт оглавления. По умолчанию — «ОБЩЕЕ». */
const selectedTlSection = ref('general')

/* Строки-описания начинаются с этих слов; остальные — адреса. */
const DESC_PREFIXES = [
  'ооо',
  'установка',
  'замена',
  'работы',
  'альбион',
  'одной',
  'рекламное',
  'автоподъемник',
  'автоподъёмник'
]

function isAddressLine(line) {
  const low = line.trim().toLowerCase()
  if (!low) return false

  return !DESC_PREFIXES.some(prefix => low.startsWith(prefix))
}

/*
 * Разбирает текст на секции: вводная часть «ОБЩЕЕ» и годы.
 * Каждая секция: { key, title, descriptions: string[], addresses: string[] }.
 */
const tlSections = computed(() => {
  const text = tlData.value.text || ''
  if (!text.trim()) return []

  const lines = text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  const sections = []
  let current = {
    key: 'general',
    title: 'ОБЩЕЕ',
    descriptions: [],
    addresses: []
  }

  const flush = () => {
    if (current.descriptions.length || current.addresses.length) {
      sections.push(current)
    }
  }

  for (const line of lines) {
    const yearMatch = line.match(/^(\d{4})$/)

    if (yearMatch) {
      flush()
      current = {
        key: yearMatch[1],
        title: yearMatch[1],
        descriptions: [],
        addresses: []
      }
    } else if (isAddressLine(line)) {
      current.addresses.push(line)
    } else {
      current.descriptions.push(line)
    }
  }

  flush()

  return sections
})

const currentTlSection = computed(
  () =>
    tlSections.value.find(section => section.key === selectedTlSection.value) ||
    tlSections.value[0] ||
    null
)

function openPhotoViewer(photo, index) {
  const photos = tlData.value.photos
  openPhoto({
    images: photos.map(p => ({
      url: p.url,
      label: p.label || 'Фото светофора'
    })),
    title: 'Светофорные объекты'
  })
  // Устанавливаем текущий индекс.
  setCurrent(index)
}

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

function parseTrafficLightContent(contentText) {
  const raw = String(contentText || '').trim()

  if (!raw) {
    tlData.value = {
      image_url: null,
      custom_html: '',
      text: '',
      photos: []
    }
    return
  }

  try {
    const data = JSON.parse(raw)
    if (typeof data === 'object' && data !== null) {
      tlData.value = {
        image_url: data.image_url || null,
        custom_html: data.custom_html || '',
        text: data.text || '',
        photos: (data.photos || []).filter(p => p && p.url)
      }
    } else {
      tlData.value = {
        image_url: null,
        custom_html: '',
        text: String(data),
        photos: []
      }
    }
  } catch {
    // Если не JSON — считаем весь текст обычным.
    tlData.value = {
      image_url: null,
      custom_html: '',
      text: raw,
      photos: []
    }
  }
}

/*
 * Контент traffic-light разбираем при каждой смене активной вкладки —
 * и по клику, и при открытии по ссылке /informaciya?tab=..., и при
 * первичной загрузке (активной становится первая вкладка).
 */
watch(
  () => activeTab.value,
  tab => {
    if (tab && tab.kind === 'traffic-light') {
      parseTrafficLightContent(tab.content)
      // При смене закладки всегда открываем «ОБЩЕЕ».
      selectedTlSection.value = 'general'
    }
  },
  { immediate: true }
)

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

/* ---- Traffic-light новая версия ---- */

/*
 * Закладка занимает весь доступный вертикальный слот: страница не
 * прокручивается, а длинный текст листается внутри своей колонки.
 */
.traffic-light-layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: clamp(
    420px,
    calc(
      100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px) -
        220px
    ),
    760px
  );
  min-height: 0;
}

/*
 * Три колонки: светофор → оглавление → содержимое.
 * Светофор и оглавление — слева, описание выбранного пункта — справа.
 */
.tl-layout {
  display: grid;
  grid-template-columns: 210px 190px minmax(0, 1fr);
  gap: 22px;
  flex: 1 1 auto;
  min-height: 0;
}

/* Светофор: кастомный HTML, картинка или 3D-заглушка. */
.tl-light {
  height: 100%;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 12px;
  background: #0b0e13;
}

.tl-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 12px;
  background: #0b0e13;
}

.tl-image-placeholder {
  width: 100%;
  display: flex;
  justify-content: center;
}

/* Произвольный HTML-код из админки (заменяет блок светофора). */
.tl-custom-html {
  width: 100%;
  max-height: 100%;
  overflow: hidden;
  border-radius: 12px;
}

.tl-custom-html :deep(img),
.tl-custom-html :deep(video),
.tl-custom-html :deep(svg),
.tl-custom-html :deep(iframe) {
  display: block;
  max-width: 100%;
  max-height: 100%;
  margin: 0 auto;
  border-radius: 12px;
}

/* Оглавление: ОБЩЕЕ и годы. */
.tl-toc {
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  border-top: 1px solid #dfe4e7;
}

.tl-toc-item {
  flex: 0 0 auto;
  padding: 12px 16px;
  border: 0;
  border-bottom: 1px solid #e7ecee;
  background: transparent;
  color: #17212b;
  font-size: 17px;
  font-weight: 800;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    padding 0.15s ease;
}

.tl-toc-item:hover {
  padding-left: 21px;
  background: #f4f6f7;
}

.tl-toc-item.is-active {
  padding-left: 21px;
  background: #fff;
  color: var(--albion-accent, #ff4d3d);
  box-shadow: inset 3px 0 0 var(--albion-accent, #ff4d3d);
}

/* Содержимое выбранного пункта. */
.tl-content {
  min-height: 0;
  overflow-y: auto;
  padding-right: 8px;
  color: #3a4750;
  font-size: 16px;
  line-height: 1.7;
}

.tl-desc {
  color: #3a4750;
  font-size: 16px;
  line-height: 1.65;
  margin-bottom: 12px;
}

/* Адреса — один компактный абзац с разделителями «·». */
.tl-addresses {
  margin-top: 16px;
  padding-left: 14px;
  border-left: 2px solid #dfe4e7;
  color: #17212b;
  font-size: 15px;
  line-height: 1.7;
}

.tl-empty {
  color: #89949b;
  font-size: 15px;
  padding: 20px 0;
}

/*
 * Ряд фотографий внизу: лента от края до края окна, фото распределяются
 * пропорционально (flex: 1 1 0) и сохраняют пропорции кадра.
 */
.tl-photo-gallery {
  flex: 0 0 auto;
  display: flex;
  gap: 10px;
  flex-wrap: nowrap;
  padding: 6px 20px 10px;
  overflow: hidden;

  /* Полноэкранный разрыв контейнера .info-shell (max-width: 1720px). */
  width: 100vw;
  margin-left: calc(50% - 50vw);
}

.tl-photo-thumb {
  flex: 1 1 0;
  min-width: 0;
  aspect-ratio: 3 / 2;
  height: auto;
  padding: 0;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
  background: #0b0e13;
  transition:
    border-color 0.15s ease,
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.tl-photo-thumb:hover {
  border-color: var(--albion-accent, #ff4d3d);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
  transform: translateY(-2px);
}

.tl-photo-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.tl-photo-empty {
  color: #89949b;
  font-size: 13px;
  padding: 20px;
  text-align: center;
  width: 100%;
}

/* ---- Адаптив ---- */

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

  .traffic-light-layout {
    height: auto;
  }

  /* На мобильном панели идут друг под другом. */
  .tl-layout {
    grid-template-columns: 1fr;
    gap: 18px;
  }

  .tl-light {
    height: 200px;
    min-height: 0;
  }

  .tl-toc {
    max-height: 220px;
  }

  .tl-content {
    overflow: visible;
    padding-right: 0;
  }

  .tl-image,
  .tl-custom-html,
  .tl-custom-html :deep(img),
  .tl-custom-html :deep(video),
  .tl-custom-html :deep(svg),
  .tl-custom-html :deep(iframe) {
    max-height: 200px;
  }

  .tl-photo-gallery {
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
  }

  /* На мобильном фото фиксированной ширины — лента прокручивается. */
  .tl-photo-thumb {
    flex: 0 0 auto;
    width: 120px;
    height: 80px;
    aspect-ratio: auto;
  }
}
</style>
