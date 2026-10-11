<template>
  <section
    ref="rootRef"
    class="home-slider"
  >
    <div
      class="slides-track"
      :style="{ transform: `translateY(${-index * 100}%)` }"
    >
      <article
        v-for="(slide, slideIndex) in slides"
        :key="slide.id"
        class="slide"
        :class="{ 'is-active': slideIndex === index, 'slide--hero': slide.kind === 'hero' }"
      >
        <div
          class="slide-bg"
          :style="slideBgStyle(slide, slideIndex)"
        >
          <div class="slide-veil"></div>
        </div>

        <div
          class="slide-inner"
          :class="{ 'slide-inner--bleed': slide.kind === 'hero' }"
        >
          <!-- ============ ВЕРХНИЙ: вариант V1, карусель влево/вправо ============ -->
          <template v-if="slide.kind === 'hero'">
            <div class="hero-v1">
              <div
                class="hero-v1-track"
                :style="{ transform: `translateX(${-heroIndex * 100}%)` }"
              >
                <div
                  v-for="(item, hi) in heroItems(slide)"
                  :key="item.id || hi"
                  class="hero-v1-slide"
                >
                  <div
                    class="hero-v1-bg"
                    :style="item.image ? { backgroundImage: `url('${item.image}')` } : undefined"
                  ></div>

                  <div class="hero-a">
                    <div class="hero-a-brand">
                      <span class="hero-a-company">{{ item.eyebrow || 'Группа компаний' }}</span>
                      <span class="hero-a-name">{{ item.title || 'АЛЬБИОН' }}</span>
                    </div>

                    <p v-if="item.text" class="hero-a-text">{{ item.text }}</p>

                    <div class="hero-a-actions">
                      <template
                        v-for="btn in itemButtons(item)"
                        :key="btn.key"
                      >
                        <button
                          v-if="isFormButton(btn)"
                          type="button"
                          class="slide-btn"
                          :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                          @click="gotoFormSlide"
                        >{{ btn.label }}</button>
                        <a
                          v-else
                          class="slide-btn"
                          :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                          :href="btn.url"
                        >{{ btn.label }}</a>
                      </template>
                    </div>

                    <div
                      v-if="item.extra === 'network_stats' && netStats"
                      class="hero-net"
                    >
                      <div class="hero-net-row hero-net-row--totals">
                        <div class="hero-net-cell">
                          <span class="hero-net-label">конструкций</span>
                          <b class="hero-net-value">{{ netStats.constructions }}</b>
                        </div>
                        <div class="hero-net-cell">
                          <span class="hero-net-label">сторон</span>
                          <b class="hero-net-value">{{ netStats.sides }}</b>
                        </div>
                        <div class="hero-net-cell">
                          <span class="hero-net-label">поверхностей</span>
                          <b class="hero-net-value">{{ netStats.surfaces }}</b>
                        </div>
                      </div>

                      <div class="hero-net-row hero-net-row--formats">
                        <div
                          v-for="f in netStats.formats"
                          :key="f.name"
                          class="hero-net-cell"
                        >
                          <span class="hero-net-label">{{ f.name }}</span>
                          <b class="hero-net-value">{{ f.count }}</b>
                        </div>
                      </div>
                    </div>

                    <div v-if="hi === 0 && about && about.stats" class="hero-a-stats">
                      <div
                        v-for="stat in about.stats"
                        :key="stat.label"
                        class="hero-a-stat"
                      >
                        <span class="hero-a-stat-label">{{ stat.label }}</span>
                        <b>{{ stat.value }}</b>
                      </div>
                    </div>

                    <h2 v-if="item.slogan" class="hero-a-slogan">{{ item.slogan }}</h2>
                  </div>
                </div>
              </div>

              <button
                v-if="heroCount > 1"
                type="button"
                class="hero-arrow hero-arrow--prev"
                aria-label="Предыдущий"
                @click="gotoHero(heroIndex - 1)"
              >‹</button>
              <button
                v-if="heroCount > 1"
                type="button"
                class="hero-arrow hero-arrow--next"
                aria-label="Следующий"
                @click="gotoHero(heroIndex + 1)"
              >›</button>

              <div v-if="heroCount > 1" class="hero-dots">
                <button
                  v-for="i in heroCount"
                  :key="i"
                  type="button"
                  class="hero-dot"
                  :class="{ 'is-active': i - 1 === heroIndex }"
                  :aria-label="`Слайд ${i}`"
                  @click="gotoHero(i - 1)"
                ></button>
              </div>
            </div>
          </template>

          <!-- ============ ГОРОДА/РАЙОНЫ + ДОСТОПРИМЕЧАТЕЛЬНОСТИ ============ -->
          <template v-else-if="slide.kind === 'geo'">
            <div class="geo-layout">
              <aside class="geo-sidebar" aria-label="Города и районы">
                <div class="geo-sidebar-title">Города и районы</div>
                <div class="geo-list-window">
                  <div
                    class="geo-list-track"
                    :class="{ 'is-paused': geoListPaused }"
                    @mouseenter="geoListPaused = true"
                    @mouseleave="geoListPaused = false"
                    @focusin="geoListPaused = true"
                    @focusout="geoListPaused = false"
                  >
                    <div class="geo-list-set">
                      <button
                        v-for="location in geoLocations"
                        :key="location.id"
                        type="button"
                        class="geo-list-link"
                        @click="selectGeoLocation(location)"
                      >
                        {{ location.label }}
                      </button>
                    </div>
                    <div
                      class="geo-list-set geo-list-set--clone"
                      aria-hidden="true"
                    >
                      <span
                        v-for="location in geoLocations"
                        :key="`clone-${location.id}`"
                        class="geo-list-link"
                      >
                        {{ location.label }}
                      </span>
                    </div>
                  </div>
                </div>
              </aside>

              <section class="geo-attractions" aria-label="Города и районы">
                <div class="geo-attractions-head">
                  <p v-if="slide.text" class="geo-text">{{ slide.text }}</p>
                  <span v-if="geoCards.length" class="geo-counter">
                    {{ geoAttractionIndex + 1 }} / {{ geoCards.length }}
                  </span>
                </div>

                <!-- «Сдвинутая колода карт»: чистый CSS + индекс -->
                <div class="geo-stage">
                  <div class="geo-fan">
                    <article
                      v-for="(card, i) in geoCards"
                      :key="card.location.id"
                      class="geo-fan-card"
                      :class="{ 'is-front': i === geoAttractionIndex }"
                      :style="fanStyle(i)"
                      :tabindex="i === geoAttractionIndex ? 0 : -1"
                      @click="onCardClick(i)"
                      @keydown.enter="onCardClick(i)"
                    >
                      <div
                        class="geo-fan-photo"
                        :style="fanCover(card)"
                      >
                        <span v-if="!fanCover(card)" class="geo-fan-nophoto">
                          {{ card.location.label }}
                        </span>
                      </div>

                      <div class="geo-fan-body">
                        <div class="geo-fan-loc">{{ card.location.label }}</div>
                        <p
                          v-if="geoSummary(card.location)"
                          class="geo-fan-summary"
                        >{{ geoSummary(card.location) }}</p>
                        <div
                          v-else-if="card.attraction"
                          class="geo-fan-name"
                        >{{ card.attraction.title }}</div>
                        <small v-if="i === geoAttractionIndex">
                          Нажмите, чтобы увеличить →
                        </small>
                      </div>
                    </article>
                  </div>

                  <button
                    v-if="geoCards.length > 1"
                    type="button"
                    class="geo-arrow geo-arrow--prev"
                    aria-label="Предыдущая"
                    @click="moveGeoAttraction(-1)"
                  >‹</button>
                  <button
                    v-if="geoCards.length > 1"
                    type="button"
                    class="geo-arrow geo-arrow--next"
                    aria-label="Следующая"
                    @click="moveGeoAttraction(1)"
                  >›</button>
                </div>

                <div v-if="geoCards.length > 1" class="geo-carousel-dots">
                  <button
                    v-for="(card, i) in geoCards"
                    :key="card.location.id"
                    type="button"
                    :class="{ 'is-active': i === geoAttractionIndex }"
                    :aria-label="card.location.label"
                    @click="geoAttractionIndex = i"
                  ></button>
                </div>

                <div class="geo-region">
                  <div class="geo-region-title">Ростовская область</div>
                  <p>
                    Ростовская область — регион на юге России в бассейне реки Дон,
                    с административным центром в Ростове-на-Дону. Здесь сходятся
                    крупные транспортные пути, соединяющие центр страны, Черноморье
                    и Кавказ. Область известна донским казачеством, промышленностью
                    и аграрным югом, а её города и районы — от Таганрога и
                    Новочеркасска до Волгодонска и Сальска — образуют единую сеть,
                    в которой работает Albion.
                  </p>
                </div>

                <div class="geo-buttons">
                  <template
                    v-for="btn in slideButtons(slide, GEO_FALLBACK_BUTTONS)"
                    :key="btn.key"
                  >
                    <button
                      v-if="isFormButton(btn)"
                      type="button"
                      class="slide-btn"
                      :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                      @click="gotoFormSlide"
                    >{{ btn.label }}</button>
                    <a
                      v-else
                      class="slide-btn"
                      :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                      :href="btn.url"
                    >{{ btn.label }}</a>
                  </template>
                </div>
              </section>
            </div>

            <div
              v-if="geoExpanded && geoExpanded.location"
              class="geo-modal-backdrop"
              @click.self="geoExpanded = null"
            >
              <article class="geo-modal" role="dialog" aria-modal="true">
                <button
                  type="button"
                  class="geo-modal-close"
                  aria-label="Закрыть"
                  @click="geoExpanded = null"
                >×</button>

                <button
                  v-if="geoCards.length > 1"
                  type="button"
                  class="geo-modal-nav geo-modal-nav--prev"
                  aria-label="Предыдущая карточка"
                  @click="moveGeoAttraction(-1)"
                >‹</button>
                <button
                  v-if="geoCards.length > 1"
                  type="button"
                  class="geo-modal-nav geo-modal-nav--next"
                  aria-label="Следующая карточка"
                  @click="moveGeoAttraction(1)"
                >›</button>

                <div
                  class="geo-modal-photo"
                  :style="geoExpanded.location.cover
                    ? { backgroundImage: `url('${geoExpanded.location.cover.url}')` }
                    : undefined"
                >
                  <span
                    v-if="!geoExpanded.location.cover"
                    class="geo-modal-nophoto"
                  >{{ geoExpanded.location.label }}</span>
                </div>

                <div class="geo-modal-body">
                  <h2 class="geo-modal-title">{{ geoExpanded.location.label }}</h2>

                  <div
                    v-if="geoExpanded.location.description"
                    class="geo-modal-text"
                  >{{ geoExpanded.location.description }}</div>
                  <p v-else class="geo-modal-text geo-modal-text--muted">
                    Описание этого направления скоро появится.
                  </p>

                  <div
                    v-if="geoExpanded.location.stats
                      && geoExpanded.location.stats.constructions"
                    class="geo-modal-stats"
                  >
                    <div class="geo-modal-stats-total">
                      <span class="geo-modal-stats-label">Конструкции:</span>
                      <b>{{ geoExpanded.location.stats.constructions }}</b>
                    </div>
                    <div class="geo-modal-formats">
                      <span
                        v-for="f in geoExpanded.location.stats.formats"
                        :key="f.name"
                        class="geo-modal-format"
                      >{{ formatPlural(f.name) }}: <b>{{ f.count }}</b></span>
                    </div>
                  </div>

                  <a
                    v-if="safeCmsUrl(geoExpanded.location.map_href || geoExpanded.location.href)"
                    class="geo-modal-mapbtn"
                    :href="safeCmsUrl(geoExpanded.location.map_href || geoExpanded.location.href)"
                  >Перейти на интерактивную карту</a>

                  <div
                    v-if="geoExpanded.location.cover"
                    class="geo-modal-credit"
                  >
                    <span class="geo-modal-credit-name">
                      {{ geoExpanded.location.cover.attraction_title }}
                    </span>
                    <span v-if="geoExpanded.location.cover.source_name">
                      · фото: {{ geoExpanded.location.cover.source_name }}
                    </span>
                    <a
                      v-if="safeCmsUrl(geoExpanded.location.cover.source_url)"
                      :href="safeCmsUrl(geoExpanded.location.cover.source_url)"
                      target="_blank"
                      rel="noopener noreferrer"
                    >источник</a>
                    <span v-if="geoExpanded.location.cover.license">
                      · {{ geoExpanded.location.cover.license }}
                    </span>
                  </div>
                </div>
              </article>
            </div>
          </template>

          <!-- ============ НОВОСТИ ============ -->
          <template v-else-if="slide.kind === 'news'">
            <h1 class="slide-title">{{ slide.title }}</h1>
            <p v-if="slide.text" class="slide-text">{{ slide.text }}</p>

            <div class="news-grid">
              <a
                v-for="item in news.slice(0, 3)"
                :key="item.slug"
                class="news-card"
                :href="`/novosti/${item.slug}`"
              >
                <div class="news-date">{{ formatDate(item.date || item.published_at) }}</div>
                <div class="news-title">{{ item.title }}</div>
                <div v-if="item.excerpt" class="news-excerpt">
                  {{ item.excerpt }}
                </div>
              </a>
            </div>

            <div class="news-actions">
              <template
                v-for="btn in slideButtons(slide, NEWS_FALLBACK_BUTTONS)"
                :key="btn.key"
              >
                <button
                  v-if="isFormButton(btn)"
                  type="button"
                  class="slide-btn"
                  :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                  @click="gotoFormSlide"
                >{{ btn.label }}</button>
                <a
                  v-else
                  class="slide-btn"
                  :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                  :href="btn.url"
                >{{ btn.label }}</a>
              </template>
            </div>
          </template>

          <!-- ============ ФОРМА ОБРАТНОЙ СВЯЗИ ============ -->
          <template v-else-if="slide.kind === 'form'">
            <h1 class="slide-title">{{ slide.title }}</h1>
            <p v-if="slide.text" class="slide-text">{{ slide.text }}</p>

            <form class="feedback" @submit.prevent="submitFeedback">
              <input
                v-model="form.name"
                class="fb-input"
                type="text"
                placeholder="Имя"
                autocomplete="name"
              >
              <input
                v-model="form.phone"
                class="fb-input"
                type="tel"
                placeholder="Телефон"
                autocomplete="tel"
              >
              <textarea
                v-model="form.message"
                class="fb-input fb-textarea"
                placeholder="Сообщение"
                rows="3"
              ></textarea>

              <button
                type="submit"
                class="slide-btn fb-submit"
                :disabled="sending"
              >
                {{ sending ? 'Отправляем…' : 'Отправить' }}
              </button>

              <div v-if="sent" class="fb-note fb-note--ok">
                Спасибо! Мы свяжемся с вами.
              </div>
              <div v-else-if="formError" class="fb-note fb-note--err">
                {{ formError }}
              </div>
            </form>
          </template>

          <!-- ============ Простой текстовый слайд ============ -->
          <template v-else>
            <h1 class="slide-title">{{ slide.title }}</h1>
            <p class="slide-text">{{ slide.text }}</p>

            <div class="text-actions">
              <template
                v-for="btn in textSlideButtons(slide)"
                :key="btn.key"
              >
                <button
                  v-if="isFormButton(btn)"
                  type="button"
                  class="slide-btn"
                  :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                  @click="gotoFormSlide"
                >{{ btn.label }}</button>
                <a
                  v-else
                  class="slide-btn"
                  :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
                  :href="btn.url"
                >{{ btn.label }}</a>
              </template>
            </div>
          </template>
        </div>
      </article>
    </div>

    <div v-if="slides.length > 1" class="v-dots">
      <button
        v-for="(slide, i) in slides"
        :key="slide.id"
        type="button"
        class="v-dot"
        :class="{ 'is-active': i === index }"
        :aria-label="`Слайд ${i + 1}`"
        @click="goto(i)"
      ></button>
    </div>

    <!-- Кнопка «наверх» — на всех слайдах, кроме первого -->
    <button
      v-if="slides.length > 1 && index > 0"
      type="button"
      class="to-top"
      aria-label="Наверх, к первому слайду"
      @click="goto(0)"
    >↑</button>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { safeCmsUrl } from '../../utils/safeCmsUrl'

