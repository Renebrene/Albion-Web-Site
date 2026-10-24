<template>
  <section ref="rootRef" class="home-slider">
    <div v-if="loading" class="home-state" role="status">
      Загрузка главной страницы…
    </div>

    <div
      v-else-if="loadError"
      class="home-state home-state--error"
      role="alert"
    >
      <p>{{ loadError }}</p>
      <button type="button" class="slide-btn" @click="load"> Повторить </button>
    </div>

    <div
      class="slides-track"
      :style="{ transform: `translateY(${-index * 100}%)` }"
    >
      <article
        v-for="(slide, slideIndex) in slides"
        :key="slide.id"
        class="slide"
        :class="{
          'is-active': slideIndex === index,
          'slide--hero': slide.kind === 'hero'
        }"
        :aria-hidden="slideIndex === index ? null : 'true'"
        :inert="slideIndex === index ? null : true"
      >
        <div class="slide-bg" :style="slideBgStyle(slide, slideIndex)">
          <div class="slide-veil"></div>
        </div>

        <div
          class="slide-inner"
          :class="{ 'slide-inner--bleed': slide.kind === 'hero' }"
        >
          <!-- ============ ВЕРХНИЙ: вариант V1, карусель влево/вправо ============ -->
          <template v-if="slide.kind === 'hero'">
            <div
              class="hero-v1"
              @mouseenter="setHeroHovered(true)"
              @mouseleave="setHeroHovered(false)"
            >
              <div
                class="hero-v1-track"
                :style="{ transform: `translateX(${-heroIndex * 100}%)` }"
              >
                <div
                  v-for="(item, hi) in heroItems(slide)"
                  :key="item.id || hi"
                  class="hero-v1-slide"
                >
                  <div class="hero-v1-bg" :style="heroBgStyle(hi, item)"></div>

                  <div class="hero-a">
                    <div class="hero-a-brand">
                      <span class="hero-a-company">{{
                        item.eyebrow || 'Группа компаний'
                      }}</span>
                      <span class="hero-a-name">{{
                        item.title || 'АЛЬБИОН'
                      }}</span>
                    </div>

                    <p v-if="item.text" class="hero-a-text">{{ item.text }}</p>

                    <div class="hero-a-actions">
                      <template v-for="btn in itemButtons(item)" :key="btn.key">
                        <button
                          v-if="isFormButton(btn)"
                          type="button"
                          class="slide-btn"
                          :class="{
                            'slide-btn--ghost': btn.variant === 'ghost'
                          }"
                          @click="gotoFormSlide"
                          >{{ btn.label }}</button
                        >
                        <a
                          v-else
                          class="slide-btn"
                          :class="{
                            'slide-btn--ghost': btn.variant === 'ghost'
                          }"
                          :href="btn.url"
                          >{{ btn.label }}</a
                        >
                      </template>
                    </div>

                    <div
                      v-if="item.extra === 'network_stats' && netStats"
                      class="hero-net"
                    >
                      <div class="hero-net-row hero-net-row--totals">
                        <div class="hero-net-cell">
                          <span class="hero-net-label">конструкций</span>
                          <b class="hero-net-value">{{
                            netStats.constructions
                          }}</b>
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

                    <div
                      v-if="hi === 0 && about && about.stats"
                      class="hero-a-stats"
                    >
                      <div
                        v-for="stat in about.stats"
                        :key="stat.label"
                        class="hero-a-stat"
                      >
                        <span class="hero-a-stat-label">{{ stat.label }}</span>
                        <b>{{ stat.value }}</b>
                      </div>
                    </div>

                    <h2 v-if="item.slogan" class="hero-a-slogan">{{
                      item.slogan
                    }}</h2>
                  </div>
                </div>
              </div>

              <button
                v-if="heroCount > 1"
                type="button"
                class="hero-arrow hero-arrow--prev"
                aria-label="Предыдущий"
                @click="gotoHero(heroIndex - 1)"
                >‹</button
              >
              <button
                v-if="heroCount > 1"
                type="button"
                class="hero-arrow hero-arrow--next"
                aria-label="Следующий"
                @click="gotoHero(heroIndex + 1)"
                >›</button
              >

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
          <GeoSlide
            v-else-if="slide.kind === 'geo'"
            ref="geoSlideRefs"
            v-model:expanded="geoExpanded"
            :slide="slide"
            :active="slideIndex === index"
            @open-form="gotoFormSlide"
          />

          <!-- ============ НОВОСТИ ============ -->
          <NewsSlide
            v-else-if="slide.kind === 'news'"
            :slide="slide"
            :news="news"
            @open-form="gotoFormSlide"
          />

          <!-- ============ ФОРМА ОБРАТНОЙ СВЯЗИ ============ -->
          <FeedbackSlide v-else-if="slide.kind === 'form'" :slide="slide" />

          <!-- ============ Простой текстовый слайд ============ -->
          <TextSlide v-else :slide="slide" @open-form="gotoFormSlide" />
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
      >↑</button
    >
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { safeCmsUrl } from '../../utils/safeCmsUrl'
import FeedbackSlide from './slides/FeedbackSlide.vue'
import GeoSlide from './slides/GeoSlide.vue'
import NewsSlide from './slides/NewsSlide.vue'
import TextSlide from './slides/TextSlide.vue'
import { isFormButton, itemButtons, slideButtons } from './slides/slideButtons'

