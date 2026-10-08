<template>
  <div class="portfolio-panel" :class="`portfolio-panel--${variant}`">
    <!-- ЗАГОЛОВОК -->
    <div class="portfolio-head">
      <span class="portfolio-head-icon">🗂</span>
      <span class="portfolio-head-title">Портфель</span>
      <span v-if="count" class="portfolio-head-count">{{ count }}</span>
    </div>

    <!-- НАЗВАНИЕ ПОРТФЕЛЯ (для распечатки/выгрузки) + подсказка о реквизитах -->
    <div class="portfolio-title">
      <q-input
        :model-value="titleDraft"
        dense
        outlined
        maxlength="120"
        class="portfolio-title-input"
        placeholder="Название портфеля (для распечатки)"
        @update:model-value="onTitleInput"
        @blur="commitTitle"
      />
      <div class="portfolio-title-hint">{{ requisitesHint }}</div>
    </div>

    <!-- ПУСТОЕ СОСТОЯНИЕ -->
    <div v-if="!count" class="portfolio-empty">
      Портфель пуст — добавляйте месяцы на карточках.
    </div>

    <!-- СПИСОК ПОЗИЦИЙ -->
    <div v-else class="portfolio-list">
      <div
        v-for="(item, index) in items"
        :key="item.surfaceId"
        :class="['portfolio-row', { 'has-photo': Boolean(itemThumb(item)) }]"
      >
        <div class="portfolio-row-num">{{ index + 1 }}</div>

        <!-- Маленькое превью: клик открывает полноэкранный просмотр -->
        <button
          v-if="itemThumb(item)"
          type="button"
          class="portfolio-row-photo"
          title="Открыть фото"
          @click="openItemPhoto(item)"
        >
          <img :src="itemThumb(item)" alt="" loading="lazy" decoding="async" />
        </button>

        <div class="portfolio-row-main">
          <div class="portfolio-row-format">
            {{ item.type || 'Формат не указан' }}
          </div>

          <div class="portfolio-row-address">
            {{ addressLabel(item) }}
          </div>

          <div class="portfolio-row-meta">
            <span v-if="item.side" class="portfolio-side">
              Сторона: {{ item.side }}
            </span>
            <span v-if="item.size" class="portfolio-size">
              {{ item.size }}
            </span>
          </div>

          <!-- Мини-месяцы -->
          <div class="portfolio-months">
            <span
              v-for="month in monthChips(item)"
              :key="month.full"
              class="portfolio-month"
              :class="{
                'is-selected': month.selected,
                'is-stale': month.stale
              }"
              :title="month.title"
            >
              {{ month.short }}
              <span
                v-if="month.selected && month.price !== null"
                class="portfolio-month-price"
              >
                {{ formatPrice(month.price) }} ₽
              </span>
            </span>
          </div>
        </div>

        <div class="portfolio-row-side">
          <div class="portfolio-row-sum">
            {{ formatPrice(itemSum(item)) }} ₽
          </div>

          <button
            v-if="item.photo"
            type="button"
            class="portfolio-photo-link"
            @click="openItemPhoto(item)"
          >
            Фото
          </button>

          <button
            type="button"
            class="portfolio-remove"
            @click="removeItem(item)"
          >
            Убрать
          </button>
        </div>
      </div>
    </div>

    <!-- ИТОГ -->
    <div v-if="count" class="portfolio-total">
      <span class="portfolio-total-count">
        Позиций: <b>{{ count }}</b>
      </span>
      <span class="portfolio-total-sum">
        Итого: <b>{{ formatPrice(totalPrice) }} ₽</b>
      </span>
    </div>

    <!-- ДЕЙСТВИЯ -->
    <div class="portfolio-actions">
      <q-checkbox
        v-model="withPhotos"
        dense
        class="portfolio-photos-toggle"
        label="Добавлять фото"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Excel"
        :disable="!count"
        :loading="busy === 'xlsx'"
        @click="exportAs('xlsx')"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Word"
        :disable="!count"
        :loading="busy === 'docx'"
        @click="exportAs('docx')"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="PDF"
        :disable="!count"
        :loading="busy === 'pdf'"
        @click="exportAs('pdf')"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Распечатать"
        :disable="!count"
        @click="handlePrint"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Отправить на почту"
        :disable="!count"
        @click="handleEmail"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Переправить в чат"
        :disable="!count"
        @click="handleChat"
      />
      <q-btn
        outline
        no-caps
        dense
        class="portfolio-action"
        label="Сохранить в личном кабинете"
        :disable="!count"
        :loading="saving"
        @click="handleSave"
      />
    </div>

    <!-- «Очистить» — отдельной строкой ниже, с небольшим отступом -->
    <div class="portfolio-actions portfolio-actions--danger">
      <q-btn
        flat
        no-caps
        dense
        class="portfolio-action portfolio-action--danger"
        label="Очистить"
        :disable="!count"
        @click="handleClear"
      />
    </div>

    <!-- Простой тост (плагин Notify в проекте не подключён) -->
    <Transition name="portfolio-toast">
      <div
        v-if="toast.show"
        class="portfolio-toast"
        :class="`is-${toast.type}`"
      >
        {{ toast.text }}
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref, unref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  copyToClipboard,
  downloadPortfolio,
  emailPortfolio,
  formatPrice,
  itemSum,
  portfolioText,
  printPortfolio
} from '../../services/portfolioExport'
import { useAccount } from '../../composables/useAccount'
import { usePortfolio } from '../../composables/usePortfolio'
import {
  photoLabel,
  sanitizeFileName,
  usePhotoViewer
} from '../../composables/usePhotoViewer'
import { MONTHS } from '../../utils/constructionGroups'