const rootRef = ref(null)
const slides = ref([])
const index = ref(0)

const news = ref([])
const about = ref(null)
const netStats = ref(null)

const AUTOPLAY_MS = 6000
const heroIndex = ref(0)
let heroTimer = null
let homeSliderMounted = false

/* Карточки верхнего слайда (горизонтальная карусель). */
function heroItems(slide) {
  const items = ((slide && slide.items) || []).filter(i => i.is_active !== false)

  if (items.length) {
    return items
  }

  return [{
    id: 'fallback',
    eyebrow: 'Группа компаний',
    title: 'АЛЬБИОН',
    text: (about.value && about.value.intro) || (slide && slide.text) || '',
    slogan: (about.value && about.value.title) || '',
    button_label: (slide && slide.button_label) || 'Смотреть карту',
    button_url: (slide && slide.button_url) || '/vozmozhnosti',
    button2_label: 'Деятельность',
    button2_url: '/napravleniya',
    image: (slide && slide.image) || ''
  }]
}

// ---------------------------------------------------------------- кнопки слайдов

/*
 * Кнопки приходят из home_slide_buttons (slide.buttons / item.buttons):
 * { label, url, variant: 'primary' | 'ghost' }. Если список пуст — берём
 * legacy-поля (button_label/button2_label и т.п.), чтобы старый контент
 * продолжал работать.
 */