const rootRef = ref(null)
const slides = ref([])
const index = ref(0)
const loading = ref(true)
const loadError = ref('')

/*
 * Ленивая загрузка фонов слайдов.
 *
 * Раньше background-image ставился сразу всем слайдам, и браузер тянул
 * все фоны при открытии главной. Теперь фон грузится только у активного
 * слайда и его соседей (чтобы переход был плавным без «мигания»), а
 * остальные — по мере активации (см. markSlideBg / slideBgStyle).
 */
const loadedSlideBgs = reactive(new Set())

/*
 * Ленивая загрузка фонов карусели hero-слайда (те же соображения, что и
 * для слайдов). Грузим фон текущего кадра и следующего (его вот-вот
 * покажет автопрокрутка), остальные — по мере активации.
 */
const loadedHeroBgs = reactive(new Set())

const news = ref([])
const about = ref(null)
const netStats = ref(null)

/* Автопрокрутка ТОЛЬКО горизонтальной карусели первого (hero) слайда.
   Вертикальные главные слайды сами не листаются — переключаются вручную.
   Интервал ~8с, по кругу (см. restartHeroAutoplay). */
const AUTOPLAY_MS = 8000
const heroIndex = ref(0)
let heroTimer = null
let homeSliderMounted = false

/*
 * Geo-слайд: ссылка нужна для стрелок клавиатуры и сброса при уходе со
 * слайда, а состояние модалки держим у себя — родитель решает, листать
 * ли слайды колесом (при открытой модалке — нет).
 */
const geoSlideRefs = ref([])
const geoExpanded = ref(null)

/* Пользователь просит меньше движения — не крутим hero-карусель автоматически.
   Переходы слайдов гасит CSS-медиазапрос prefers-reduced-motion. */
const prefersReducedMotion = ref(false)
let reduceMotionQuery = null

if (typeof window !== 'undefined' && window.matchMedia) {
  reduceMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = reduceMotionQuery.matches
}

/* Карточки верхнего слайда (горизонтальная карусель). */
function heroItems(slide) {
  const items = ((slide && slide.items) || []).filter(
    i => i.is_active !== false
  )

  if (items.length) {
    return items
  }

  return [
    {
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
    }
  ]
}

// ---------------------------------------------------------------- кнопки слайдов

/*
 * Кнопки приходят из home_slide_buttons (slide.buttons / item.buttons):
 * { label, url, variant: 'primary' | 'ghost' }. Если список пуст — берём
 * legacy-поля (button_label/button2_label и т.п.), чтобы старый контент
 * продолжал работать.
 */

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

/*
 * Пауза автопрокрутки: курсор над каруселью (пользователь читает кнопки)
 * или вкладка скрыта. Раньше слайды листались прямо под курсором и
 * продолжали крутиться в фоне.
 */
const heroHovered = ref(false)

function heroAutoplayPaused() {
  return (
    heroHovered.value || (typeof document !== 'undefined' && document.hidden)
  )
}

function syncHeroAutoplay() {
  if (heroAutoplayPaused()) {
    if (heroTimer) {
      clearInterval(heroTimer)
      heroTimer = null
    }

    return
  }

  restartHeroAutoplay()
}

function setHeroHovered(value) {
  heroHovered.value = value
  syncHeroAutoplay()
}

function onVisibilityChange() {
  syncHeroAutoplay()
}

function restartHeroAutoplay() {
  if (!homeSliderMounted) return

  if (heroTimer) {
    clearInterval(heroTimer)
    heroTimer = null
  }

  /* Пока карусель на паузе (курсор/скрытая вкладка) — не запускаем. */
  if (heroAutoplayPaused()) return

  // При reduced motion автопрокрутка выключена.
  if (prefersReducedMotion.value) {
    return
  }

  const slide = slides.value[index.value]

  if (!slide || slide.kind !== 'hero' || heroCount.value < 2) {
    return
  }

  heroTimer = setInterval(() => {
    heroIndex.value = (heroIndex.value + 1) % heroCount.value
  }, AUTOPLAY_MS)
}

/* Реакция на изменение предпочтения: включили reduce — гасим таймер,
   выключили — запускаем заново. */
