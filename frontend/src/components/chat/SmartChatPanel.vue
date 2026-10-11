<template>
  <section
    class="chat-panel"
    :class="[`chat-panel--${variant}`, { 'is-expanded': expanded }]"
    aria-label="Спроси помощника"
  >
    <div class="chat-title">
      <span
        v-if="variant !== 'compact'"
        class="chat-title-icon"
        aria-hidden="true"
      >
        ✦
      </span>
      <span v-if="variant !== 'compact' && chatNumber" class="chat-title-count">
        {{ chatNumber }}
      </span>

      <!-- Подсказка-заглушка — в один ряд со значком и номером. -->
      <span
        v-if="variant !== 'compact' && !messages.length"
        class="chat-title-hint"
      >
        Спросите про конструкции, цену, доступность или загрузку.
      </span>

      <!-- Развернуть чат вниз до конца страницы. -->
      <q-btn
        v-if="variant !== 'compact'"
        class="chat-expand"
        flat
        dense
        round
        :icon="expanded ? 'unfold_less' : 'unfold_more'"
        :title="expanded ? 'Свернуть чат' : 'Развернуть чат вниз'"
        @click="expanded = !expanded"
      />

      <q-btn
        v-if="pageLink"
        class="chat-title-link"
        outline
        dense
        no-caps
        color="primary"
        to="/chat"
        label="Открыть на странице"
        @click="$emit('close')"
      />
    </div>

    <div
      class="chat-session"
      :style="{ '--cols': columns }"
      role="log"
      aria-live="polite"
    >
      <div v-if="!messages.length && variant === 'compact'" class="chat-empty">
        Спросите про конструкции, цену, доступность или загрузку.
      </div>

      <article
        v-for="(exchange, index) in exchanges"
        :key="`exchange-${index}`"
        class="chat-module"
      >
        <div v-if="exchange.question" class="chat-message chat-message-user">
          <div class="chat-message-row">
            <div class="chat-bubble">{{ exchange.question.text }}</div>
            <button
              type="button"
              class="chat-copy"
              :title="
                copiedKey === `q-${index}` ? 'Скопировано' : 'Скопировать'
              "
              @click="copyMessage(exchange.question, `q-${index}`)"
            >
              <q-icon
                :name="copiedKey === `q-${index}` ? 'check' : 'content_copy'"
                size="14px"
              />
            </button>
          </div>
        </div>

        <template
          v-for="(message, ai) in exchange.answers"
          :key="`answer-${index}-${ai}`"
        >
          <div class="chat-message chat-message-assistant">
            <div class="chat-message-row">
              <div class="chat-bubble">{{ message.text }}</div>
              <button
                type="button"
                class="chat-copy"
                :title="
                  copiedKey === `a-${index}-${ai}`
                    ? 'Скопировано'
                    : 'Скопировать'
                "
                @click="copyMessage(message, `a-${index}-${ai}`)"
              >
                <q-icon
                  :name="
                    copiedKey === `a-${index}-${ai}` ? 'check' : 'content_copy'
                  "
                  size="14px"
                />
              </button>
            </div>
            <div v-if="message.warnings?.length" class="chat-warning">
              {{ message.warnings.join(' ') }}
            </div>
          </div>

          <div v-if="message.clarification" class="chat-options">
            <q-btn
              v-for="option in message.clarification.options"
              :key="option.value"
              outline
              dense
              no-caps
              :label="option.label"
              :disable="loading"
              @click="send(option.value)"
            />
          </div>

          <template v-for="block in resultBlocks(message)" :key="block.key">
            <div v-if="block.title" class="chat-block-title">
              {{ block.title }}
            </div>

            <div class="chat-results">
              <article
                v-for="(point, position) in block.points"
                :key="point.key"
                class="chat-result"
              >
                <div class="chat-result-num">{{ position + 1 }}</div>

                <div class="chat-result-photo-col">
                  <button
                    v-if="hasMedia(point.primary)"
                    type="button"
                    class="chat-result-photo"
                    :title="point.address"
                    @click="openMediaViewer(point.primary)"
                  >
                    <img
                      :src="mediaSrc(point.primary)"
                      :alt="point.address"
                      loading="lazy"
                    />
                  </button>
                  <div v-else class="chat-result-photo is-empty" />

                  <div
                    v-if="point.price != null"
                    class="chat-result-photo-price"
                  >
                    {{ formatPrice(point.price) }} ₽
                  </div>
                </div>

                <div class="chat-result-info">
                  <div class="chat-result-line chat-result-format">
                    <span class="chat-result-type">{{ point.type }}</span>
                  </div>
                  <div
                    v-if="point.city"
                    class="chat-result-line chat-result-city"
                  >
                    {{ point.city }}
                  </div>
                  <div class="chat-result-line chat-result-address">
                    {{ point.address }}
                  </div>
                  <div
                    v-if="point.sides"
                    class="chat-result-line chat-result-side"
                  >
                    Сторона: {{ point.sides }}
                  </div>
                </div>

                <div class="chat-result-sides">
                  <div
                    v-for="side in point.blocks"
                    :key="side.key"
                    class="chat-side"
                    :class="{ 'is-pf-mode': isBlockActive(side) }"
                  >
                    <!-- Свёрнутый режим «по сторонам»: одна строка на сторону,
                         месяц свободен, если свободна хоть одна поверхность. -->
                    <div
                      v-if="collapseToSides && side.kind === 'dynamic'"
                      class="chat-side-row"
                    >
                      <span class="chat-side-label">{{ side.parent }}</span>

                      <div class="chat-months">
                        <button
                          v-for="month in sideMonthChips(side)"
                          :key="month.full"
                          type="button"
                          class="chat-month"
                          :class="{
                            'is-selected': month.selected,
                            'is-disabled': !month.canPick,
                            [`state-${month.state}`]: true
                          }"
                          :disabled="!month.canPick"
                          :title="month.title"
                          @click="onSideMonthClick(side, month)"
                        >
                          {{ month.short }}
                        </button>
                      </div>
                    </div>

                    <template v-else>
                      <div
                        v-for="(row, ri) in side.items"
                        :key="row.id"
                        class="chat-side-row"
                      >
                        <span v-if="ri === 0" class="chat-side-label">
                          {{ side.parent }}
                        </span>

                        <div class="chat-months">
                          <button
                            v-for="month in rowMonthChips(side, row)"
                            :key="month.full"
                            type="button"
                            class="chat-month"
                            :class="{
                              'is-selected': month.selected,
                              'is-disabled': !month.canPick,
                              [`state-${month.state}`]: true
                            }"
                            :disabled="!month.canPick"
                            :title="month.title"
                            @click="onRowMonthClick(side, row, month)"
                          >
                            {{ month.short }}
                          </button>
                        </div>

                        <span class="chat-side-load">{{ loadLabel(row) }}</span>
                      </div>
                    </template>
                  </div>

                  <!-- «Портфель» общий для всех сторон конструкции.
                       Кнопка только включает/выключает выбор месяцев. -->
                  <button
                    type="button"
                    class="chat-pf-toggle"
                    :class="{ 'is-active': isPointActive(point) }"
                    :title="
                      isPointActive(point)
                        ? 'Убрать из портфеля'
                        : 'Добавить в портфель'
                    "
                    @click="onPointToggle(point)"
                  >
                    <q-icon name="work_outline" size="16px" />
                    <span>Портфель</span>
                  </button>
                </div>
              </article>
            </div>
          </template>
        </template>
      </article>
    </div>

    <form class="chat-input" @submit.prevent="submit">
      <textarea
        v-model="draft"
        rows="2"
        maxlength="2000"
        placeholder="Например: свободные пиллары на декабрь"
        :disabled="loading"
        @keydown.ctrl.enter.prevent="submit"
      />
      <div class="chat-input-actions">
        <q-btn
          unelevated
          dense
          no-caps
          color="primary"
          label="Спросить"
          type="submit"
          :loading="loading"
          :disable="!draft.trim() || loading"
        />
        <q-btn
          flat
          dense
          no-caps
          label="Очистить"
          :disable="loading || (!messages.length && !draft)"
          @click="reset"
        />
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

