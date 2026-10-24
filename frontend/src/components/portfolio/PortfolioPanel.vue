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
      <div v-if="requisitesHint" class="portfolio-title-hint">
        {{ requisitesHint }}
      </div>
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
            <span v-if="!hasMonths(item)" class="portfolio-no-months">
              месяцы не выбраны · 0 ₽
            </span>
          </div>

          <!-- Мини-месяцы: клик добавляет/убирает месяц -->
          <div class="portfolio-months">
            <button
              v-for="month in monthChips(item)"
              :key="month.full"
              type="button"
              class="portfolio-month"
              :class="{
                'is-selected': month.selected,
                'is-stale': month.stale,
                'is-disabled': !month.canPick,
                [`state-${month.state}`]: true
              }"
              :disabled="!month.canPick"
              :title="month.title"
              @click="onMonthClick(item, month)"
            >
              {{ month.short }}
              <span
                v-if="month.selected && month.price !== null"
                class="portfolio-month-price"
              >
                {{ formatPrice(month.price) }} ₽
              </span>
            </button>
          </div>
        </div>

        <!-- Превью справа от текста: клик открывает полноэкранный просмотр -->
        <button
          v-if="itemThumb(item)"
          type="button"
          class="portfolio-row-photo"
          title="Открыть фото"
          @click="openItemPhoto(item)"
        >
          <img :src="itemThumb(item)" alt="" loading="lazy" decoding="async" />
        </button>

        <!-- Плейсхолдер, когда фото нет: держит колонку, чтобы строки с фото
             и без него стояли на одной вертикальной оси. -->
        <div
          v-else
          class="portfolio-row-photo portfolio-row-photo--empty"
          aria-hidden="true"
        ></div>

        <div class="portfolio-row-side">
          <div class="portfolio-row-sum">
            {{ formatPrice(itemSum(item)) }} ₽
          </div>

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
      <!-- Полный вывод: фото и карта добавляются автоматически
           (отдельные галочки «Фото»/«Карта» убраны). -->
      <q-checkbox
        v-model="fullOutput"
        dense
        class="portfolio-photos-toggle portfolio-full-output-toggle"
        :label="fullOutput ? 'Полный вывод' : 'Краткий вывод'"
        :disable="!count"
      />

      <!--
        Форматы и действия — иконками: выпадающие списки прятали частые
        действия за лишним кликом. Три основных формата вынесены наружу,
        редкие остались в «…» (exportOptions минус вынесенные).
      -->
      <!-- Пока файл собирается на сервере (LibreOffice), показываем, что
           именно происходит: одних только погашенных кнопок недостаточно. -->
      <span v-if="busy" class="portfolio-busy" role="status">
        {{ busyLabel }}
      </span>

      <div class="portfolio-icons" role="group" aria-label="Вывод портфеля">
        <q-btn
          v-for="badge in fileBadges"
          :key="badge.value"
          flat
          dense
          class="portfolio-icon"
          :disable="!count || Boolean(busy)"
          :loading="busy === badge.value"
          :aria-label="badge.title"
          @click="exportAs(badge.value)"
        >
          <span class="portfolio-file-badge" :class="`is-${badge.value}`">
            {{ badge.badge }}
          </span>

          <q-tooltip>{{ badge.title }}</q-tooltip>
        </q-btn>

        <q-btn-dropdown
          flat
          dense
          class="portfolio-icon"
          :disable="!count || Boolean(busy)"
          aria-label="Остальные форматы"
        >
          <template #label>
            <span class="portfolio-more">…</span>

            <q-tooltip>Остальные форматы</q-tooltip>
          </template>

          <q-list dense class="portfolio-export-menu">
            <q-item
              v-for="option in extraExportOptions"
              :key="option.value"
              v-close-popup
              clickable
              @click="exportAs(option.value)"
            >
              <q-item-section>
                <q-item-label>{{ option.label }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>

        <q-btn
          flat
          dense
          class="portfolio-icon"
          icon="print"
          :disable="!count || Boolean(busy)"
          :loading="busy === 'print'"
          aria-label="Печать"
          @click="handlePrint"
        >
          <q-tooltip>Печать</q-tooltip>
        </q-btn>

        <q-btn
          flat
          dense
          class="portfolio-icon"
          icon="mail_outline"
          :disable="!count || Boolean(busy)"
          aria-label="Отправить письмом"
          @click="handleEmail"
        >
          <q-tooltip>Отправить письмом</q-tooltip>
        </q-btn>

        <!--
          Ссылка на портфель: переносится сам портфель (?pf=…), а не
          фильтры — этим она отличается от «Поделиться» в каталоге.
        -->
        <q-btn
          flat
          dense
          class="portfolio-icon"
          icon="link"
          :disable="!count || Boolean(busy)"
          aria-label="Ссылка на портфель"
          @click="sharePortfolioLink"
        >
          <q-tooltip ref="linkTip" :offset="[0, 6]">
            {{
              linkCopied
                ? 'Скопировано в память!'
                : 'Вы можете отправить содержимое портфеля ссылкой'
            }}
          </q-tooltip>
        </q-btn>
      </div>

      <!--
        Сохранение в личный кабинет. Кабинет скрыт флагом ACCOUNT_UI_ENABLED
        (портфель живёт в рамках сессии), но код сохранён — вернём флагом.
      -->
      <span v-if="ACCOUNT_UI_ENABLED" class="portfolio-save-wrap">
        <q-btn
          outline
          no-caps
          dense
          class="portfolio-action"
          label="Сохранить"
          :disable="!count || !isAuthenticated"
          :loading="saving"
          @click="handleSave"
        />
        <q-tooltip v-if="!isAuthenticated">Войдите в личный кабинет</q-tooltip>
      </span>

      <q-btn
        unelevated
        no-caps
        dense
        color="primary"
        class="portfolio-action"
        label="Отправить заявку"
        :disable="!count"
        @click="openRequest"
      />

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
    <!--
      Заявка по выбранным позициям. Личного кабинета нет (см.
      doc/account-cabinet.md) — уходит публичным POST /api/requests.
    -->
    <q-dialog v-model="requestOpen">
      <q-card class="request-card">
        <q-card-section>
          <div class="request-title">Отправить заявку</div>

          <p class="request-hint">
            {{ count }} {{ positionsWord }} из портфеля — мы свяжемся по
            указанному телефону или e-mail.
          </p>

          <p v-if="requestLimitNotice" class="request-hint request-hint--warn">
            {{ requestLimitNotice }}
          </p>

          <q-input
            ref="requestNameRef"
            v-model="requestForm.name"
            dense
            outlined
            label="Имя"
            autocomplete="name"
            :error="Boolean(requestFieldErrors.name)"
            :error-message="requestFieldErrors.name"
            @update:model-value="clearRequestFieldError('name')"
          />

          <!-- Способ связи: телефон или e-mail — достаточно одного. -->
          <div
            class="request-contact-switch"
            role="group"
            aria-label="Способ связи"
          >
            <button
              type="button"
              :class="{ active: requestContactMode === 'phone' }"
              @click="setContactMode('phone')"
            >
              Телефон
            </button>

            <button
              type="button"
              :class="{ active: requestContactMode === 'email' }"
              @click="setContactMode('email')"
            >
              E-mail
            </button>
          </div>

          <q-input
            v-if="requestContactMode === 'phone'"
            ref="requestPhoneRef"
            v-model="requestForm.phone"
            dense
            outlined
            type="tel"
            autocomplete="tel"
            label="Телефон"
            placeholder="+7 900 000-00-00"
            :error="Boolean(requestFieldErrors.contact)"
            :error-message="requestFieldErrors.contact"
            @blur="formatRequestPhone"
            @update:model-value="clearRequestFieldError('contact')"
          />

          <q-input
            v-else
            ref="requestEmailRef"
            v-model="requestForm.email"
            dense
            outlined
            type="email"
            autocomplete="email"
            label="E-mail"
            placeholder="name@example.ru"
            :error="Boolean(requestFieldErrors.contact)"
            :error-message="requestFieldErrors.contact"
            @update:model-value="clearRequestFieldError('contact')"
          />

          <q-input
            v-model="requestForm.comment"
            dense
            outlined
            autogrow
            type="textarea"
            label="Комментарий"
          />

          <div v-if="requestError" class="request-error">
            {{ requestError }}
          </div>
          <div v-else-if="requestDone" class="request-ok">
            Заявка отправлена — мы свяжемся с вами.
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Закрыть" @click="requestOpen = false" />
          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Отправить"
            :loading="requestSending"
            :disable="requestDone"
            @click="submitRequest"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Очистка портфеля: своё окно вместо нативного confirm. -->
    <q-dialog v-model="clearDialog" persistent>
      <q-card class="portfolio-clear-dialog">
        <q-card-section>
          <div class="portfolio-clear-title">Очистить портфель?</div>
          <div class="portfolio-clear-text">
            Будут убраны все {{ count }} позиций этой подборки. Действие нельзя
            отменить.
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" @click="clearDialog = false" />
          <q-btn
            unelevated
            no-caps
            color="negative"
            label="Очистить"
            @click="confirmClear"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <Transition name="portfolio-toast">
      <div
        v-if="toast.show"
        class="portfolio-toast"
        :class="`is-${toast.type}`"
      >
        <span>{{ toast.text }}</span>

        <button
          v-if="toast.action"
          type="button"
          class="portfolio-toast-action"
          @click="runToastAction"
        >
          {{ toast.action.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, unref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  copyToClipboard,
  downloadPortfolio,
  emailPortfolio,
  formatPrice,
  itemSum,
  printPortfolio
} from '../../services/portfolioExport'
import { useAccount } from '../../composables/useAccount'
import { ACCOUNT_UI_ENABLED } from '../../config/features'
import { urlStateTokenFormat } from '../../config/urlStateMode'
import { usePortfolio } from '../../composables/usePortfolio'
import {
  photoLabel,
  sanitizeFileName,
  usePhotoViewer
} from '../../composables/usePhotoViewer'
import {
  MONTHS,
  MONTH_ORDER,
  buildMonthList
} from '../../utils/constructionGroups'
import { getAvailabilityState } from '../../utils/availability'
import { isValidEmail, normalizeRuPhone } from '../../utils/contactFields'
import { encodePortfolioLink } from '../../utils/portfolioLink'

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
  toggleItemMonth,
  removeSurface,
  restoreSurface,
  clear,
  setTitle,
  saveToAccount,
  accountSaveError
} = usePortfolio()

/*
 * Ошибка автосохранения портфеля в ЛК. Повторы уже идут в composable,
 * здесь только показываем причину — и при открытии панели, если ошибка
 * появилась, пока панель была закрыта.
 */
watch(
  accountSaveError,
  message => {
    if (message) {
      notify(message, 'error')
    }
  },
  { immediate: true }
)

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
  /*
   * Кабинет отключён — подсказка про реквизиты ведёт в несуществующий
   * раздел. Код реквизитов сохранён: при включении ACCOUNT_UI_ENABLED
   * подсказка вернётся вместе с кабинетом.
   */
  if (!ACCOUNT_UI_ENABLED) {
    return ''
  }

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

/* Карта-схема: крупный вариант, иначе card, иначе миниатюра. */
function itemFullMap(item) {
  return (item && (item.map_large || item.map_card || item.map_thumb)) || ''
}

/*
 * Открыть позицию в общем окне: сначала фото, затем карта-схема
 * (переключение стрелками/точками). Название — «город, адрес ·
 * Сторона X»; у карты к имени файла добавляется «· карта».
 */
function openItemPhoto(item) {
  const photoUrl = itemFullPhoto(item)
  const mapUrl = itemFullMap(item)

  if (!photoUrl && !mapUrl) {
    return
  }

  const label = photoLabel({
    city: item.city,
    address: item.address,
    side: item.side
  })

  const images = []

  if (photoUrl) {
    images.push({
      url: photoUrl,
      label: 'Фото',
      filename: sanitizeFileName(label, photoUrl)
    })
  }

  if (mapUrl) {
    images.push({
      url: mapUrl,
      label: 'Карта',
      filename: sanitizeFileName(`${label} · карта`, mapUrl)
    })
  }

  openPhoto({ images, title: label })
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
function hasMonths(item) {
  return Object.keys((item && item.months) || {}).length > 0
}

function monthChips(item) {
  const months = (item && item.months) || {}
  const prices = (item && item.prices) || {}
  const monthTexts = (item && item.monthTexts) || {}
  const statuses = (item && item.statuses) || {}

  /*
   * Глобальный MONTHS заполняется только на странице рекламных
   * возможностей. На главной и /portfolio строим список из самой позиции,
   * иначе свободные месяцы в панели не отображаются.
   */
  const baseNames = new Set(MONTHS.map(month => month.full))

  /*
   * Fallback нужен только когда глобальный список ещё не заполнен
   * (главная, прямой заход на /portfolio). На /vozmozhnosti он уже
   * содержит актуальный календарь, и подмешивать снимок позиции не надо.
   */
  if (!baseNames.size) {
    for (const key of Object.keys(prices)) baseNames.add(key)
    for (const key of Object.keys(monthTexts)) baseNames.add(key)
    for (const key of Object.keys(statuses)) baseNames.add(key)
    for (const key of Object.keys(months)) baseNames.add(key)
  }

  const sortedNames = [...baseNames].sort((a, b) => {
    const ia = MONTH_ORDER.indexOf(a)
    const ib = MONTH_ORDER.indexOf(b)

    if (ia === -1 && ib === -1) return a.localeCompare(b, 'ru')
    if (ia === -1) return 1
    if (ib === -1) return -1

    return ia - ib
  })

  const known = new Set(sortedNames)
  const chips = buildMonthList(sortedNames).map(({ full, short }) => {
    const value = months[full]
    const selected = Boolean(value)
    const price = selected ? toNumber(value.price) : toNumber(prices[full])

    /*
     * Статус — тем же разбором, что на карте и в списке: статус берётся
     * из item.statuses, а сырой текст месяцев (item.monthTexts) — там,
     * где статуса нет (проценты загрузки у видеоэкранов). См.
     * getMonthValue в utils/availability.
     */
    const state = getAvailabilityState(
      { months: item?.monthTexts, statuses: item?.statuses },
      full
    )
    const free = state === 'free'

    /*
     * Добавить можно любой свободный месяц — цена не обязательна
     * (как в попапе карты). Если цены нет, месяц добавится без суммы.
     */
    const canPick = selected || free

    let title

    if (selected) {
      title = value.stale
        ? `${full}: статус изменился — нажмите, чтобы убрать`
        : `${full}: выбран${price !== null ? ` · ${formatPrice(price)} ₽` : ''} — нажмите, чтобы убрать`
    } else if (!free) {
      title = `${full}: ${state === 'reserve' ? 'в резерве' : 'занято'} — выбрать нельзя`
    } else if (price === null) {
      title = `${full}: свободен — нажмите, чтобы добавить (цена не указана)`
    } else {
      title = `${full}: ${formatPrice(price)} ₽ — нажмите, чтобы добавить`
    }

    return {
      full,
      short,
      selected,
      canPick,
      free,
      /* Статус для раскраски чипа: free / reserve / busy. */
      state,
      price: selected ? toNumber(value.price) : null,
      stale: selected && Boolean(value.stale),
      title
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
      canPick: true,
      state: 'free',
      price: toNumber(value.price),
      stale: Boolean(value.stale),
      title: `${full}: выбран — нажмите, чтобы убрать`
    })
  })

  return chips
}

/* Клик по месяцу в панели: добавить или убрать прямо здесь. */
function onMonthClick(item, month) {
  if (!month || !month.canPick) {
    return
  }

  toggleItemMonth(item.surfaceId, month.full)
}

// ---------------------------------------------------------------- тосты

const toast = ref({ show: false, type: 'ok', text: '', action: null })

let toastTimer = null

/* action: { label, run } — кнопка в тосте (например, «Вернуть»). */
function notify(text, type = 'ok', action = null) {
  toast.value = { show: true, type, text, action }

  if (toastTimer) {
    clearTimeout(toastTimer)
  }

  toastTimer = setTimeout(
    () => {
      toast.value.show = false
      toast.value.action = null
    },
    action ? 5000 : 3000
  )
}

function runToastAction() {
  const action = toast.value.action

  if (!action || typeof action.run !== 'function') {
    return
  }

  toast.value.show = false
  toast.value.action = null

  action.run()
}

// ---------------------------------------------------------------- действия

const busy = ref('')
const saving = ref(false)

/* Подпись текущей операции: формат файла или подготовка печати. */
const busyLabel = computed(() =>
  busy.value === 'print' ? 'Готовим версию для печати…' : 'Формируем файл…'
)

/*
 * «Полный вывод»: фото и карта добавляются в документ автоматически
 * (отдельных галочек «Фото»/«Карта» больше нет). Выключен по умолчанию;
 * влияет на выгрузку и печать.
 */
const fullOutput = ref(false)

/*
 * Форматы выгрузки. Текстовые (csv/txt/md/json) отдают только
 * текстовую часть и не зависят от «полный/краткий вывод» — это обеспечивает
 * сервер (см. backend/services/portfolio_export.py).
 */
const exportOptions = [
  { label: 'XLS — Excel 97-2003', value: 'xls' },
  { label: 'XLSX — Excel 2007+', value: 'xlsx' },
  { label: 'DOC — Word 97-2003', value: 'doc' },
  { label: 'DOCX — Word 2007+', value: 'docx' },
  { label: 'PDF', value: 'pdf' },
  { label: 'ODT — LibreOffice/OpenOffice (документ)', value: 'odt' },
  { label: 'ODS — LibreOffice/OpenOffice (таблица)', value: 'ods' },
  { label: 'RTF — Rich Text', value: 'rtf' },
  { label: 'CSV — таблица (только текст)', value: 'csv' },
  { label: 'TXT — текст', value: 'txt' },
  { label: 'MD — Markdown', value: 'md' },
  { label: 'JSON — данные', value: 'json' }
]

/* Три частых формата — отдельными иконками, остальные уходят в «…». */
const fileBadges = [
  { value: 'pdf', badge: 'PDF', title: 'Скачать PDF' },
  { value: 'xlsx', badge: 'XLS', title: 'Скачать Excel (XLSX)' },
  { value: 'docx', badge: 'DOC', title: 'Скачать Word (DOCX)' }
]

const extraExportOptions = exportOptions.filter(
  option => !fileBadges.some(badge => badge.value === option.value)
)

function removeItem(item) {
  const snapshot = removeSurface(item.surfaceId)

  if (!snapshot) {
    return
  }

  notify('Позиция удалена', 'ok', {
    label: 'Вернуть',
    run: () => {
      if (restoreSurface(snapshot)) {
        notify('Позиция восстановлена.')
      }
    }
  })
}

/* Файл формируется на сервере и скачивается. */
async function exportAs(format) {
  if (!count.value) {
    return
  }

  busy.value = format

  try {
    await downloadPortfolio(format, items.value, {
      withPhotos: fullOutput.value,
      withMaps: fullOutput.value,
      fullOutput: fullOutput.value,
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

/* Печать: PDF (та же doc-раскладка), открывается и печатается. */
async function handlePrint() {
  if (!count.value) {
    return
  }

  busy.value = 'print'

  try {
    await printPortfolio(items.value, {
      withPhotos: fullOutput.value,
      withMaps: fullOutput.value,
      fullOutput: fullOutput.value,
      title: title.value,
      requisites: currentRequisites()
    })
    notify('Открываю версию для печати.')
  } catch (exc) {
    notify(
      exc && exc.message ? exc.message : 'Не удалось подготовить печать.',
      'error'
    )
  } finally {
    busy.value = ''
  }
}

/* Почта: mailto с темой и телом; адрес по умолчанию — с сайта. */
function handleEmail() {
  if (!count.value) {
    return
  }

  const result = emailPortfolio(items.value, {
    withMaps: fullOutput.value,
    fullOutput: fullOutput.value,
    title: title.value,
    requisites: currentRequisites()
  })

  notify(
    result?.truncated
      ? 'Письмо сокращено — полный список можно скопировать кнопкой «Скопировать».'
      : 'Открываю почтовый клиент.'
  )
}

/*
 * Ссылка на портфель.
 *
 * Переносится сам портфель — позиции и выбранные месяцы (?pf=…, см.
 * utils/portfolioLink.js). Фильтры в ссылку не попадают: получателю нужен
 * тот же набор позиций, а не чужая выдача. Алфавит токена берётся из
 * настройки сайта «Формат ссылок» — как у кнопки «Поделиться» в каталоге.
 */
const linkTip = ref(null)
const linkCopied = ref(false)
let linkCopiedTimer = null

function buildPortfolioLink() {
  const token = encodePortfolioLink(
    { items: items.value, title: title.value },
    urlStateTokenFormat.value
  )

  return `${window.location.origin}/vozmozhnosti?pf=${token}`
}

async function sharePortfolioLink() {
  if (!count.value) {
    return
  }

  let url

  try {
    url = buildPortfolioLink()
  } catch (exc) {
    notify(
      exc && exc.message
        ? `${exc.message} — выгрузите его файлом.`
        : 'Не удалось подготовить ссылку.',
      'error'
    )

    return
  }

  if (!(await copyToClipboard(url))) {
    notify('Не удалось скопировать ссылку — скопируйте её вручную.', 'error')

    return
  }

  linkCopied.value = true

  /* Подсказку показываем принудительно: копирование могло быть по хоткею. */
  if (linkTip.value) {
    linkTip.value.show()
  }

  if (linkCopiedTimer) {
    clearTimeout(linkCopiedTimer)
  }

  linkCopiedTimer = setTimeout(() => {
    linkCopied.value = false
    linkCopiedTimer = null

    if (linkTip.value) {
      linkTip.value.hide()
    }
  }, 2000)
}

onBeforeUnmount(() => {
  if (linkCopiedTimer) {
    clearTimeout(linkCopiedTimer)
    linkCopiedTimer = null
  }

  if (toastTimer) {
    clearTimeout(toastTimer)
    toastTimer = null
  }
})

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

/* ------------------------------------------------- заявка без кабинета */

const requestOpen = ref(false)
const requestSending = ref(false)
const requestDone = ref(false)
const requestError = ref('')
const requestForm = reactive({ name: '', phone: '', email: '', comment: '' })

/* Чем связываться: телефон или e-mail. Достаточно одного. */
const requestContactMode = ref('phone')
const requestFieldErrors = reactive({ name: '', contact: '' })

const requestNameRef = ref(null)
const requestPhoneRef = ref(null)
const requestEmailRef = ref(null)

function openRequest() {
  requestError.value = ''
  requestDone.value = false
  requestFieldErrors.name = ''
  requestFieldErrors.contact = ''
  requestOpen.value = true
}

function clearRequestFieldError(field) {
  requestFieldErrors[field] = ''
}

function setContactMode(mode) {
  if (requestContactMode.value === mode) {
    return
  }

  requestContactMode.value = mode
  requestFieldErrors.contact = ''

  /* Второе поле не отправляем — чистим, чтобы не осталось «мусора». */
  if (mode === 'phone') {
    requestForm.email = ''
  } else {
    requestForm.phone = ''
  }
}

/* Форматирование телефона — после ввода, а не по каждой цифре. */
function formatRequestPhone() {
  const formatted = normalizeRuPhone(requestForm.phone)

  if (formatted) {
    requestForm.phone = formatted
    requestFieldErrors.contact = ''
  }
}

/* Проверка формы: имя и один заполненный контакт. */
function validateRequestForm() {
  requestFieldErrors.name =
    requestForm.name.trim().length < 2 ? 'Укажите имя' : ''

  let contactValid = true

  if (requestContactMode.value === 'phone') {
    const phone = normalizeRuPhone(requestForm.phone)

    if (phone) {
      requestForm.phone = phone
      requestFieldErrors.contact = ''
    } else {
      requestFieldErrors.contact = 'Телефон в формате +7 (900) 000-00-00'
      contactValid = false
    }
  } else {
    const email = requestForm.email.trim().toLowerCase()

    if (isValidEmail(email)) {
      requestForm.email = email
      requestFieldErrors.contact = ''
    } else {
      requestFieldErrors.contact = 'Укажите корректный e-mail'
      contactValid = false
    }
  }

  return !requestFieldErrors.name && contactValid
}

/*
 * Позиции портфеля → короткий список для заявки.
 *
 * Лимит — только защитный (как у выгрузки на сервере, 500 позиций): раньше
 * стояло 60, и портфель больше 60 молча уходил менеджеру обрезанным, хотя
 * в диалоге было написано «N позиций из портфеля». Если позиций больше,
 * число ушедших видно прямо в диалоге (см. requestLimitNotice).
 */
const REQUEST_ITEMS_LIMIT = 500

function requestItems() {
  return items.value.slice(0, REQUEST_ITEMS_LIMIT).map(item => ({
    id: Number(item.surfaceId) || null,
    title: [item.type, item.address].filter(Boolean).join(' · ')
  }))
}

/* «1 позиция», «2 позиции», «80 позиций» — как в остальных счётчиках. */
const positionsWord = computed(() => {
  const value = Math.abs(Number(count.value) || 0)
  const mod10 = value % 10
  const mod100 = value % 100

  if (mod10 === 1 && mod100 !== 11) {
    return 'позиция'
  }

  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) {
    return 'позиции'
  }

  return 'позиций'
})

/* В заявку уходит не больше REQUEST_ITEMS_LIMIT позиций — предупреждаем. */
const requestLimitNotice = computed(() =>
  count.value > REQUEST_ITEMS_LIMIT
    ? `В заявку уйдут первые ${REQUEST_ITEMS_LIMIT} позиций — остальные выгрузите файлом.`
    : ''
)

async function submitRequest() {
  requestError.value = ''

  if (!validateRequestForm()) {
    /* Ведём курсор к первой проблеме, а не оставляем человека гадать. */
    if (requestFieldErrors.name) {
      requestNameRef.value?.focus()
    } else if (requestContactMode.value === 'phone') {
      requestPhoneRef.value?.focus()
    } else {
      requestEmailRef.value?.focus()
    }

    return
  }

  requestSending.value = true

  try {
    const response = await fetch('/api/requests', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: requestForm.name.trim(),
        phone: requestContactMode.value === 'phone' ? requestForm.phone : '',
        email: requestContactMode.value === 'email' ? requestForm.email : '',
        comment: requestForm.comment.trim(),
        items: requestItems()
      })
    })

    const data = await response.json().catch(() => null)

    if (!response.ok) {
      throw new Error(data?.detail || 'Не удалось отправить заявку')
    }

    requestDone.value = true
    requestForm.comment = ''
  } catch (exc) {
    requestError.value = String(exc?.message || exc)
  } finally {
    requestSending.value = false
  }
}

/* Очистка портфеля: подтверждаем окном страницы, а не нативным confirm. */
const clearDialog = ref(false)

function handleClear() {
  if (!count.value) {
    return
  }

  clearDialog.value = true
}

function confirmClear() {
  clearDialog.value = false
  clear()
  notify('Портфель очищен.')
}
</script>

<style scoped>
/* Диалог подтверждения очистки портфеля. */
.portfolio-clear-dialog {
  width: min(420px, calc(100vw - 32px));
  border-radius: 14px;
}

.portfolio-clear-title {
  margin-bottom: 6px;
  color: #17212b;
  font-size: 16px;
  font-weight: 800;
}

.portfolio-clear-text {
  color: #52606a;
  font-size: 13px;
  line-height: 1.45;
}

/* Диалог заявки (без личного кабинета). */
.request-card {
  width: min(480px, calc(100vw - 32px));
}

.request-title {
  margin-bottom: 6px;
  font-size: 17px;
  font-weight: 800;
}

.request-hint {
  margin: 0 0 12px;
  color: #6b6b6b;
  font-size: 13px;
  line-height: 1.4;
}

.request-card .q-field + .q-field {
  margin-top: 8px;
}

/* Переключатель «Телефон / E-mail» над полем контакта. */
.request-contact-switch {
  display: inline-flex;
  gap: 2px;

  margin: 10px 0 0;
  padding: 3px;

  border-radius: 9px;

  background: #f0f3f4;
}

.request-contact-switch button {
  padding: 5px 12px;

  border: 0;
  border-radius: 7px;

  background: transparent;
  color: #5b6873;

  cursor: pointer;

  font-family: inherit;
  font-size: 11px;
  font-weight: 800;
}

.request-contact-switch button.active {
  background: #fff;
  color: #17212b;

  box-shadow: 0 1px 4px rgba(23, 33, 43, 0.12);
}

.request-contact-switch + .q-field {
  margin-top: 8px;
}

.request-error,
.request-ok {
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
}

.request-error {
  border: 1px solid #e57373;
  background: #fdecea;
  color: #c62828;
}

.request-ok {
  border: 1px solid #a5d6a7;
  background: #e8f5e9;
  color: #2e7d32;
}

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

  /* Панель не прокручивается целиком: шапка и нижний блок действий
     зафиксированы, прокручивается только список позиций (см. ниже).
     Иначе при большом числе позиций терялось нижнее поле с кнопками. */
  overflow: hidden;

  padding: 16px 18px;
}