watch(prefersReducedMotion, value => {
  if (value) {
    if (heroTimer) {
      clearInterval(heroTimer)
      heroTimer = null
    }
  } else {
    restartHeroAutoplay()
  }
})

/*
 * Помечает слайд и его соседей как «нужно загрузить фон».
 * Соседей — заранее, чтобы при листании картинка уже была в кэше.
 */
function markSlideBg(i) {
  const count = slides.value.length

  if (!count) {
    return
  }

  for (const offset of [0, -1, 1]) {
    const idx = i + offset

    if (idx >= 0 && idx < count) {
      loadedSlideBgs.add(idx)
    }
  }
}

watch([index, () => slides.value.length], () => markSlideBg(index.value), {
  immediate: true
})

/* Фон слайда с вертикальным параллаксом. */
function slideBgStyle(slide, i) {
  const style = {
    transform: `scale(1.12) translateY(${(i - index.value) * 12}%)`
  }

  // Картинку подставляем только когда фон уже разрешено грузить.
  if (slide && slide.image && loadedSlideBgs.has(i)) {
    style.backgroundImage = `url('${slide.image}')`
  }

  return style
}

/* Фон кадра hero-карусели — грузим только у разрешённых кадров. */
function heroBgStyle(i, item) {
  if (item && item.image && loadedHeroBgs.has(i)) {
    return { backgroundImage: `url('${item.image}')` }
  }

  return undefined
}

let wheelLock = 0