import { usePhotoViewer } from '../../composables/usePhotoViewer'
import { usePortfolio } from '../../composables/usePortfolio'
import { useSmartChat } from '../../composables/useSmartChat'
import { copyToClipboard } from '../../services/portfolioExport'
import {
  MONTHS,
  dedupeSides,
  groupByPoint,
  groupSides
} from '../../utils/constructionGroups'
import { getAvailabilityState, isFree } from '../../utils/availability'
import { availableMode } from '../../config/availableMode'

const props = defineProps({
  initialDraft: {
    type: String,
    default: ''
  },
  /*
   * Оформление окна:
   *   'compact' — маленькое окно в шапке (выпадающее меню);
   *   'page'    — большое окно на странице /chat.
   * Варианты стилизуются независимо (см. .chat-panel--compact / --page).
   */
  variant: {
    type: String,
    default: 'compact'
  },
  /* Показать ссылку «Открыть на странице» (в выпадающем меню шапки). */
  pageLink: {
    type: Boolean,
    default: false
  },
  /* Число столбцов сетки модулей (большое окно). */
  columns: {
    type: Number,
    default: 1
  },
  /* Ключ независимого чата: у каждого чатика своё состояние. */
  chatKey: {
    type: String,
    default: 'default'
  },
  /* Номер чата (порядковый) — показывается после значка. */
  chatNumber: {
    type: Number,
    default: null
  }
})