/*
 * Панель портфеля.
 *
 * variant:
 *   'dropdown' — компактная панель внутри выпадающего меню шапки;
 *   'page'     — развёрнутый вид на странице /portfolio.
 */
defineProps({
  variant: {
    type: String,
    default: 'page'
  }
})

const emit = defineEmits(['navigate'])

const router = useRouter()

const {
  items,
  title,
  count,
  totalPrice,
  removeSurface,
  clear,
  setTitle,
  saveToAccount
} = usePortfolio()

/*
 * Аккаунт читаем целиком (а не деструктуризацией): requisites появится
 * в useAccount позже — обращение по свойству устойчиво к отсутствию.
 */
const accountApi = useAccount()
const { isAuthenticated } = accountApi

// ------------------------------------------------- название портфеля

/*
 * Локальный черновик поля названия: ввод не «съедает» пробелы,
 * а в стор (и далее в localStorage/ЛК) значение уходит уже тримленным.
 */
const titleDraft = ref(title.value)

function onTitleInput(value) {
  titleDraft.value = value
  setTitle(value)
}

function commitTitle() {
  setTitle(titleDraft.value)
  titleDraft.value = title.value
}

// Внешнее изменение (гидратация/сервер) — подтянуть в поле.
watch(title, value => {
  if (value !== titleDraft.value && value !== titleDraft.value.trim()) {
    titleDraft.value = value
  }
})

// ------------------------------------------------- реквизиты (подсказка)

const REQUISITE_KEYS = [
  'organization',
  'inn',
  'kpp',
  'address',
  'phone',
  'email',
  'contact'
]

/* Плоский объект непустых реквизитов — для экспорта. */
function currentRequisites() {
  const source = unref(accountApi.requisites)
  const out = {}

  REQUISITE_KEYS.forEach(key => {
    const raw = source && typeof source === 'object' ? source[key] : ''

    out[key] = raw === null || raw === undefined ? '' : String(raw).trim()
  })

  return out
}

/* Реквизиты заполнены? И первая непустая подпись для короткого текста. */
const requisitesInfo = computed(() => {
  const data = currentRequisites()
  const filled = REQUISITE_KEYS.map(key => data[key]).filter(Boolean)

  return {
    hasAny: filled.length > 0,
    label: data.organization || filled[0] || ''
  }
})

const requisitesHint = computed(() => {
  if (isAuthenticated.value && requisitesInfo.value.hasAny) {
    return `Реквизиты: ${requisitesInfo.value.label}`
  }

  return 'Реквизиты можно указать в настройках личного кабинета — они появятся в распечатке и при копировании.'
})

