<template>
  <div class="geo-layout">
    <aside class="geo-sidebar" aria-label="Города и районы">
      <div class="geo-sidebar-title">Города и районы</div>
      <div class="geo-list-window">
        <div
          class="geo-list-track"
          :class="{ 'is-paused': listPaused || !active }"
          @mouseenter="listPaused = true"
          @mouseleave="listPaused = false"
          @focusin="listPaused = true"
          @focusout="listPaused = false"
        >
          <div class="geo-list-set">
            <button
              v-for="location in locations"
              :key="location.id"
              type="button"
              class="geo-list-link"
              @click="selectLocation(location)"
            >
              {{ location.label }}
            </button>
          </div>
          <div class="geo-list-set geo-list-set--clone" aria-hidden="true">
            <span
              v-for="location in locations"
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
        <span v-if="cards.length" class="geo-counter">
          {{ attractionIndex + 1 }} / {{ cards.length }}
        </span>
      </div>

      <!-- «Сдвинутая колода карт»: чистый CSS + индекс -->
      <div class="geo-stage" @wheel="onStageWheel">
        <div class="geo-fan">
          <article
            v-for="(card, i) in cards"
            :key="card.location.id"
            class="geo-fan-card"
            :class="{ 'is-front': i === attractionIndex }"
            :style="fanStyle(i)"
            :tabindex="i === attractionIndex ? 0 : -1"
            @click="onCardClick(i)"
            @keydown.enter="onCardClick(i)"
          >
            <div class="geo-fan-photo" :style="fanCover(card, i)">
              <span v-if="!fanCover(card, i)" class="geo-fan-nophoto">
                {{ card.location.label }}
              </span>
            </div>

            <div class="geo-fan-body">
              <div class="geo-fan-loc">{{ card.location.label }}</div>
              <p v-if="geoSummary(card.location)" class="geo-fan-summary">{{
                geoSummary(card.location)
              }}</p>
              <div v-else-if="card.attraction" class="geo-fan-name">{{
                card.attraction.title
              }}</div>
              <small v-if="i === attractionIndex">
                Нажмите, чтобы увеличить →
              </small>
            </div>
          </article>
        </div>

        <button
          v-if="cards.length > 1"
          type="button"
          class="geo-arrow geo-arrow--prev"
          aria-label="Предыдущая"
          @click="move(-1)"
          >‹</button
        >
        <button
          v-if="cards.length > 1"
          type="button"
          class="geo-arrow geo-arrow--next"
          aria-label="Следующая"
          @click="move(1)"
          >›</button
        >
      </div>

      <div v-if="cards.length > 1" class="geo-carousel-dots">
        <button
          v-for="(card, i) in cards"
          :key="card.location.id"
          type="button"
          :class="{ 'is-active': i === attractionIndex }"
          :aria-label="card.location.label"
          @click="attractionIndex = i"
        ></button>
      </div>

      <div class="geo-region">
        <div class="geo-region-title">Ростовская область</div>
        <p>
          Ростовская область — регион на юге России в бассейне реки Дон, с
          административным центром в Ростове-на-Дону. Здесь сходятся крупные
          транспортные пути, соединяющие центр страны, Черноморье и Кавказ.
          Область известна донским казачеством, промышленностью и аграрным югом,
          а её города и районы — от Таганрога и Новочеркасска до Волгодонска и
          Сальска — образуют единую сеть, в которой работает Albion.
        </p>
      </div>

      <div class="geo-buttons">
        <template v-for="btn in buttons" :key="btn.key">
          <button
            v-if="isFormButton(btn)"
            type="button"
            class="slide-btn"
            :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
            @click="emit('open-form')"
            >{{ btn.label }}</button
          >
          <a
            v-else
            class="slide-btn"
            :class="{ 'slide-btn--ghost': btn.variant === 'ghost' }"
            :href="btn.url"
            >{{ btn.label }}</a
          >
        </template>
      </div>
    </section>
  </div>

  <div
    v-if="expanded && expanded.location"
    class="geo-modal-backdrop"
    @click.self="closeModal"
  >
    <article
      class="geo-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="geo-modal-title"
      @keydown="onModalKeydown"
    >
      <button
        ref="closeButtonRef"
        type="button"
        class="geo-modal-close"
        aria-label="Закрыть"
        @click="closeModal"
        >×</button
      >

      <button
        v-if="cards.length > 1"
        type="button"
        class="geo-modal-nav geo-modal-nav--prev"
        aria-label="Предыдущая карточка"
        @click="move(-1)"
        >‹</button
      >
      <button
        v-if="cards.length > 1"
        type="button"
        class="geo-modal-nav geo-modal-nav--next"
        aria-label="Следующая карточка"
        @click="move(1)"
        >›</button
      >

      <div
        class="geo-modal-photo"
        :style="
          expanded.location.cover
            ? {
                backgroundImage: `url('${expanded.location.cover.url}')`
              }
            : undefined
        "
      >
        <span v-if="!expanded.location.cover" class="geo-modal-nophoto">{{
          expanded.location.label
        }}</span>
      </div>

      <div class="geo-modal-body">
        <h2 id="geo-modal-title" class="geo-modal-title">{{
          expanded.location.label
        }}</h2>

        <div v-if="expanded.location.description" class="geo-modal-text">{{
          expanded.location.description
        }}</div>
        <p v-else class="geo-modal-text geo-modal-text--muted">
          Описание этого направления скоро появится.
        </p>

        <div
          v-if="
            expanded.location.stats && expanded.location.stats.constructions
          "
          class="geo-modal-stats"
        >
          <div class="geo-modal-stats-total">
            <span class="geo-modal-stats-label">Конструкции:</span>
            <b>{{ expanded.location.stats.constructions }}</b>
          </div>
          <div class="geo-modal-formats">
            <span
              v-for="f in expanded.location.stats.formats"
              :key="f.name"
              class="geo-modal-format"
              >{{ formatPlural(f.name) }}: <b>{{ f.count }}</b></span
            >
          </div>
        </div>

        <a
          v-if="
            safeCmsUrl(expanded.location.map_href || expanded.location.href)
          "
          class="geo-modal-mapbtn"
          :href="
            safeCmsUrl(expanded.location.map_href || expanded.location.href)
          "
          >Перейти на интерактивную карту</a
        >

        <div v-if="expanded.location.cover" class="geo-modal-credit">
          <span class="geo-modal-credit-name">
            {{ expanded.location.cover.attraction_title }}
          </span>
          <span v-if="expanded.location.cover.source_name">
            · фото: {{ expanded.location.cover.source_name }}
          </span>
          <a
            v-if="safeCmsUrl(expanded.location.cover.source_url)"
            :href="safeCmsUrl(expanded.location.cover.source_url)"
            target="_blank"
            rel="noopener noreferrer"
            >источник</a
          >
          <span v-if="expanded.location.cover.license">
            · {{ expanded.location.cover.license }}
          </span>
        </div>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { safeCmsUrl } from '../../../utils/safeCmsUrl'