defineEmits(['close'])

const draft = ref(props.initialDraft)

/* Развёрнут ли чат вниз (до конца страницы). */
const expanded = ref(false)

/*
 * Сворачивать поверхности до одной строки на сторону.
 *   маленькое окно — всегда;
 *   большое окно — по настройке «Внешний вид» (available_mode).
 */
const collapseToSides = computed(
  () => props.variant === 'compact' || availableMode.value === 'sides'
)
const { messages, loading, lastResponse, send, reset } = useSmartChat(
  props.chatKey
)
const { openPhoto } = usePhotoViewer()
const {
  isInPortfolio,
  isMonthSelected,
  isSelectionMode,
  toggleSelectionMode,
  toggleMonth,
  removeSurface
} = usePortfolio()

/*
 * Сессия — список независимых модулей: один модуль = один вопрос
 * пользователя и все ответы на него (с результатами и подсказками).
 */
const exchanges = computed(() => {
  const list = []
  let current = null

  messages.value.forEach(message => {
    if (message.role === 'user') {
      current = { question: message, answers: [] }
      list.push(current)
      return
    }

    if (!current) {
      current = { question: null, answers: [] }
      list.push(current)
    }

    current.answers.push(message)
  })

  return list
})

/* Ключ сообщения, текст которого только что скопирован (для иконки-галочки). */
const copiedKey = ref('')

async function copyMessage(message, key) {
  const ok = await copyToClipboard(message?.text || '')

  if (!ok) {
    return
  }

  copiedKey.value = key
  window.setTimeout(() => {
    if (copiedKey.value === key) {
      copiedKey.value = ''
    }
  }, 1500)
}

function submit() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  send(text)
}

function formatPrice(value) {
  return new Intl.NumberFormat('ru-RU').format(value)
}

/* ------------------------------------------------- превью */

function hasMedia(item) {
  return Boolean(
    item.photo ||
    item.photo_thumb ||
    item.photo_large ||
    item.map ||
    item.map_thumb ||
    item.map_card ||
    item.map_large
  )
}

/* Превью: миниатюра фото, при её отсутствии — карта. */
function mediaSrc(item) {
  return (
    item.photo_thumb ||
    item.photo ||
    item.photo_large ||
    item.photo_url ||
    item.map_thumb ||
    item.map_card ||
    item.map_large ||
    item.map ||
    ''
  )
}

/* Клик по превью — общий просмотрщик со всеми доступными изображениями. */
function openMediaViewer(item) {
  const photoUrl = item.photo_large || item.photo || item.photo_url || ''
  const mapUrl = item.map_large || item.map_card || item.map || ''
  const images = []

  if (photoUrl) {
    images.push({ url: photoUrl, label: 'Фото' })
  }

  if (mapUrl) {
    images.push({ url: mapUrl, label: 'Карта' })
  }

  if (!images.length) {
    return
  }

  openPhoto({
    images,
    title: item.address || item.type || 'Конструкция'
  })
}