/* Общее окно просмотра фото (singleton-композабл). */
const { openPhoto } = usePhotoViewer()

/* Формат цены месяца к числу (для подписи в чипе). */
function toNumber(value) {
  if (value === null || value === undefined) {
    return null
  }

  const num = Number(String(value).replace(/\s/g, '').replace(',', '.'))

  return Number.isFinite(num) ? num : null
}

/*
 * Маленькое превью (thumb) для строки портфеля и печати.
 * Фолбэк на card, если миниатюры нет (старые позиции в localStorage).
 */
function itemThumb(item) {
  return (item && (item.photo_thumb || item.photo)) || ''
}

/* Полноразмерный вариант — только для окна просмотра. */
function itemFullPhoto(item) {
  return (item && (item.photo_large || item.photo)) || ''
}

/*
 * Открыть фото позиции в общем окне. Название и имя файла —
 * «город, адрес · Сторона X» (как на карточке списка).
 */
function openItemPhoto(item) {
  const url = itemFullPhoto(item)

  if (!url) {
    return
  }

  const label = photoLabel({
    city: item.city,
    address: item.address,
    side: item.side
  })

  openPhoto({
    url,
    title: label,
    filename: sanitizeFileName(label, url)
  })
}

/* Подпись позиции: «город, адрес». */
function addressLabel(item) {
  const city = String((item && item.city) || '').trim()
  const address = String((item && item.address) || '').trim()

  return [city, address].filter(Boolean).join(', ') || 'Адрес не указан'
}

/*
 * Чипы месяцев: все MONTHS + возможные «чужие» месяцы позиции.
 * Выбранные подсвечены и показывают цену; stale помечается предупреждением.
 */
function monthChips(item) {
  const months = (item && item.months) || {}
  const known = new Set(MONTHS.map(month => month.full))

  const chips = MONTHS.map(({ full, short }) => {
    const value = months[full]
    const selected = Boolean(value)

    return {
      full,
      short,
      selected,
      price: selected ? toNumber(value.price) : null,
      stale: selected && Boolean(value.stale),
      title: selected
        ? value.stale
          ? `${full}: статус изменился`
          : `${full}: выбран`
        : `${full}: не выбран`
    }
  })

  Object.entries(months).forEach(([full, value]) => {
    if (known.has(full) || !value) {
      return
    }

    chips.push({
      full,
      short: full.slice(0, 3).toUpperCase(),
      selected: true,
      price: toNumber(value.price),
      stale: Boolean(value.stale),
      title: `${full}: выбран`
    })
  })

  return chips
}

// ---------------------------------------------------------------- тосты

const toast = ref({ show: false, type: 'ok', text: '' })

let toastTimer = null