const GEO_FALLBACK_BUTTONS = [
  {
    label: 'Перейти на интерактивную карту',
    url: '/vozmozhnosti',
    variant: 'primary'
  },
  {
    label: 'Смотреть описание городов и районов',
    url: '/informaciya?tab=города и районы',
    variant: 'ghost'
  }
]

const NEWS_FALLBACK_BUTTONS = [
  { label: 'Все новости', url: '/novosti', variant: 'ghost' }
]

/* Список кнопок с ключом для v-for; пустые подписи отбрасываем. */
function withKeys(list) {
  return (Array.isArray(list) ? list : [])
    .filter(btn => btn && String(btn.label || '').trim())
    .map((btn, i) => {
      const rawUrl = String(btn.url || '').trim()
      return {
        key: btn.id !== null && btn.id !== undefined ? `b${btn.id}` : `k${i}`,
        label: String(btn.label).trim(),
        url: safeCmsUrl(rawUrl),
        invalidUrl: Boolean(rawUrl) && !safeCmsUrl(rawUrl),
        variant: btn.variant === 'ghost' ? 'ghost' : 'primary'
      }
    })
    .filter(btn => !btn.invalidUrl)
}

/* Кнопки слайда: свои из базы либо запасные (legacy/зашитые). */
function slideButtons(slide, fallback = []) {
  const own = withKeys(slide && slide.buttons)

  return own.length ? own : withKeys(fallback)
}