/* ----------------------------------------------- портфель: выбор месяцев */

const MONTH_NUM_TO_NAME = {
  1: 'Январь',
  2: 'Февраль',
  3: 'Март',
  4: 'Апрель',
  5: 'Май',
  6: 'Июнь',
  7: 'Июль',
  8: 'Август',
  9: 'Сентябрь',
  10: 'Октябрь',
  11: 'Ноябрь',
  12: 'Декабрь'
}

const STATUS_LABELS = {
  FREE: 'Свободно',
  RESERVED: 'Резерв',
  PENDING: 'На утверждении',
  SOLD: 'Занято',
  LOAD: 'Занято'
}

function monthNameOf(key) {
  return MONTH_NUM_TO_NAME[Number(key)] || String(key)
}

/*
 * Приводит результат чата к «поверхности» в формате каталога
 * (ключи месяцев — полные русские названия), чтобы переиспользовать
 * общий портфель и те же правила добавления месяцев, что на карте/в списке.
 */
function surfaceOf(item) {
  const monthPrices = {}
  const statuses = {}
  const monthTexts = {}

  Object.entries(item.monthly_prices || {}).forEach(([key, value]) => {
    monthPrices[monthNameOf(key)] = value
  })

  Object.entries(item.monthly_statuses || {}).forEach(([key, value]) => {
    const normalized = String(value || '').toUpperCase()
    statuses[monthNameOf(key)] =
      STATUS_LABELS[normalized] || String(value || '')
  })

  Object.entries(item.month_texts || {}).forEach(([key, value]) => {
    const name = monthNameOf(key)
    monthTexts[name] = value || statuses[name] || ''
  })

  return {
    id: item.id,
    lat: item.lat,
    lng: item.lng,
    address: item.address,
    city: item.city,
    side: item.side,
    type: item.type || item.media_type,
    size: item.size,
    price: item.price,
    load_percent: item.load_percent,
    photo: item.photo || item.photo_large || '',
    photo_thumb: item.photo_thumb,
    photo_large: item.photo_large,
    map: item.map,
    map_card: item.map_card,
    map_thumb: item.map_thumb,
    map_large: item.map_large,
    month_prices: monthPrices,
    statuses,
    months: monthTexts
  }
}

/*
 * Поверхности одной конструкции → одна карточка, как в каталоге:
 * группируем по точке, затем по стороне (kind: dynamic/static/video).
 */
/*
 * Стороны для строки «СТОРОНА»: только те, что свободны под запрос
 * (есть хотя бы один свободный месяц доступности из базы).
 */
function sidesLabel(blocks) {
  const all = blocks.map(side => side.parent).filter(Boolean)

  const free = blocks
    .filter(side =>
      side.items.some(row => MONTHS.some(month => isFree(row, month.full)))
    )
    .map(side => side.parent)
    .filter(Boolean)

  return (free.length ? free : all).join(' · ')
}

function groupPoints(items) {
  const surfaces = (items || []).map(surfaceOf)

  return groupByPoint(surfaces).map(point => {
    const first = point.items[0] || {}
    const blocks = groupSides(dedupeSides(point.items)).map((side, index) => ({
      key: `${point.key}-${index}`,
      parent: side.parent,
      kind: side.kind,
      items: side.items
    }))

    return {
      key: point.key,
      primary: first,
      type: String(first.type || 'Конструкция').trim(),
      // Стороны: только свободные под запрос (есть свободный месяц).
      sides: sidesLabel(blocks),
      address: String(first.address || first.name || 'Адрес не указан').trim(),
      city: String(first.city || '').trim(),
      price: first.price,
      blocks
    }
  })
}

/*
 * Блоки результата под конкретным сообщением: основной список и
 * предложения-альтернативы. Так каждый новый вопрос открывает свой блок.
 */