function notify(text, type = 'ok') {
  toast.value = { show: true, type, text }

  if (toastTimer) {
    clearTimeout(toastTimer)
  }

  toastTimer = setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

// ---------------------------------------------------------------- действия

const busy = ref('')
const saving = ref(false)

/* Галочка «Добавлять фото» — влияет только на выгрузку и печать. */
const withPhotos = ref(false)

function removeItem(item) {
  removeSurface(item.surfaceId)
}

/* Excel/Word/PDF: формируем файл на сервере и скачиваем. */
async function exportAs(format) {
  if (!count.value) {
    return
  }

  busy.value = format

  try {
    await downloadPortfolio(format, items.value, {
      withPhotos: withPhotos.value,
      title: title.value,
      requisites: currentRequisites()
    })
    notify('Файл сформирован — начинается скачивание.')
  } catch (exc) {
    notify(
      exc && exc.message ? exc.message : 'Не удалось сформировать файл.',
      'error'
    )
  } finally {
    busy.value = ''
  }
}

/* Печать: печатная HTML-версия в новом окне. */
function handlePrint() {
  if (!count.value) {
    return
  }

  printPortfolio(items.value, {
    withPhotos: withPhotos.value,
    title: title.value,
    requisites: currentRequisites()
  })
  notify('Открываю версию для печати.')
}

/* Почта: mailto с темой и телом. */
function handleEmail() {
  if (!count.value) {
    return
  }

  emailPortfolio(items.value, {
    title: title.value,
    requisites: currentRequisites()
  })
  notify('Открываю почтовый клиент.')
}

/* Чат: копируем текст в буфер и уходим на /chat с черновиком. */
async function handleChat() {
  if (!count.value) {
    return
  }

  const text = portfolioText(items.value, {
    title: title.value,
    requisites: currentRequisites()
  })
  const copied = await copyToClipboard(text)

  notify(
    copied
      ? 'Портфель скопирован, перехожу в чат.'
      : 'Перехожу в чат (копирование недоступно).'
  )

  emit('navigate')

  router.push({ path: '/chat', query: { draft: text } })
}

/* ЛК: сохраняем при авторизации, иначе отправляем на вход. */
async function handleSave() {
  if (!count.value) {
    return
  }

  if (!isAuthenticated.value) {
    notify('Войдите в личный кабинет — портфель сохранится автоматически.')
    emit('navigate')
    router.push('/account')

    return
  }

  saving.value = true

  try {
    const ok = await saveToAccount()

    notify(
      ok
        ? 'Портфель сохранён в личном кабинете.'
        : 'Не удалось сохранить портфель.',
      ok ? 'ok' : 'error'
    )
  } catch {
    notify('Не удалось сохранить портфель.', 'error')
  } finally {
    saving.value = false
  }
}

/* Очистка портфеля с подтверждением. */
function handleClear() {
  if (!count.value) {
    return
  }

  if (!window.confirm('Очистить портфель? Действие нельзя отменить.')) {
    return
  }

  clear()
  notify('Портфель очищен.')
}
</script>

<style scoped>
.portfolio-panel {
  display: flex;
  flex-direction: column;

  gap: 12px;

  background: #fff;

  color: #17212b;
}

.portfolio-panel--dropdown {
  width: min(760px, 92vw);
  max-height: 70vh;

  overflow-y: auto;

  padding: 16px 18px;
}

.portfolio-panel--page {
  width: 100%;
  padding: 24px 26px;

  border: 1px solid #e5e9ec;
  border-radius: 16px;

  background: #fff;

  box-shadow: 0 12px 30px rgba(25, 35, 45, 0.06);
}

/* --------------------------------------------------------- Заголовок */

.portfolio-head {
  display: flex;
  align-items: center;

  gap: 8px;
}

.portfolio-head-icon {
  font-size: 15px;
}

.portfolio-head-title {
  font-size: 14px;
  font-weight: 900;

  letter-spacing: 0.04em;

  text-transform: uppercase;
}

.portfolio-head-count {
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

/* --------------------------------------------------------- Название */

.portfolio-title {
  display: flex;
  flex-direction: column;

  gap: 4px;
}

/*
 * Поле названия. В панели-дропдауне делаем компактнее, чтобы
 * не ломать текущую вёрстку выпадающего меню.
 */
.portfolio-title-input {
  font-size: 13px;
}

.portfolio-panel--dropdown .portfolio-title-input {
  font-size: 12px;
}

.portfolio-title-input :deep(.q-field__control) {
  min-height: 34px;
}

.portfolio-title-hint {
  color: #8b98a3;

  font-size: 11px;
  line-height: 1.4;
}

.portfolio-panel--dropdown .portfolio-title-hint {
  font-size: 10px;
}

/* --------------------------------------------------------- Пусто */

.portfolio-empty {
  padding: 16px 4px;

  color: #71808c;

  font-size: 13px;
  line-height: 1.45;
}

/* --------------------------------------------------------- Список */

.portfolio-list {
  display: flex;
  flex-direction: column;

  gap: 8px;
}

.portfolio-row {
  display: grid;
  grid-template-columns: 26px 1fr auto;

  gap: 10px;

  padding: 10px 12px;

  border: 1px solid #eef1f3;
  border-radius: 12px;

  background: #fafbfc;
}

/* Появилась колонка под превью — только если фото у позиции есть. */
.portfolio-row.has-photo {
  grid-template-columns: 26px 96px 1fr auto;
}

/* Маленькое превью позиции. */
.portfolio-row-photo {
  display: block;

  width: 96px;
  aspect-ratio: 16 / 10;

  padding: 0;
  border: 1px solid #e3e8ec;
  border-radius: 8px;

  background: #f3f5f6;

  overflow: hidden;
  cursor: pointer;

  transition: border-color 0.15s ease;
}

.portfolio-row-photo:hover {
  border-color: var(--albion-accent);
}

.portfolio-row-photo img {
  display: block;
  width: 100%;
  height: 100%;

  object-fit: cover;
}

.portfolio-row-num {
  color: #71808c;

  font-size: 12px;
  font-weight: 900;

  line-height: 1.4;
}

.portfolio-row-format {
  font-size: 13px;
  font-weight: 900;
}

.portfolio-row-address {
  margin-top: 2px;

  color: #52606a;

  font-size: 12px;
  line-height: 1.4;
}

.portfolio-row-meta {
  display: flex;
  flex-wrap: wrap;

  gap: 8px;

  margin-top: 4px;

  color: #71808c;

  font-size: 11px;
  font-weight: 700;
}

.portfolio-months {
  display: flex;
  flex-wrap: wrap;

  gap: 4px;

  margin-top: 8px;
}

.portfolio-month {
  display: inline-flex;
  align-items: center;

  gap: 4px;

  padding: 3px 6px;

  border-radius: 6px;

  background: #eef1f3;
  color: #8b98a3;

  font-size: 9px;
  font-weight: 900;

  letter-spacing: 0.04em;

  white-space: nowrap;
}

.portfolio-month.is-selected {
  background: var(--albion-accent);
  color: #fff;
}

.portfolio-month.is-stale {
  background: #fff3e0;
  color: #b26a00;

  box-shadow: inset 0 0 0 1px #f0b25a;
}

.portfolio-month-price {
  font-weight: 700;
}

.portfolio-row-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;

  gap: 4px;
}

.portfolio-row-sum {
  font-size: 13px;
  font-weight: 900;

  white-space: nowrap;
}

.portfolio-photo-link {
  padding: 0;

  border: none;
  background: none;

  color: var(--albion-accent);

  font-size: 11px;
  font-weight: 800;

  text-decoration: none;

  cursor: pointer;
}

.portfolio-photo-link:hover {
  text-decoration: underline;
}

.portfolio-remove {
  padding: 0;

  border: none;
  background: none;

  color: #c62828;

  font-size: 11px;
  font-weight: 800;

  cursor: pointer;
}

.portfolio-remove:hover {
  text-decoration: underline;
}

/* --------------------------------------------------------- Итог */

.portfolio-total {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;

  gap: 8px;

  padding: 10px 12px;

  border-top: 1px solid #eef1f3;

  font-size: 13px;
}

.portfolio-total-sum {
  font-size: 14px;
}

.portfolio-total-sum b {
  color: var(--albion-accent);
}

/* --------------------------------------------------------- Действия */

.portfolio-actions {
  display: flex;
  flex-wrap: wrap;

  gap: 6px;
}

/* Отдельная строка действий (сейчас — «Очистить»). */
.portfolio-actions--danger {
  margin-top: 10px;
}

.portfolio-action {
  border-radius: 8px;

  font-size: 11px;
  font-weight: 800;

  letter-spacing: 0.02em;
}

.portfolio-action--danger {
  color: #c62828;
}

/* Галочка «Добавлять фото» — по размеру кнопок действий. */
.portfolio-photos-toggle {
  align-self: center;

  font-size: 11px;
  font-weight: 800;

  letter-spacing: 0.02em;
}

/* --------------------------------------------------------- Тост */

.portfolio-toast {
  padding: 9px 12px;

  border-radius: 9px;

  font-size: 12px;
  font-weight: 700;
}

.portfolio-toast.is-ok {
  background: #eef7ee;
  color: #1b5e20;
}

.portfolio-toast.is-error {
  background: #fff0f0;
  color: #b3261e;
}

.portfolio-toast-enter-active,
.portfolio-toast-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.portfolio-toast-enter-from,
.portfolio-toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