import { isFormButton, slideButtons } from './slideButtons'

/*
 * Слайд «Города и районы»: боковой список локаций, колода карточек
 * с достопримечательностями и модалка с описанием.
 *
 * Данные приходят целиком в `slide` (настройки из админки — в
 * `slide.settings`), поэтому компонент самодостаточен.
 *
 * Наружу отдаёт:
 *   v-model:expanded — открыта ли модалка (родителю нужно для клавиатуры
 *                      и для того, чтобы не листать слайды колесом);
 *   move(dir)        — переключить карточку (стрелки клавиатуры);
 *   reset()          — сбросить состояние при уходе со слайда;
 *   open-form        — кнопка без ссылки открывает слайд с формой.
 */
const props = defineProps({
  slide: {
    type: Object,
    required: true
  },

  expanded: {
    type: Object,
    default: null
  },

  /* Слайд на экране: неактивные гасятся через inert, но анимации в них
     продолжают крутиться — бегущую строку останавливаем явно. */
  active: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:expanded', 'open-form'])

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

const listPaused = ref(false)
const attractionIndex = ref(0)
const closeButtonRef = ref(null)

let deckWheelLock = 0

/* Модалка: при открытии ведём фокус на «Закрыть», при закрытии —
   возвращаем туда, откуда её открыли. */
let lastFocus = null

watch(
  () => props.expanded,
  (value, previous) => {
    if (value && !previous) {
      lastFocus =
        typeof document !== 'undefined' ? document.activeElement : null
      closeButtonRef.value?.focus?.()
    } else if (!value && previous) {
      if (lastFocus && typeof lastFocus.focus === 'function') {
        lastFocus.focus()
      }

      lastFocus = null
    }
  },
  /* post: кнопка закрытия уже отрисована. */
  { flush: 'post' }
)

/*
 * Удержание Tab внутри окна описания. У окна aria-modal="true", но фокус
 * всё равно уходил на карточки колоды и кнопки слайда за подложкой.
 */
function onModalKeydown(event) {
  if (event.key !== 'Tab') {
    return
  }

  const modal = event.currentTarget

  if (!modal) {
    return
  }

  const focusable = modal.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )

  if (!focusable.length) {
    return
  }

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  const active = document.activeElement

  if (event.shiftKey) {
    if (active === first || !modal.contains(active)) {
      event.preventDefault()
      last.focus()
    }

    return
  }

  if (active === last || !modal.contains(active)) {
    event.preventDefault()
    first.focus()
  }
}

const locations = computed(() => props.slide?.geo?.locations || [])

const attractions = computed(() => props.slide?.geo?.attractions || [])

/* Карточка колоды = локация + её достопримечательность (если есть). */
const cards = computed(() =>
  locations.value.map(location => ({
    location,
    attraction:
      attractions.value.find(
        item => String(item.location_id) === String(location.id)
      ) || null
  }))
)

const buttons = computed(() => slideButtons(props.slide, GEO_FALLBACK_BUTTONS))

function selectLocation(location) {
  const index = cards.value.findIndex(card => card.location.id === location.id)

  if (index >= 0) {
    attractionIndex.value = index
  }
}

function move(direction) {
  const count = cards.value.length

  if (!count) {
    return
  }

  const next = (attractionIndex.value + direction + count) % count

  attractionIndex.value = next

  /* Открыта модалка — показываем соседнюю карточку. */
  if (props.expanded) {
    emit('update:expanded', cards.value[next])
  }
}

/* Открыть карточку, которая сейчас спереди. */
function openCurrentCard() {
  const card = cards.value[attractionIndex.value]

  if (card) {
    emit('update:expanded', card)
  }
}

function onCardClick(index) {
  const card = cards.value[index]

  if (!card) {
    return
  }

  if (index === attractionIndex.value) {
    emit('update:expanded', card)
  } else {
    attractionIndex.value = index
  }
}

/*
 * Обложки подставляем только карточкам рядом с видимой зоной: у далёких
 * фон всё равно не виден (opacity: 0), а фото локации — сотни килобайт.
 * Запас ±3 карточки, чтобы при быстрой прокрутке колоды фон уже был.
 */
const FAN_MAX_VISIBLE = 6
const FAN_PRELOAD_MARGIN = 3

function fanCover(card, index) {
  const offset = cardOffset(index)

  if (Math.abs(offset) > FAN_MAX_VISIBLE + FAN_PRELOAD_MARGIN) {
    return undefined
  }

  const url = card?.attraction?.photos?.[0]?.url

  return url ? { backgroundImage: `url('${url}')` } : undefined
}

/* Смещение карточки от передней: то же, что в fanStyle, но без вёрстки. */
function cardOffset(index) {
  const count = cards.value.length
  let offset = index - attractionIndex.value

  if (count > 1) {
    if (offset > count / 2) offset -= count
    if (offset < -count / 2) offset += count
  }

  return offset
}

/* Названия форматов в именительном падеже множественного числа. */
const FORMAT_PLURALS = {
  Щит: 'Щиты',
  Видеоэкран: 'Видеоэкраны',
  'Сити-формат': 'Сити-форматы',
  Призматрон: 'Призматроны',
  Скроллер: 'Скроллеры',
  Пиллар: 'Пиллары'
}

function formatPlural(name) {
  const key = String(name || '').trim()

  return FORMAT_PLURALS[key] || key
}

/* Краткая выжимка для карточки колоды: первый абзац описания локации. */
function geoSummary(location) {
  const text = String(location?.description || '').trim()

  if (!text) return ''

  const first = text
    .split(/\n{2,}/)[0]
    .replace(/\s+/g, ' ')
    .trim()
  const limit = 180

  if (first.length <= limit) return first

  const cut = first.slice(0, limit)
  const lastSpace = cut.lastIndexOf(' ')

  return `${(lastSpace > 100 ? cut.slice(0, lastSpace) : cut).trim()}…`
}

/* Позиция карты в «колоде»: передняя по центру, соседние веером назад. */
function fanStyle(index) {
  const offset = cardOffset(index)
  const maxVisible = FAN_MAX_VISIBLE
  const clamped = Math.max(-maxVisible, Math.min(maxVisible, offset))
  const abs = Math.abs(clamped)
  const sign = clamped === 0 ? 0 : clamped > 0 ? 1 : -1

  return {
    transform:
      `translate(-50%, -50%) ` +
      `translate(${sign * abs * 46}px, ${abs * 10}px) ` +
      `rotate(${sign * abs * 4.5}deg) scale(${1 - abs * 0.05})`,
    zIndex: String(60 - Math.abs(offset)),
    opacity: Math.abs(offset) > maxVisible ? '0' : '1',
    pointerEvents: Math.abs(offset) > maxVisible ? 'none' : 'auto'
  }
}

/*
 * Колесо над колодой (режим задаётся в админке: deck_wheel_mode).
 * Обработчик висит на самой сцене и гасит всплытие, когда событие
 * обработано, — иначе родитель заодно переключил бы слайд.
 */
function onStageWheel(event) {
  const mode = props.slide?.geo?.settings?.deck_wheel_mode || 'off'

  if (mode === 'off') return

  const count = cards.value.length

  if (!count) return

  const now = Date.now()

  if (now < deckWheelLock) {
    event.preventDefault()
    event.stopPropagation()
    return
  }

  const down = event.deltaY > 0

  if (mode === 'v1') {
    event.preventDefault()
    event.stopPropagation()

    if (!down) {
      openCurrentCard()
    } else {
      const rect = event.currentTarget.getBoundingClientRect()
      const center = rect.left + rect.width / 2

      move(event.clientX < center ? -1 : 1)
    }

    deckWheelLock = now + 220
    return
  }

  if (mode === 'v2') {
    event.preventDefault()
    event.stopPropagation()
    move(down ? -1 : 1)
    deckWheelLock = now + 220
    return
  }

  if (mode === 'v3') {
    const next = attractionIndex.value + (down ? 1 : -1)

    if (next < 0 || next > count - 1) return

    event.preventDefault()
    event.stopPropagation()
    attractionIndex.value = next
    deckWheelLock = now + 220
  }
}

/* Данные обновились: если карточек стало меньше — возвращаемся к первой. */
watch(
  () => cards.value.length,
  count => {
    if (!count || attractionIndex.value >= count) {
      attractionIndex.value = 0
    }
  }
)

function closeModal() {
  emit('update:expanded', null)
}

function reset() {
  attractionIndex.value = 0
  emit('update:expanded', null)
}

defineExpose({ move, reset })
</script>

<style scoped>
/* Базовые классы слайда — см. комментарий в FeedbackSlide.vue. */
.slide-btn {
  margin-top: 8px;
  padding: 12px 26px;

  border: 0;
  border-radius: 999px;

  background: var(--albion-accent, #e2231a);
  color: #fff;

  font-family: inherit;
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

.slide-btn--ghost {
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: transparent;
}

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
  border-right: 1px solid rgba(255, 255, 255, 0.15);
  padding-right: 20px;
  overflow: hidden;
}
.geo-sidebar-title {
  font-size: 13px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: rgba(255, 255, 255, 0.65);
}
.geo-list-window {
  min-height: 0;
  flex: 1;
  overflow: hidden;
  position: relative;
  mask-image: linear-gradient(transparent, #000 7%, #000 93%, transparent);
}
.geo-list-track {
  animation: geo-marquee 48s linear infinite;
}
.geo-list-track:hover {
  animation-play-state: paused;
}
/*
 * Пауза по ховеру и по фокусу с клавиатуры (обработчики выше): без этого
 * правила строка не останавливалась при навигации табом и уезжала
 * из-под фокуса. Тем же классом гасим анимацию у неактивного слайда.
 */
.geo-list-track.is-paused {
  animation-play-state: paused;
}
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
  color: rgba(255, 255, 255, 0.9);
  font: inherit;
  font-size: 14px;
  text-decoration: none;
  text-align: left;
  cursor: pointer;
  transition:
    color 0.15s ease,
    transform 0.15s ease;
}
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
  color: rgba(255, 255, 255, 0.9);
}
.geo-counter {
  color: rgba(255, 255, 255, 0.55);
  font-size: 13px;
  white-space: nowrap;
}
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
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 16px;
  overflow: hidden;
  background: #182127;
  cursor: pointer;
  transform-origin: center;
  transition:
    transform 0.5s cubic-bezier(0.22, 0.61, 0.36, 1),
    opacity 0.4s ease;
  will-change: transform;
}
.geo-fan-card.is-front {
  border-color: rgba(255, 255, 255, 0.4);
  box-shadow: 0 20px 46px rgba(0, 0, 0, 0.42);
}
.geo-fan-photo {
  height: 54%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #10181d center/cover no-repeat;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  text-align: center;
  padding: 8px;
}
.geo-fan-body {
  padding: 11px 14px;
}
.geo-fan-loc {
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.geo-fan-name {
  margin-top: 4px;
  font-size: 14px;
  font-weight: 700;
}
.geo-fan-summary {
  margin: 5px 0 0;
  color: rgba(255, 255, 255, 0.82);
  font-size: 12px;
  line-height: 1.4;
  font-weight: 500;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.geo-fan-body small {
  display: block;
  margin-top: 7px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
}
.geo-arrow {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 42px;
  height: 42px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 26px;
  cursor: pointer;
}
.geo-arrow:hover {
  background: rgba(255, 255, 255, 0.22);
}
.geo-arrow--prev {
  left: 10px;
}
.geo-arrow--next {
  right: 10px;
}
.geo-region {
  margin-top: 14px;
  max-width: 100%;
  color: rgba(255, 255, 255, 0.78);
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
.geo-region p {
  margin: 0;
}
.geo-carousel-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}
.geo-carousel-dots button {
  width: 8px;
  height: 8px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  cursor: pointer;
}
.geo-carousel-dots button.is-active {
  background: #fff;
}
.geo-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 18px;
}
.geo-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.72);
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
  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.55);
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
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}
.geo-modal-close:hover {
  background: rgba(255, 255, 255, 0.22);
}
.geo-modal-nav {
  position: absolute;
  top: 50%;
  z-index: 3;
  width: 46px;
  height: 46px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 28px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease;
}
.geo-modal-nav:hover {
  background: rgba(255, 255, 255, 0.22);
}
.geo-modal-nav--prev {
  left: 12px;
}
.geo-modal-nav--next {
  right: 12px;
}
.geo-modal-photo {
  position: relative;
  min-height: 340px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0e1519 center/cover no-repeat;
}
.geo-modal-nophoto {
  padding: 20px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  text-align: center;
}
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
.geo-modal-text {
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  line-height: 1.7;
  white-space: pre-line;
}
.geo-modal-text--muted {
  color: rgba(255, 255, 255, 0.55);
}
.geo-modal-stats {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.05);
}
.geo-modal-stats-total {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.geo-modal-stats-total b {
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
}
.geo-modal-stats-label {
  color: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}
.geo-modal-formats {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 0;
  margin-top: 8px;
}
.geo-modal-format {
  margin-right: 7px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
}
.geo-modal-format:not(:last-child)::after {
  content: ',';
}
.geo-modal-format b {
  font-weight: 800;
}
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
  transition: filter 0.15s ease;
}
.geo-modal-mapbtn:hover {
  filter: brightness(1.08);
}
.geo-modal-credit {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.5);
  font-size: 10.5px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
.geo-modal-credit-name {
  color: rgba(255, 255, 255, 0.72);
  font-weight: 700;
}
.geo-modal-credit a {
  margin: 0 4px;
  color: rgba(255, 255, 255, 0.75);
}
@media (prefers-reduced-motion: reduce) {
  .geo-list-track {
    animation: none;
  }
  .geo-modal {
    transition: none;
  }
}
@media (max-width: 760px) {
  .geo-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
    width: 94vw;
    min-height: 0;
    gap: 14px;
  }
  .geo-sidebar {
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    padding: 0 0 10px;
    min-height: 120px;
    flex: 0 0 150px;
  }
  .geo-attractions {
    min-height: 0;
  }
  .geo-list-window {
    max-height: 150px;
  }
  .geo-region {
    display: none;
  }
  .geo-modal {
    grid-template-columns: 1fr;
    max-height: 90vh;
    overflow-y: auto;
  }
  .geo-modal-photo {
    min-height: 0;
    height: 34vh;
  }
  .geo-modal-body {
    max-height: none;
    overflow: visible;
    padding: 22px 20px;
  }
}
@keyframes geo-marquee {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-50%);
  }
}
</style>