async function load() {
  loading.value = true
  loadError.value = ''

  try {
    const res = await fetch('/api/home')

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`)
    }

    const data = await res.json()
    slides.value = Array.isArray(data.slides) ? data.slides : []
  } catch (exc) {
    slides.value = []
    loadError.value =
      'Не удалось загрузить главную страницу. Проверьте соединение и повторите.'
    loading.value = false
    return
  }

  loading.value = false

  const kinds = new Set(slides.value.map(s => s.kind))

  if (kinds.has('hero')) {
    try {
      const res = await fetch('/api/about')

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      about.value = await res.json()
    } catch (exc) {
      /* ignore */
    }

    try {
      const res = await fetch('/api/constructions/stats')

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      netStats.value = await res.json()
    } catch (exc) {
      /* ignore */
    }
  }

  if (kinds.has('news')) {
    try {
      const res = await fetch('/api/news')

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = await res.json()
      news.value = Array.isArray(data) ? data : data.items || []
    } catch (exc) {
      /* ignore */
    }
  }
}

/* Ссылка внутри v-for — массив: берём живой экземпляр гео-слайда. */
function geoSlideApi() {
  const list = geoSlideRefs.value

  return Array.isArray(list) ? list.find(Boolean) : list
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

  /* Горизонтальный трекпад и Ctrl+wheel (zoom) не листают слайды. */
  if (event.ctrlKey || event.deltaY === 0) return

  if (slides.value.length < 2) return

  const dir = event.deltaY > 0 ? 1 : -1

  /*
   * Список городов/районов больше не прокручивается вручную (это бегущая
   * строка), поэтому прежняя проверка scrollTop только глушила колесо
   * вниз над этим блоком: scrollTop всегда 0, «докручен до края» никогда
   * не выполнялось. Теперь слайд листается одинаково в обе стороны.
   */

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
      geoSlideApi()?.move(1)
    } else if (event.key === 'ArrowLeft') {
      geoSlideApi()?.move(-1)
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
  geoExpanded.value = null
  geoSlideApi()?.reset()

  // Индексы кадров hero у каждого слайда свои — сбрасываем отметки загрузки.
  loadedHeroBgs.clear()

  /*
   * Отмечаем кадры явно: если heroIndex уже был 0 и число кадров у нового
   * слайда совпало, watch([heroIndex, heroCount]) не сработает, и фон
   * hero-кадра остался бы не подставленным до следующего тика.
   */
  markHeroBg(heroIndex.value)

  restartHeroAutoplay()
})

/*
 * Помечает текущий кадр hero-карусели и следующий как «нужно загрузить».
 * Индексы замкнуты по кругу: после последнего кадра снова идёт первый.
 */
function markHeroBg(i) {
  const count = heroCount.value

  if (!count) {
    return
  }

  loadedHeroBgs.add(((i % count) + count) % count)
  loadedHeroBgs.add((((i + 1) % count) + count) % count)
}

watch([heroIndex, heroCount], () => markHeroBg(heroIndex.value), {
  immediate: true
})

function onReduceMotionChange(event) {
  prefersReducedMotion.value = event.matches
}

onMounted(() => {
  homeSliderMounted = true
  load().then(() => {
    if (homeSliderMounted) restartHeroAutoplay()
  })

  reduceMotionQuery?.addEventListener?.('change', onReduceMotionChange)
  document.addEventListener('visibilitychange', onVisibilityChange)

  const el = rootRef.value
  if (el) el.addEventListener('wheel', onWheel, { passive: false })
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  homeSliderMounted = false
  reduceMotionQuery?.removeEventListener?.('change', onReduceMotionChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
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
.home-state {
  position: absolute;
  inset: 0;
  z-index: 5;
  display: grid;
  place-content: center;
  gap: 16px;
  padding: 24px;
  color: #fff;
  font-size: 15px;
  text-align: center;
  background: rgba(20, 24, 29, 0.92);
}
.home-state--error {
  color: #ffd7d2;
}
.home-state .slide-btn {
  justify-self: center;
}
.slides-track {
  height: 100%;
  transition: transform 0.75s cubic-bezier(0.65, 0.05, 0.36, 1);
  will-change: transform;
}
.slide {
  position: relative;
  height: 100%;
  overflow: hidden;
}
.slide-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  transform: scale(1.08);
  transition: transform 1.2s ease;
}
.slide.is-active .slide-bg {
  transform: scale(1);
}
.slide-veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(6, 12, 16, 0.55),
    rgba(6, 12, 16, 0.78)
  );
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
  transition:
    opacity 0.7s ease 0.15s,
    transform 0.7s ease 0.15s;
}
.slide.is-active .slide-inner {
  opacity: 1;
  transform: translateY(0);
}
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
.slide-btn:hover {
  transform: translateY(-2px);
}
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
.hero-net-row--totals .hero-net-value {
  font-size: clamp(28px, 3vw, 44px);
}
.hero-net-row--formats .hero-net-value {
  font-size: clamp(18px, 1.8vw, 26px);
  font-weight: 800;
}
.hero-a-text {
  text-shadow: 0 2px 20px rgba(0, 0, 0, 0.5);
}
.slide--hero .slide-bg {
  display: none;
}
.hero-v1 {
  position: relative;
  height: 100%;
  width: 100%;
  overflow: hidden;
}
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
.hero-v1 .hero-a {
  position: relative;
  z-index: 1;
}
@media (max-width: 760px) {
  .hero-a {
    padding: 24px 18px;
  }
  .hero-a-name {
    font-size: 46px;
  }
  .hero-a-text {
    max-width: 100%;
  }
}

.hero-viewport {
  position: relative;
  width: min(1500px, 96vw);
  overflow: hidden;
  margin-top: clamp(6px, 1.6vh, 18px);
}
.hero-track {
  display: flex;
  transition: transform 0.7s cubic-bezier(0.65, 0.05, 0.36, 1);
}
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
.hero-title {
  margin: 0;
  font-size: clamp(24px, 3.6vw, 56px);
  font-weight: 900;
}
.hero-text {
  margin: 0;
  max-width: min(760px, 84vw);
  font-size: clamp(14px, 1.5vw, 22px);
  opacity: 0.9;
}
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
.hero-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.hero-stat b {
  font-size: clamp(22px, 3vw, 40px);
  font-weight: 900;
  line-height: 1;
}
.hero-stat span {
  font-size: 12px;
  opacity: 0.75;
  margin-top: 2px;
}
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
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.18);
  font-size: 13px;
}
.hero-chips--ghost span {
  background: transparent;
}
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
.hero-list li {
  position: relative;
  padding-left: 16px;
  font-size: 14px;
}
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
  background: rgba(255, 255, 255, 0.08);
  text-align: left;
}
.hero-prod-item b {
  font-size: 15px;
}
.hero-prod-item span {
  font-size: 13px;
  opacity: 0.82;
}
.hero-arrow {
  position: absolute;
  top: 50%;
  z-index: 3;
  width: 44px;
  height: 44px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
}
.hero-arrow:hover {
  background: rgba(255, 255, 255, 0.3);
}
.hero-arrow--prev {
  right: 84px;
  left: auto;
}
.hero-arrow--next {
  right: 24px;
  left: auto;
}
.hero-dots {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.hero-dot {
  width: 9px;
  height: 9px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  cursor: pointer;
}
.hero-dot.is-active {
  background: #fff;
}
.slide-btn--ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.55);
}
.v-dots {
  position: absolute;
  top: 50%;
  left: 16px;
  right: auto;
  z-index: 4;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.v-dot {
  width: 10px;
  height: 10px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  cursor: pointer;
}
.v-dot.is-active {
  background: #fff;
}
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

  transition:
    background 0.15s ease,
    transform 0.15s ease;
}
.to-top:hover {
  background: rgba(20, 24, 28, 0.78);
  transform: translateY(-2px);
}
@media (max-width: 760px) {
  .hero-prod {
    grid-template-columns: 1fr;
  }
  .hero-card {
    padding: 0 8px;
    max-height: 62vh;
  }
}
</style>