function resultBlocks(message) {
  const blocks = []

  if (message.results?.count) {
    blocks.push({
      key: 'results',
      title: '',
      points: groupPoints(message.results.items)
    })
  }

  ;(message.suggestions || []).forEach((suggestion, index) => {
    if (suggestion.items?.length) {
      blocks.push({
        key: `suggestion-${index}`,
        title: suggestion.title,
        points: groupPoints(suggestion.items)
      })
    }
  })

  return blocks
}

/* --- портфель --- */

function isBlockActive(side) {
  return side.items.some(item => {
    const id = Number(item.id)

    return isInPortfolio(id) || isSelectionMode(id)
  })
}

/* «Портфель» — общий для всех сторон конструкции. */
function pointIds(point) {
  return point.blocks.flatMap(side => side.items.map(item => Number(item.id)))
}

function isPointActive(point) {
  const ids = pointIds(point)

  return ids.some(id => isInPortfolio(id) || isSelectionMode(id))
}

function onPointToggle(point) {
  const ids = pointIds(point)

  if (isPointActive(point)) {
    // Активна — сбрасываем все поверхности конструкции.
    ids.forEach(id => removeSurface(id))
    return
  }

  // Неактивна — включаем режим выбора месяцев (как в каталоге):
  // по первой поверхности каждой стороны.
  point.blocks.forEach(side => {
    const first = side.items[0]

    if (first) {
      toggleSelectionMode(Number(first.id))
    }
  })
}

function onRowMonthClick(side, row, month) {
  if (!isBlockActive(side) || rowLocked(row, month.full)) {
    return
  }

  toggleMonth(row, month.full, row.month_prices[month.full])
}

/* --- доступность конкретной поверхности (row — уже формат каталога) --- */

function rowLocked(row, monthFull) {
  return !isFree(row, monthFull)
}

/* --- чипы месяцев в стиле портфеля --- */

/* Подсказка при наведении: месяц, цена и возможность выбора. */
function monthTitle(full, price, state, selected) {
  if (selected) {
    return `${full}: выбран${price != null ? ` · ${formatPrice(price)} ₽` : ''} — нажмите, чтобы убрать`
  }

  if (state !== 'free') {
    return `${full}: ${state === 'reserve' ? 'в резерве' : 'занято'} — выбрать нельзя`
  }

  return price != null
    ? `${full}: ${formatPrice(price)} ₽ — нажмите, чтобы добавить`
    : `${full}: свободен — нажмите, чтобы добавить (цена не указана)`
}

/* Одна строка на сторону: цена — первая непустая среди поверхностей. */
function sideMonthPrice(side, monthFull) {
  for (const row of side?.items || []) {
    const price = row.month_prices?.[monthFull]

    if (price != null) {
      return price
    }
  }

  return null
}

function sideMonthChips(side) {
  const active = isBlockActive(side)

  return MONTHS.map(month => {
    const state = isSideFree(side, month.full) ? 'free' : 'busy'
    const selected = isSideMonthSelected(side, month.full)
    const price = sideMonthPrice(side, month.full)

    return {
      full: month.full,
      short: month.short,
      state,
      selected,
      canPick: active && (selected || state === 'free'),
      title: monthTitle(month.full, price, state, selected)
    }
  })
}

/* Строка поверхности: своя доступность и цена. */
function rowMonthChips(side, row) {
  const active = isBlockActive(side)

  return MONTHS.map(month => {
    const state = getAvailabilityState(row, month.full)
    const selected = isMonthSelected(row.id, month.full)
    const price = row.month_prices?.[month.full] ?? null

    return {
      full: month.full,
      short: month.short,
      state,
      selected,
      canPick: active && (selected || state === 'free'),
      title: monthTitle(month.full, price, state, selected)
    }
  })
}

function isSideFree(side, monthFull) {
  return (side?.items || []).some(row => isFree(row, monthFull))
}

function isSideMonthSelected(side, monthFull) {
  return (side?.items || []).some(row => isMonthSelected(row.id, monthFull))
}

function onSideMonthClick(side, month) {
  for (const row of side?.items || []) {
    onRowMonthClick(side, row, month)
  }
}