/* Кнопки текстового слайда: свои либо legacy-кнопка слайда. */
function textSlideButtons(slide) {
  const fallback =
    slide && slide.button_label
      ? [
          {
            label: slide.button_label,
            url: slide.button_url || '',
            variant: 'primary'
          }
        ]
      : []

  return slideButtons(slide, fallback)
}

/* Кнопки карточки hero: свои либо legacy button/button2. */
function itemButtons(item) {
  const own = withKeys(item && item.buttons)

  if (own.length) {
    return own
  }

  const fallback = []

  if (item && item.button_label) {
    fallback.push({
      label: item.button_label,
      url: item.button_url || '',
      variant: 'primary'
    })
  }

  if (item && item.button2_label) {
    fallback.push({
      label: item.button2_label,
      url: item.button2_url || '#',
      variant: 'ghost'
    })
  }

  return withKeys(fallback)
}

/* Кнопка-действие (переход к форме): пустая ссылка или якорь (#form). */
function isFormButton(btn) {
  const url = String((btn && btn.url) || '').trim()

  return !url || url.startsWith('#')
}

const heroCount = computed(() => {
  const slide = slides.value[index.value]
  return slide && slide.kind === 'hero' ? heroItems(slide).length : 0
})

function gotoHero(i) {
  const count = heroCount.value
  if (!count) return
  heroIndex.value = ((i % count) + count) % count
  restartHeroAutoplay()
}

function restartHeroAutoplay() {
  if (!homeSliderMounted) return

  if (heroTimer) {
    clearInterval(heroTimer)
    heroTimer = null
  }

  const slide = slides.value[index.value]

  if (!slide || slide.kind !== 'hero' || heroCount.value < 2) {
    return
  }

  heroTimer = setInterval(() => {
    heroIndex.value = (heroIndex.value + 1) % heroCount.value
  }, AUTOPLAY_MS)
}

/* Фон слайда с вертикальным параллаксом. */
function slideBgStyle(slide, i) {
  const style = {
    transform: `scale(1.12) translateY(${(i - index.value) * 12}%)`
  }

  if (slide && slide.image) {
    style.backgroundImage = `url('${slide.image}')`
  }

  return style
}

const form = ref({ name: '', phone: '', message: '' })
const sending = ref(false)
const sent = ref(false)
const formError = ref('')

const geoListPaused = ref(false)
const geoExpanded = ref(null)
const geoAttractionIndex = ref(0)

const currentGeo = computed(() => slides.value[index.value]?.geo || {
  settings: { map_links_enabled: true },
  locations: [],
  attractions: []
})

const geoLocations = computed(() => currentGeo.value.locations || [])
const geoAttractions = computed(() => currentGeo.value.attractions || [])

/* Карточка колоды = локация + её достопримечательность (если есть). */
const geoCards = computed(() => geoLocations.value.map(location => ({
  location,
  attraction: geoAttractions.value.find(
    item => String(item.location_id) === String(location.id)
  ) || null
})))

let wheelLock = 0
let deckWheelLock = 0

async function load() {
  try {
    const res = await fetch('/api/home')
    const data = await res.json()
    slides.value = Array.isArray(data.slides) ? data.slides : []
  } catch (exc) {
    slides.value = []
    return
  }

  const kinds = new Set(slides.value.map(s => s.kind))

  if (kinds.has('hero')) {
    try {
      const res = await fetch('/api/about')
      about.value = await res.json()
    } catch (exc) { /* ignore */ }

    try {
      const res = await fetch('/api/constructions/stats')
      netStats.value = await res.json()
    } catch (exc) { /* ignore */ }
  }

  if (kinds.has('news')) {
    try {
      const res = await fetch('/api/news')
      const data = await res.json()
      news.value = Array.isArray(data) ? data : (data.items || [])
    } catch (exc) { /* ignore */ }
  }
}