/*
 * В дропдауне список позиций — единственная прокручиваемая область.
 * flex: 1 + min-height: 0 заставляют его занять остаток высоты и
 * скроллиться, не растягивая панель.
 */
.portfolio-panel--dropdown .portfolio-list {
  flex: 1 1 auto;
  min-height: 0;

  overflow-y: auto;

  /* Небольшой отступ, чтобы скроллбар не лип к карточкам. */
  padding-right: 4px;
  margin-right: -4px;
}

/* Шапка, название, итог и блок действий не сжимаются — они всегда видны. */
.portfolio-panel--dropdown .portfolio-head,
.portfolio-panel--dropdown .portfolio-title,
.portfolio-panel--dropdown .portfolio-total,
.portfolio-panel--dropdown .portfolio-actions,
.portfolio-panel--dropdown .portfolio-empty {
  flex-shrink: 0;
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
  color: #5f6c76;

  font-size: 11px;
  line-height: 1.4;
}

.portfolio-panel--dropdown .portfolio-title-hint {
  font-size: 10px;
}

/* --------------------------------------------------------- Пусто */

.portfolio-empty {
  padding: 16px 4px;

  color: #5b6873;

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
  /* Колонки превью (96px) и правого столбца (96px) фиксированы, поэтому
     превью и цена/«Убрать» во всех строках встают на одну вертикальную ось
     (раньше ширина правой колонки «auto» зависела от длины цены и смещала
     колонку фото). */
  grid-template-columns: 26px minmax(0, 1fr) 96px 96px;

  gap: 10px;

  padding: 10px 12px;

  border: 1px solid #eef1f3;
  border-radius: 12px;

  background: #fafbfc;
}