/* Загруженность поверхности (для строки динамической стороны). */
function loadLabel(row) {
  return row.load_percent == null ? '' : `Загрузка ${row.load_percent}%`
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  min-width: 0;
}
.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #17212b;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.chat-title-icon {
  color: var(--albion-accent);
  font-size: 15px;
}
/* Подсказка-заглушка в шапке чата. */
.chat-title-hint {
  color: #71808c;
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
  white-space: normal;
}
/* Кнопка разворота — прижата вправо. */
.chat-expand {
  margin-left: auto;
  color: #8b98a3;
}
.chat-expand:hover {
  color: var(--albion-accent);
}
.chat-title-link {
  margin-left: auto;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.02em;
  text-transform: none;
  white-space: nowrap;
}
.chat-title-count {
  display: grid;
  place-items: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--albion-accent);
  color: #fff;
  font-size: 11px;
  font-weight: 900;
}
/* Сетка модулей сессии; число столбцов задаётся переключателем на странице. */
.chat-session {
  display: grid;
  grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
  grid-auto-rows: auto;
  gap: 14px;
  align-content: start;
  max-height: 70vh;
  overflow: auto;
  padding-right: 4px;
  margin-right: -4px;
}
/* Модуль = один вопрос и его ответы: независимый блок сессии. */
.chat-module {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  padding: 12px;
  border: 1px solid #eef1f3;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}
/* Внутри модуля прокручивается только список результатов. */
.chat-module .chat-results {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
}
.chat-module .chat-message,
.chat-module .chat-options,
.chat-module .chat-block-title {
  flex: 0 0 auto;
}
.chat-empty,
.chat-warning {
  color: #71808c;
  font-size: 13px;
}
.chat-message-user {
  align-self: flex-end;
}
.chat-message-assistant {
  align-self: flex-start;
}
.chat-bubble {
  max-width: 90%;
  padding: 9px 12px;
  border-radius: 10px;
  background: #f1f4f6;
  color: #17212b;
  white-space: pre-wrap;
}
.chat-message-user .chat-bubble {
  background: #17212b;
  color: #fff;
}
.chat-message-row {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  max-width: 100%;
}
.chat-message-user .chat-message-row {
  flex-direction: row-reverse;
}
.chat-copy {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #8b98a3;
  cursor: pointer;
  opacity: 0.6;
  transition: 0.15s ease;
}
.chat-copy:hover {
  opacity: 1;
  color: var(--albion-accent);
}
.chat-options,
.chat-input-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chat-results {
  max-height: 340px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chat-block-title {
  margin: 4px 0 2px;
  color: #71808c;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.chat-result {
  display: grid;
  /* Номер · превью · текстовая информация · месяцы и портфель. */
  grid-template-columns: 22px auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
  padding: 10px 12px;
  border: 1px solid #eef1f3;
  border-radius: 12px;
  background: #fafbfc;
}
.chat-result-num {
  color: #71808c;
  font-size: 12px;
  font-weight: 900;
  line-height: 1.4;
}
.chat-result-sides {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  min-width: 0;
}
.chat-result-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  /* Узкий текст с переносами — место отдаётся блоку месяцев. */
  max-width: 320px;
}
.chat-result-line {
  line-height: 1.35;
}
/* ФОРМАТ , рядом РАЗМЕР */
.chat-result-format {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}
.chat-result-type {
  color: #17212b;
  font-size: 14px;
  font-weight: 900;
  letter-spacing: 0.01em;
}
/* АДРЕС */
.chat-result-address {
  color: #17212b;
  font-size: 13px;
  font-weight: 900;
}
/* ГОРОД */
.chat-result-city {
  color: #71808c;
  font-size: 12px;
  font-weight: 400;
}
/* СТОРОНА */
.chat-result-side {
  color: #71808c;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.chat-result-photo {
  flex: 0 0 auto;
  align-self: start;
  width: 120px;
  aspect-ratio: 16 / 10;
  padding: 0;
  border: 1px solid #e3e8ec;
  border-radius: 8px;
  background: #f3f5f6;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s ease;
}
.chat-result-photo:hover {
  border-color: var(--albion-accent);
}
.chat-result-photo.is-empty {
  border: 0;
  background: transparent;
  cursor: default;
}
.chat-result-photo-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
/* Цена под фотографией. */
.chat-result-photo-price {
  color: #17212b;
  font-size: 12px;
  font-weight: 900;
  white-space: nowrap;
}
.chat-result-photo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.chat-side {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 6px;
  padding-top: 8px;
  margin-top: 8px;
  border-top: 1px solid #edf0f2;
}
.chat-side-label {
  flex: 0 0 auto;
  /* Общая колонка букв: A/B/C встают на одну вертикаль. */
  min-width: 16px;
  color: #17212b;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.04em;
}
.chat-side-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.chat-side-load {
  color: #8b98a3;
  font-size: 10px;
  font-weight: 700;
}
.chat-months {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.chat-month {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 6px;
  border: 0;
  border-radius: 6px;
  background: #eef1f3;
  color: #8b98a3;
  font-family: inherit;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 0.04em;
  white-space: nowrap;
  cursor: pointer;
  transition: 0.15s ease;
}
/* Палитра статусов — как в портфеле и на карточках карты. */
.chat-month.state-free {
  background: #dff3e4;
  color: #16803a;
}
.chat-month.state-reserve {
  background: #fff0d2;
  color: #b96b00;
}
.chat-month.state-busy {
  background: #f9dede;
  color: #c62828;
}
.chat-month.state-free:not(:disabled):hover {
  filter: brightness(0.95);
}
/* В режиме выбора месяцы без статуса «свободно» недоступны. */
.chat-month.is-disabled,
.chat-month:disabled {
  opacity: 0.8;
  cursor: not-allowed;
}
.chat-month.is-selected {
  background: var(--albion-accent);
  color: #fff;
}
.chat-month.is-selected:hover {
  filter: brightness(0.94);
}
.chat-pf-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 11px;
  border: 1px solid #dce2e6;
  border-radius: 8px;
  background: #fff;
  color: #52606a;
  font-family: inherit;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.3px;
  cursor: pointer;
  transition: 0.15s ease;
}
.chat-pf-toggle:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}
.chat-pf-toggle.is-active {
  border-color: var(--albion-accent);
  background: #fdeceb;
  color: var(--albion-accent);
}
.chat-input textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid #dce2e6;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
}
.chat-input-actions {
  justify-content: space-between;
  margin-top: 7px;
}
/* ============================================================
 * Варианты окна: стилизуются независимо.
 *   .chat-panel--compact — маленькое окно в шапке;
 *   .chat-panel--page    — большое окно на странице /chat.
 * Общие правила выше применяются к обоим вариантам; здесь — отличия.
 * ============================================================ */