function formatDate(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`
}

function selectGeoLocation(location) {
  const idx = geoCards.value.findIndex(card => card.location.id === location.id)
  if (idx >= 0) geoAttractionIndex.value = idx
}

function moveGeoAttraction(direction) {
  const count = geoCards.value.length
  if (!count) return
  const next = (geoAttractionIndex.value + direction + count) % count
  geoAttractionIndex.value = next
  // Если открыто окно описания — переключаем и его на соседнюю карточку.
  if (geoExpanded.value) geoExpanded.value = geoCards.value[next]
}

function openCurrentGeoCard() {
  const card = geoCards.value[geoAttractionIndex.value]
  if (card) geoExpanded.value = card
}

/* Управление колодой карточек колесом мыши (режим задаётся в админке).
   Возвращает true, если событие «съедено» и вертикальный слайд не листается. */
function handleDeckWheel(event) {
  const mode = currentGeo.value.settings?.deck_wheel_mode || 'off'
  if (mode === 'off') return false
  if (slides.value[index.value]?.kind !== 'geo') return false

  const stage = event.target?.closest?.('.geo-stage')
  if (!stage) return false

  const count = geoCards.value.length
  if (!count) return false

  const now = Date.now()
  if (now < deckWheelLock) {
    event.preventDefault()
    return true
  }

  const down = event.deltaY > 0

  if (mode === 'v1') {
    event.preventDefault()
    if (!down) {
      openCurrentGeoCard()
    } else {
      const rect = stage.getBoundingClientRect()
      const center = rect.left + rect.width / 2
      moveGeoAttraction(event.clientX < center ? -1 : 1)
    }
    deckWheelLock = now + 220
    return true
  }

  if (mode === 'v2') {
    event.preventDefault()
    moveGeoAttraction(down ? -1 : 1)
    deckWheelLock = now + 220
    return true
  }

  if (mode === 'v3') {
    const next = geoAttractionIndex.value + (down ? 1 : -1)
    if (next < 0 || next > count - 1) return false
    event.preventDefault()
    geoAttractionIndex.value = next
    deckWheelLock = now + 220
    return true
  }

  return false
}

function onCardClick(i) {
  const card = geoCards.value[i]
  if (!card) return

  if (i === geoAttractionIndex.value) {
    geoExpanded.value = card
  } else {
    geoAttractionIndex.value = i
  }
}

function fanCover(card) {
  const url = card?.attraction?.photos?.[0]?.url
  return url ? { backgroundImage: `url('${url}')` } : undefined
}

/* Названия форматов в именительном падеже множественного числа. */
const FORMAT_PLURALS = {
  'Щит': 'Щиты',
  'Видеоэкран': 'Видеоэкраны',
  'Сити-формат': 'Сити-форматы',
  'Призматрон': 'Призматроны',
  'Скроллер': 'Скроллеры',
  'Пиллар': 'Пиллары'
}

function formatPlural(name) {
  const key = String(name || '').trim()
  return FORMAT_PLURALS[key] || key
}

/* Краткая выжимка для карточки колоды: первый абзац описания локации. */
function geoSummary(location) {
  const text = String(location?.description || '').trim()
  if (!text) return ''

  const first = text.split(/\n{2,}/)[0].replace(/\s+/g, ' ').trim()
  const limit = 180
  if (first.length <= limit) return first

  const cut = first.slice(0, limit)
  const lastSpace = cut.lastIndexOf(' ')
  return `${(lastSpace > 100 ? cut.slice(0, lastSpace) : cut).trim()}…`
}

/* Позиция карты в «колоде»: передняя по центру, соседние веером назад. */
function fanStyle(i) {
  const n = geoCards.value.length
  let r = i - geoAttractionIndex.value

  if (n > 1) {
    if (r > n / 2) r -= n
    if (r < -n / 2) r += n
  }

  const maxVisible = 6
  const clamped = Math.max(-maxVisible, Math.min(maxVisible, r))
  const abs = Math.abs(clamped)
  const sign = clamped === 0 ? 0 : (clamped > 0 ? 1 : -1)

  return {
    transform: `translate(-50%, -50%) `
      + `translate(${sign * abs * 46}px, ${abs * 10}px) `
      + `rotate(${sign * abs * 4.5}deg) scale(${1 - abs * 0.05})`,
    zIndex: String(60 - Math.abs(r)),
    opacity: Math.abs(r) > maxVisible ? '0' : '1',
    pointerEvents: Math.abs(r) > maxVisible ? 'none' : 'auto'
  }
}

async function submitFeedback() {
  sending.value = true
  sent.value = false
  formError.value = ''

  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })

    if (!res.ok) {
      throw new Error('Не удалось отправить')
    }

    sent.value = true
    form.value = { name: '', phone: '', message: '' }
  } catch (exc) {
    formError.value = String(exc.message || exc)
  } finally {
    sending.value = false
  }
}

function goto(i) {
  const count = slides.value.length
  if (!count) return
  index.value = Math.max(0, Math.min(count - 1, i))
}

/* Перейти к слайду «Обратная связь» (форма) на этой же странице. */
function gotoFormSlide() {
  const target = slides.value.findIndex(slide => slide.kind === 'form')
  if (target >= 0) goto(target)
}

function onWheel(event) {
  if (geoExpanded.value) return

  // Колода geo-слайда может перехватывать колесо (режим задаётся в админке).
  if (handleDeckWheel(event)) return

  if (slides.value.length < 2) return

  const dir = event.deltaY > 0 ? 1 : -1

  // Внутренний список (города/районы) прокручиваем сами, а слайд
  // переключаем только когда список уже докручен до края.
  const scroller = event.target && event.target.closest
    ? event.target.closest('.geo-list-window')
    : null

  if (scroller) {
    const atTop = scroller.scrollTop <= 0
    const atBottom =
      scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 1

    if (dir > 0 && !atBottom) return
    if (dir < 0 && !atTop) return
  }

  const now = Date.now()
  if (now < wheelLock) {
    event.preventDefault()
    return
  }

  const next = index.value + dir

  if (next < 0 || next > slides.value.length - 1) {
    return
  }

  event.preventDefault()
  wheelLock = now + 900
  index.value = next
}

function onKey(event) {
  const tag = (event.target && event.target.tagName) || ''
  if (['INPUT', 'TEXTAREA'].includes(tag)) return

  if (event.key === 'Escape' && geoExpanded.value) {
    geoExpanded.value = null
    return
  }

  // При открытом окне описания ←/→ переключают карточки колоды.
  if (geoExpanded.value) {
    if (event.key === 'ArrowRight') {
      moveGeoAttraction(1)
    } else if (event.key === 'ArrowLeft') {
      moveGeoAttraction(-1)
    }
    return
  }

  if (event.key === 'ArrowDown' || event.key === 'PageDown') {
    goto(index.value + 1)
  } else if (event.key === 'ArrowUp' || event.key === 'PageUp') {
    goto(index.value - 1)
  } else if (event.key === 'ArrowRight') {
    gotoHero(heroIndex.value + 1)
  } else if (event.key === 'ArrowLeft') {
    gotoHero(heroIndex.value - 1)
  }
}

watch(index, () => {
  heroIndex.value = 0
  geoAttractionIndex.value = 0
  geoExpanded.value = null
  restartHeroAutoplay()
})

watch(
  () => geoCards.value.length,
  count => {
    if (!count) {
      geoAttractionIndex.value = 0
    } else if (geoAttractionIndex.value >= count) {
      geoAttractionIndex.value = 0
    }
  }
)

onMounted(() => {
  homeSliderMounted = true
  load().then(() => {
    if (homeSliderMounted) restartHeroAutoplay()
  })

  const el = rootRef.value
  if (el) el.addEventListener('wheel', onWheel, { passive: false })
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  homeSliderMounted = false
  const el = rootRef.value
  if (el) el.removeEventListener('wheel', onWheel)
  window.removeEventListener('keydown', onKey)
  if (heroTimer) {
    clearInterval(heroTimer)
    heroTimer = null
  }
})
</script>

<style scoped>
.home-slider {
  position: fixed;
  top: var(--albion-header-h, 96px);
  right: 0;
  bottom: var(--albion-footer-h, 46px);
  left: 0;
  z-index: 1;
  overflow: hidden;
  background: #2a2e34;
}

.slides-track {
  height: 100%;
  transition: transform 0.75s cubic-bezier(0.65, 0.05, 0.36, 1);
  will-change: transform;
}

.slide { position: relative; height: 100%; overflow: hidden; }

.slide-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  transform: scale(1.08);
  transition: transform 1.2s ease;
}

.slide.is-active .slide-bg { transform: scale(1); }

.slide-veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(6,12,16,0.55), rgba(6,12,16,0.78));
}

.slide-inner {
  position: relative;
  z-index: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(8px, 1.4vh, 16px);
  padding: clamp(16px, 3vh, 32px) clamp(16px, 3vw, 40px);
  text-align: center;
  color: #fff;
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.7s ease 0.15s, transform 0.7s ease 0.15s;
}

.slide.is-active .slide-inner { opacity: 1; transform: translateY(0); }

.slide-title {
  margin: 0;
  font-size: clamp(26px, 4vw, 56px);
  font-weight: 900;
  letter-spacing: 0.04em;
}

.slide-text {
  margin: 0;
  max-width: 780px;
  font-size: clamp(14px, 1.5vw, 20px);
  opacity: 0.9;
}

.slide-btn {
  margin-top: 8px;
  padding: 12px 26px;
  border: 0;
  border-radius: 999px;
  background: var(--albion-accent, #e2231a);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-decoration: none;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.slide-btn:hover { transform: translateY(-2px); }

/* -------- Первый слайд: вариант A (во всю ширину, без боковых полей) -------- */

.slide-inner--bleed {
  padding: 0;
  align-items: stretch;
}

.slide--hero .slide-veil {
  background: linear-gradient(
    90deg,
    rgba(8, 12, 16, 0.95) 0%,
    rgba(8, 12, 16, 0.72) 48%,
    rgba(8, 12, 16, 0.18) 100%
  );
}

.hero-a {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: clamp(12px, 1.8vh, 22px);
  padding: clamp(28px, 6vh, 72px) clamp(28px, 6vw, 120px);
  text-align: left;
}

.hero-a-brand {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hero-a-company {
  font-size: clamp(12px, 1.1vw, 16px);
  letter-spacing: 0.3em;
  text-transform: uppercase;
  opacity: 0.8;
}

.hero-a-name {
  font-size: clamp(46px, 7vw, 108px);
  line-height: 0.95;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.hero-a-slogan {
  margin: 0;
  max-width: min(920px, 84%);
  font-size: clamp(24px, 3.4vw, 52px);
  line-height: 1.06;
  font-weight: 800;
}

.hero-a-text {
  margin: 0;
  max-width: min(620px, 78%);
  font-size: clamp(15px, 1.4vw, 20px);
  opacity: 0.9;
}

.hero-a-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

/* Обёртки списка кнопок у новостного и текстового слайдов. */
.news-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.text-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

.hero-a-stats {
  display: flex;
  flex-wrap: wrap;
  gap: clamp(18px, 2.6vw, 40px);
  margin-top: 6px;
  padding: 14px 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  background: rgba(10, 14, 18, 0.5);
}

.hero-a-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
}

.hero-a-stat-label {
  font-size: clamp(9px, 0.85vw, 11px);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.62;
}

.hero-a-stat b {
  font-size: clamp(26px, 3vw, 44px);
  font-weight: 900;
  line-height: 1;
}

/* Блок статистики сети на карточке (network_stats). */
.hero-net {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 6px;
  padding: 14px 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 14px;
  background: rgba(10, 14, 18, 0.5);
}

.hero-net-row {
  display: flex;
  flex-wrap: wrap;
  gap: clamp(16px, 2.4vw, 36px);
}

.hero-net-row--formats {
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.hero-net-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
}

.hero-net-label {
  font-size: clamp(9px, 0.85vw, 11px);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.62;
}

.hero-net-value {
  font-weight: 900;
  line-height: 1;
}

.hero-net-row--totals .hero-net-value { font-size: clamp(28px, 3vw, 44px); }
.hero-net-row--formats .hero-net-value { font-size: clamp(18px, 1.8vw, 26px); font-weight: 800; }

.hero-a-name,
.hero-a-slogan,
.hero-a-text {
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.5);
}

/* Горизонтальная карусель верхнего слайда (V1). */
.slide--hero .slide-bg { display: none; }

.hero-v1 { position: relative; height: 100%; width: 100%; overflow: hidden; }

.hero-v1-track {
  display: flex;
  height: 100%;
  transition: transform 0.8s cubic-bezier(0.65, 0.05, 0.36, 1);
}

.hero-v1-slide {
  position: relative;
  flex: 0 0 100%;
  height: 100%;
  overflow: hidden;
}

.hero-v1-bg {
  position: absolute;
  inset: 0;
  background: #141a1f center/cover no-repeat;
}

.hero-v1-slide::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    rgba(8, 12, 16, 0.95) 0%,
    rgba(8, 12, 16, 0.72) 48%,
    rgba(8, 12, 16, 0.18) 100%
  );
}

.hero-v1 .hero-a { position: relative; z-index: 1; }

@media (max-width: 760px) {
  .hero-a { padding: 24px 18px; }
  .hero-a-name { font-size: 46px; }
  .hero-a-slogan,
  .hero-a-text { max-width: 100%; }
}

/* -------- Верхний слайд: горизонтальная карусель -------- */

.hero-viewport {
  position: relative;
  width: min(1500px, 96vw);
  overflow: hidden;
  margin-top: clamp(6px, 1.6vh, 18px);
}
.hero-track { display: flex; transition: transform 0.7s cubic-bezier(0.65, 0.05, 0.36, 1); }
.hero-card {
  flex: 0 0 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(10px, 1.6vh, 18px);
  padding: 0 clamp(14px, 4vw, 64px);
}

.hero-photo {
  width: 100%;
  max-width: min(900px, 72vw);
  height: clamp(150px, 34vh, 360px);
  border-radius: 16px;
  background-size: cover;
  background-position: center;
}

.hero-title { margin: 0; font-size: clamp(24px, 3.6vw, 56px); font-weight: 900; }
.hero-text { margin: 0; max-width: min(760px, 84vw); font-size: clamp(14px, 1.5vw, 22px); opacity: 0.9; }

.hero-card {
  max-height: 56vh;
  overflow-y: auto;
}

.hero-eyebrow {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.75;
}

.hero-stats {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 14px 34px;
  margin-top: 6px;
}

.hero-stat { display: flex; flex-direction: column; align-items: center; }
.hero-stat b { font-size: clamp(22px, 3vw, 40px); font-weight: 900; line-height: 1; }
.hero-stat span { font-size: 12px; opacity: 0.75; margin-top: 2px; }

.hero-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 8px;
}

.hero-chips span {
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.14);
  border: 1px solid rgba(255,255,255,0.18);
  font-size: 13px;
}

.hero-chips--ghost span { background: transparent; }

.hero-sub {
  margin-top: 14px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.7;
}

.hero-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 24px;
  margin: 8px auto 0;
  padding: 0;
  list-style: none;
  text-align: left;
  max-width: 780px;
}

.hero-list li { position: relative; padding-left: 16px; font-size: 14px; }
.hero-list li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--albion-accent, #e2231a);
}

.hero-prod {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin: 10px auto 0;
  max-width: 880px;
}

.hero-prod-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px;
  border-radius: 12px;
  background: rgba(255,255,255,0.08);
  text-align: left;
}

.hero-prod-item b { font-size: 15px; }
.hero-prod-item span { font-size: 13px; opacity: 0.82; }

.hero-arrow {
  position: absolute;
  top: 50%;
  z-index: 3;
  width: 44px;
  height: 44px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(255,255,255,0.16);
  color: #fff;
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
}

.hero-arrow:hover { background: rgba(255,255,255,0.3); }
.hero-arrow--prev { left: 0; }
/* Обе стрелки — слева, рядом друг с другом. */
.hero-arrow--next { left: 60px; right: auto; }

.hero-dots { display: flex; gap: 8px; margin-top: 12px; }

.hero-dot {
  width: 9px; height: 9px; padding: 0; border: 0; border-radius: 50%;
  background: rgba(255,255,255,0.4); cursor: pointer;
}

.hero-dot.is-active { background: #fff; }

/* -------- Geo: бесконечный список + карусель -------- */

.geo-layout {
  display: grid;
  grid-template-columns: minmax(250px, 26%) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: clamp(20px, 3vw, 48px);
  width: min(1500px, 96vw);
  flex: 1 1 auto;
  min-height: 0;
  text-align: left;
}

.geo-sidebar {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-right: 1px solid rgba(255,255,255,0.15);
  padding-right: 20px;
  overflow: hidden;
}

.geo-sidebar-title {
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.65);
}

.geo-list-window {
  min-height: 0;
  flex: 1;
  overflow: hidden;
  position: relative;
  mask-image: linear-gradient(transparent, #000 7%, #000 93%, transparent);
}

.geo-list-track { animation: geo-marquee 48s linear infinite; }
.geo-list-track.is-paused,
.geo-list-track:focus-within,
.geo-list-track:hover { animation-play-state: paused; }

.geo-list-set {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 4px 0;
}

.geo-list-link {
  display: flex;
  align-items: baseline;
  gap: 8px;
  width: 100%;
  padding: 5px 0;
  border: 0;
  background: transparent;
  color: rgba(255,255,255,0.9);
  font: inherit;
  font-size: 14px;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
  transition: color 0.15s ease, transform 0.15s ease;
}

.geo-list-link:hover,
.geo-list-link:focus-visible {
  color: #fff;
  transform: translateX(5px);
  outline: none;
}

.geo-attractions {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: hidden;
}

.geo-attractions-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.geo-text {
  margin: 0;
  font-size: clamp(15px, 1.4vw, 20px);
  font-weight: 700;
  color: rgba(255,255,255,0.9);
}
.geo-counter { color: rgba(255,255,255,0.55); font-size: 13px; white-space: nowrap; }

/* «Сдвинутая колода карт» (чистый CSS + индекс). */
.geo-stage {
  position: relative;
  flex: 1 1 auto;
  min-height: 190px;
  margin-top: 4px;
}

.geo-fan {
  position: relative;
  width: 100%;
  height: 100%;
}

.geo-fan-card {
  position: absolute;
  top: 50%;
  left: 50%;
  width: clamp(180px, 32%, 280px);
  height: min(100%, 360px);
  max-height: 100%;
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 16px;
  overflow: hidden;
  background: #182127;
  cursor: pointer;
  transform-origin: center;
  transition: transform .5s cubic-bezier(.22,.61,.36,1), opacity .4s ease;
  will-change: transform;
}

.geo-fan-card.is-front {
  border-color: rgba(255,255,255,0.4);
  box-shadow: 0 20px 46px rgba(0,0,0,.42);
}

.geo-fan-photo {
  height: 54%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #10181d center/cover no-repeat;
  color: rgba(255,255,255,.7);
  font-size: 12px;
  text-align: center;
  padding: 8px;
}

.geo-fan-body { padding: 11px 14px; }
.geo-fan-loc {
  color: rgba(255,255,255,.55);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
}
.geo-fan-name { margin-top: 4px; font-size: 14px; font-weight: 700; }
.geo-fan-summary {
  margin: 5px 0 0;
  color: rgba(255,255,255,.82);
  font-size: 12px;
  line-height: 1.4;
  font-weight: 500;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.geo-fan-body small { display: block; margin-top: 7px; color: rgba(255,255,255,.5); font-size: 11px; }

.geo-arrow {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 42px;
  height: 42px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(0,0,0,.45);
  color: #fff;
  font-size: 26px;
  cursor: pointer;
}

.geo-arrow:hover { background: rgba(255,255,255,.22); }
.geo-arrow--prev { left: 10px; }
.geo-arrow--next { right: 10px; }
.geo-region {
  margin-top: 14px;
  max-width: 100%;
  color: rgba(255,255,255,.78);
  font-size: 13px;
  line-height: 1.5;
}

.geo-region-title {
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.geo-region p { margin: 0; }

.geo-carousel-dots { display: flex; justify-content: center; gap: 8px; margin-top: 12px; }
.geo-carousel-dots button { width: 8px; height: 8px; border: 0; border-radius: 50%; background: rgba(255,255,255,.35); cursor: pointer; }
.geo-carousel-dots button.is-active { background: #fff; }

.geo-buttons { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; margin-top: 18px; }
.slide-btn--ghost { background: transparent; border: 1px solid rgba(255,255,255,.55); }

.geo-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0,0,0,.72);
  backdrop-filter: blur(3px);
}

.geo-modal {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  width: min(1040px, 94vw);
  max-height: 86vh;
  border-radius: 18px;
  overflow: hidden;
  background: #182127;
  color: #fff;
  text-align: left;
  box-shadow: 0 30px 80px rgba(0,0,0,.55);
}

.geo-modal-close {
  position: absolute;
  top: 10px;
  right: 12px;
  z-index: 2;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 50%;
  background: rgba(0,0,0,.45);
  color: #fff;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}
.geo-modal-close:hover { background: rgba(255,255,255,.22); }

.geo-modal-nav {
  position: absolute;
  top: 50%;
  z-index: 3;
  width: 46px;
  height: 46px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(0,0,0,.45);
  color: #fff;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  transition: background .15s ease;
}
.geo-modal-nav:hover { background: rgba(255,255,255,.22); }
.geo-modal-nav--prev { left: 12px; }
.geo-modal-nav--next { right: 12px; }

.geo-modal-photo {
  position: relative;
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0e1519 center/cover no-repeat;
}

.geo-modal-nophoto { padding: 20px; color: rgba(255,255,255,.6); font-size: 14px; text-align: center; }

.geo-modal-body {
  display: flex;
  flex-direction: column;
  max-height: 86vh;
  padding: 30px 30px 24px;
  overflow-y: auto;
}

.geo-modal-title {
  margin: 0 0 14px;
  font-size: clamp(24px, 2.4vw, 34px);
  line-height: 1.08;
  font-weight: 900;
}

.geo-modal-text { color: rgba(255,255,255,.85); font-size: 15px; line-height: 1.7; white-space: pre-line; }
.geo-modal-text--muted { color: rgba(255,255,255,.55); }

.geo-modal-stats {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(255,255,255,.1);
  border-radius: 12px;
  background: rgba(255,255,255,.05);
}

.geo-modal-stats-total { display: flex; align-items: baseline; gap: 8px; }
.geo-modal-stats-total b { font-size: 22px; font-weight: 900; line-height: 1; }
.geo-modal-stats-label { color: rgba(255,255,255,.72); font-size: 13px; }

.geo-modal-formats { display: flex; flex-wrap: wrap; gap: 4px 0; margin-top: 8px; }
.geo-modal-format { margin-right: 7px; color: rgba(255,255,255,.8); font-size: 12px; }
.geo-modal-format:not(:last-child)::after { content: ','; }
.geo-modal-format b { font-weight: 800; }

.geo-modal-mapbtn {
  align-self: flex-start;
  margin-top: 16px;
  padding: 11px 18px;
  border-radius: 999px;
  background: var(--albion-accent, #ff4d3d);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
  transition: filter .15s ease;
}
.geo-modal-mapbtn:hover { filter: brightness(1.08); }

.geo-modal-credit {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid rgba(255,255,255,.14);
  color: rgba(255,255,255,.5);
  font-size: 10.5px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.geo-modal-credit-name { color: rgba(255,255,255,.72); font-weight: 700; }
.geo-modal-credit a { margin: 0 4px; color: rgba(255,255,255,.75); }

@keyframes geo-marquee {
  from { transform: translateY(0); }
  to { transform: translateY(-50%); }
}

@media (prefers-reduced-motion: reduce) {
  .geo-list-track { animation: none; }
}

/* -------- Новости -------- */

.news-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  width: min(1000px, 92vw);
  margin-top: 6px;
}

.news-card {
  display: block;
  padding: 16px;
  border-radius: 12px;
  background: rgba(255,255,255,0.08);
  text-decoration: none;
  color: #fff;
  text-align: left;
  transition: transform 0.15s ease;
}

.news-card:hover { transform: translateY(-3px); }
.news-date { font-size: 12px; opacity: 0.7; }
.news-title { font-weight: 700; font-size: 15px; margin: 6px 0; }
.news-excerpt { font-size: 13px; opacity: 0.82; }

/* -------- Форма -------- */

.feedback {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(460px, 92vw);
  margin-top: 8px;
}

.fb-input {
  padding: 12px 14px;
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: 10px;
  background: rgba(255,255,255,0.1);
  color: #fff;
  font-size: 14px;
  outline: none;
}

.fb-input::placeholder { color: rgba(255,255,255,0.6); }
.fb-textarea { resize: vertical; }
.fb-submit { align-self: center; }

.fb-note { font-size: 13px; }
.fb-note--ok { color: #86efac; }
.fb-note--err { color: #fca5a5; }

/* -------- Вертикальная навигация -------- */

.v-dots {
  position: absolute;
  top: 50%;
  right: 16px;
  z-index: 4;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.v-dot {
  width: 10px; height: 10px; padding: 0; border: 0; border-radius: 50%;
  background: rgba(255,255,255,0.4); cursor: pointer;
}

.v-dot.is-active { background: #fff; }

/* Кнопка «наверх» — фиксированный полупрозрачный круг со стрелкой. */
.to-top {
  position: absolute;
  right: clamp(14px, 2vw, 28px);
  bottom: clamp(14px, 2.5vh, 28px);
  z-index: 6;

  width: 46px;
  height: 46px;

  display: flex;
  align-items: center;
  justify-content: center;

  padding: 0;

  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 50%;

  background: rgba(20, 24, 28, 0.5);
  color: #fff;

  font-size: 22px;
  line-height: 1;

  cursor: pointer;

  backdrop-filter: blur(4px);

  transition: background 0.15s ease, transform 0.15s ease;
}

.to-top:hover {
  background: rgba(20, 24, 28, 0.78);
  transform: translateY(-2px);
}

@media (max-width: 760px) {
  .geo-layout { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); width: 94vw; min-height: 0; gap: 14px; }
  .geo-sidebar { border-right: 0; border-bottom: 1px solid rgba(255,255,255,.15); padding: 0 0 10px; min-height: 120px; flex: 0 0 150px; }
  .geo-attractions { min-height: 0; }
  .geo-list-window { max-height: 150px; }
  .geo-region { display: none; }
  .news-grid,
  .hero-list,
  .hero-prod { grid-template-columns: 1fr; }
  .hero-card { padding: 0 8px; max-height: 62vh; }

  .geo-modal { grid-template-columns: 1fr; max-height: 90vh; overflow-y: auto; }
  .geo-modal-photo { min-height: 0; height: 34vh; }
  .geo-modal-body { max-height: none; overflow: visible; padding: 22px 20px; }
}
</style>