/* Маленькое превью позиции. */
.portfolio-row-photo {
  display: block;

  width: 96px;
  aspect-ratio: 16 / 10;

  /* По вертикальному центру строки (иначе превью прижималось к верху). */
  align-self: center;

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

/* Плейсхолдер без фото — только держит колонку, невидим. */
.portfolio-row-photo--empty {
  border: 0;
  background: transparent;
}

.portfolio-row-photo img {
  display: block;
  width: 100%;
  height: 100%;

  object-fit: cover;
}

.portfolio-row-num {
  color: #5b6873;

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

  color: #5b6873;

  font-size: 11px;
  font-weight: 700;
}

.portfolio-no-months {
  color: #9a6b00;
  font-weight: 800;
}

.portfolio-months {
  display: flex;
  flex-wrap: wrap;

  gap: 4px;

  margin-top: 8px;
}

/* Месяц — кнопка: клик добавляет или убирает его. */
.portfolio-month {
  display: inline-flex;
  align-items: center;

  gap: 4px;

  padding: 3px 6px;

  border: 0;
  border-radius: 6px;

  background: #eef1f3;
  color: #5f6c76;

  font-family: inherit;
  font-size: 9px;
  font-weight: 900;

  letter-spacing: 0.04em;

  white-space: nowrap;

  cursor: pointer;
  transition: 0.15s ease;
}

/*
 * Статус месяца — та же палитра, что на карточках карты:
 * свободно — зелёный, резерв — янтарный, занято — красный.
 * (Идут до .is-selected, чтобы выбранный месяц перекрывал цвет статуса.)
 */
.portfolio-month.state-free {
  background: #dff3e4;
  color: #16803a;
}

.portfolio-month.state-reserve {
  background: #fff0d2;
  color: #b96b00;
}

.portfolio-month.state-busy {
  background: #f9dede;
  color: #c62828;
}

/* Свободный месяц кликабелен: клик добавляет и убирает его. */
.portfolio-month.state-free:hover:not(.is-disabled) {
  filter: brightness(0.95);
}

/* Занятые и резервные добавить нельзя — цвет статуса оставляем читаемым. */
.portfolio-month.is-disabled {
  opacity: 0.8;
  cursor: not-allowed;
}

.portfolio-month.is-selected {
  background: var(--albion-accent);
  color: #fff;
}

.portfolio-month.is-selected:hover {
  filter: brightness(0.94);
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

.portfolio-action {
  border-radius: 8px;

  font-size: 11px;
  font-weight: 800;

  letter-spacing: 0.02em;
}

/* «Очистить» — отдельно от группы: прижата к правому краю строки. */
.portfolio-action--danger {
  margin-left: auto;

  color: #c62828;
}

/*
 * Иконки вывода и действий: три формата (PDF/XLSX/DOCX), «…» для
 * редких, принтер, почта и ссылка на портфель.
 */
.portfolio-icons {
  display: flex;
  align-items: center;

  gap: 2px;
}

/* Статус долгой операции (сборка файла на сервере). */
.portfolio-busy {
  color: #607d8b;

  font-size: 11px;
  white-space: nowrap;
}

.portfolio-icon {
  min-width: 28px;
  min-height: 28px;
  padding: 0 5px;

  border-radius: 8px;

  color: #455a64;
}

/* Бейджи форматов: буквы вместо картинок — узнаваемо и без внешних файлов. */
.portfolio-file-badge {
  padding: 2px 4px;

  border-radius: 4px;

  font-size: 9px;
  font-weight: 800;
  line-height: 1.2;

  letter-spacing: 0.02em;
}

.portfolio-file-badge.is-pdf {
  background: #fdecea;

  color: #c62828;
}

.portfolio-file-badge.is-xlsx {
  background: #e6f4ea;

  color: #1e6f43;
}

.portfolio-file-badge.is-docx {
  background: #e8eefb;

  color: #2b579a;
}

/* «…» — единственный символ, поэтому крупнее буквенных бейджей. */
.portfolio-more {
  font-size: 16px;
  font-weight: 800;
  line-height: 1;

  color: #546e7a;
}

/* Обёртка «Сохранить»: нужна, чтобы тултип показывался и когда кнопка
   задизейблена (disabled-элементы не принимают наведение). */
.portfolio-save-wrap {
  display: inline-flex;
}

/* Гасим указатель у выключенной кнопки — наведение ловит обёртка,
   и тултип «Войдите в личный кабинет» показывается. */
.portfolio-save-wrap .q-btn--disabled {
  pointer-events: none;
}

/* Список редких форматов («…») — с прокруткой. */
.portfolio-export-menu {
  max-height: 320px;
  overflow-y: auto;
}

/* Пункты меню — тем же кеглем и весом, что подписи кнопок портфеля,
   чтобы меню выглядело компактнее. */
.portfolio-export-menu :deep(.q-item__label) {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
}

.portfolio-export-menu :deep(.q-item) {
  min-height: 30px;
  padding-top: 2px;
  padding-bottom: 2px;
}

/* Галочка «Фото» — по размеру кнопок действий. */
.portfolio-photos-toggle {
  align-self: center;

  font-size: 11px;
  font-weight: 800;

  letter-spacing: 0.02em;
}

/*
 * Подпись «Полный вывод» — жирная (жирнее «Фото»/«Карта»). Класс задаёт
 * вес только этой подписи; шрифт остальных галочек не меняется.
 */
/*
 * Переключатель режима вывода. Подпись меняется («Краткий вывод» /
 * «Полный вывод») и намеренно отличается от галочек «Фото»/«Карта»:
 * отделена чертой, набрана прописными и акцентным цветом.
 */
.portfolio-full-output-toggle {
  padding-left: 10px;
  margin-left: 2px;

  border-left: 1px solid #dfe6ea;
}

.portfolio-full-output-toggle :deep(.q-checkbox__label) {
  color: var(--albion-accent);

  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* --------------------------------------------------------- Тост */

/* Предупреждение в диалоге заявки: портфель больше лимита заявки. */
.request-hint--warn {
  color: #b3261e;
}

.portfolio-toast {
  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 12px;

  padding: 9px 12px;

  border-radius: 9px;

  font-size: 12px;
  font-weight: 700;
}

.portfolio-toast-action {
  padding: 0;

  border: 0;
  background: transparent;

  color: inherit;

  cursor: pointer;

  font-size: 12px;
  font-weight: 900;
  text-decoration: underline;
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