/* Маленькое окно: ограничено высотой выпадающего меню, одна колонка. */
.chat-panel--compact .chat-session {
  grid-template-columns: minmax(0, 1fr);
  max-height: 50vh;
}
.chat-panel--compact .chat-module .chat-results {
  max-height: 220px;
}
/* «Портфель» — под блоком месяцев, во всю ширину стороны. */
.chat-panel--compact .chat-pf-toggle {
  align-self: stretch;
  width: 100%;
}

/* Большое окно: на всю ширину страницы, число столбцов — из переключателя. */
.chat-panel--page .chat-session {
  grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
  max-height: 70vh;
}
/* Список результатов внутри модуля — со скроллом, чтобы модуль не разрастался. */
.chat-panel--page .chat-module .chat-results {
  max-height: 420px;
}
/* Развёрнутый чат: список тянется вниз до конца страницы. */
.chat-panel--page.is-expanded .chat-session {
  max-height: calc(100vh - var(--albion-header-h, 78px) - 300px);
}
.chat-panel--page.is-expanded .chat-module .chat-results {
  max-height: calc(100vh - var(--albion-header-h, 78px) - 460px);
}

@media (max-width: 760px) {
  .chat-result {
    grid-template-columns: 22px minmax(0, 1fr);
  }
  .chat-result-photo-col,
  .chat-result-info,
  .chat-result-sides {
    grid-column: 2;
  }
  .chat-result-sides {
    align-items: stretch;
  }
  .chat-result-photo-col {
    align-items: stretch;
  }
  .chat-result-photo {
    width: 100%;
  }
}
</style>
