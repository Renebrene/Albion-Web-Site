import { computed, nextTick, reactive, ref, watch } from 'vue'

import { useAccount } from './useAccount'
import { isFree } from '../utils/availability'

/*
 * Портфель — корзина избранных поверхностей.
 *
 * Состояние общее для всего приложения (singleton): модульные ref
 * создаются один раз, поэтому список избранного в шапке, на карточке
 * поверхности и на странице портфеля всегда синхронны.
 *
 * Позиция портфеля:
 *   {
 *     surfaceId, address, city, side, type, size,
 *     photo, photo_thumb, photo_large,
 *     map_card, map_thumb, map_large,
 *     months: { [monthFull]: { price, addedAt, stale } },
 *     // Снимки для статуса/цен по ВСЕМ месяцам (не только выбранным):
 *     prices: { [monthFull]: number|null },
 *     statuses: { [monthFull]: string },   // нормализованный статус
 *     monthTexts: { [monthFull]: string }, // сырой текст месяцев (как на карте)
 *     addedAt
 *   }
 *
 * monthFull — полное русское имя месяца («Октябрь») — как ключи
 * в statuses/month_prices объекта конструкции из GET /api/constructions.
 */

const STORAGE_KEY = 'albion_portfolio'
const TOKEN_KEY = 'albion_account_token'
const API_URL = '/api'
const SAVE_DEBOUNCE_MS = 1000

// Название портфеля — попадает в распечатку/выгрузку/копирование.
// Ограничение длины, чтобы не раздувать заголовки файлов и письма.
const TITLE_MAX = 120

// «Паспортные» поля позиции, которые берутся из конструкции.
// Три варианта фото нужны, чтобы не тянуть оригинал: миниатюра — в списке
// портфеля и печати, крупный — только в полноэкранном просмотре.
const PASSPORT_FIELDS = [
  'address',
  'city',
  'side',
  'type',
  'size',
  'photo',
  'photo_thumb',
  'photo_large',
  'map',
  'map_card',
  'map_thumb',
  'map_large'
]

// Экземпляр ЛК нужен для реактивной проверки авторизации.
const { isAuthenticated } = useAccount()

// ---------------------------------------------------------------- состояние

const items = ref([])

// Название портфеля (для распечатки/выгрузки/копирования).
const title = ref('')

/*
 * Название портфеля, СОХРАНЁННОГО в личном кабинете (не текущего).
 * Нужно странице ЛК: она показывает, что именно лежит на сервере.
 */
const accountTitle = ref('')

// Дата последнего сохранения портфеля в ЛК (ISO-строка) — для фильтра по дате.
const accountPortfolioUpdatedAt = ref('')

// surfaceId (в виде строки) -> true, если включён режим выбора месяцев.
const selectionMode = reactive({})

// Число позиций (поверхностей), а не месяцев.
const count = computed(() => items.value.length)

// Сумма price по всем выбранным месяцам всех позиций.
const totalPrice = computed(() =>
  items.value.reduce((sum, item) => {
    const months = item.months || {}

    return (
      sum +
      Object.values(months).reduce(
        (monthSum, month) => monthSum + (toNumber(month && month.price) || 0),
        0
      )
    )
  }, 0)
)

// ---------------------------------------------------------------- утилиты

function keyOf(surfaceId) {
  return String(surfaceId)
}

// Приводит идентификатор поверхности к числу (или null).
function toSurfaceId(value) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string' && value.trim() !== '') {
    const num = Number(value.trim())

    if (Number.isFinite(num)) {
      return num
    }
  }

  return null
}

// Приводит цену к числу: «100 000», «1 500,50» -> 100000, 1500.5.
// Пусто/некорректно -> null.
function toNumber(value) {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }

  const text = String(value).trim()

  if (text === '') {
    return null
  }

  const num = Number(text.replace(/\s/g, '').replace(',', '.'))

  return Number.isFinite(num) ? num : null
}

/*
 * Название портфеля: строка без крайних пробелов, не длиннее TITLE_MAX.
 * Пусто/не строку приводит к ''.
 */
function normalizeTitle(value) {
  return String(value ?? '')
    .trim()
    .slice(0, TITLE_MAX)
}

function cloneDeep(value) {
  try {
    return JSON.parse(JSON.stringify(value))
  } catch {
    return null
  }
}

function nowIso() {
  return new Date().toISOString()
}

function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

/*
 * Нормализует plain-позицию к внутреннему виду.
 * Возвращает null, если surfaceId не является числом.
 */
/*
 * Снимок цен по всем месяцам поверхности.
 *
 * Нужен, чтобы месяцы можно было переключать прямо в панели портфеля —
 * без обращения к каталогу конструкций (панель доступна на любой
 * странице, где каталог может быть не загружен).
 */
function monthPricesOf(surface) {
  const prices = {}

  Object.entries(surface?.month_prices || {}).forEach(([month, value]) => {
    prices[month] = toNumber(value)
  })

  return prices
}

function monthStatusesOf(surface) {
  const statuses = {}

  Object.entries(surface?.statuses || {}).forEach(([month, value]) => {
    statuses[month] = String(value ?? '')
  })

  return statuses
}

/*
 * Сырой текст доступности месяцев из поля `months` конструкции
 * («33%», «Резерв до 17.08», «Свободно»).
 *
 * Карта и список читают статус ИМЕННО отсюда — getMonthValue отдаёт
 * приоритет `months`, а `statuses` берёт лишь как запасной вариант.
 * Поэтому портфель хранит такой же снимок: иначе статусы расходятся
 * (например, у видеоэкранов, где `months` = «8%», а `statuses` =
 * «Доступность»).
 *
 * ВНИМАНИЕ: не путать с item.months — там лежат ВЫБРАННЫЕ месяцы.
 */
function monthTextsOf(surface) {
  const texts = {}

  Object.entries(surface?.months || {}).forEach(([month, value]) => {
    texts[month] = String(value ?? '')
  })

  return texts
}

function normalizeMonthTexts(raw) {
  const texts = {}

  if (raw && typeof raw === 'object') {
    Object.entries(raw).forEach(([month, value]) => {
      texts[month] = String(value ?? '')
    })
  }

  return texts
}

function normalizePrices(raw) {
  const prices = {}

  if (raw && typeof raw === 'object') {
    Object.entries(raw).forEach(([month, value]) => {
      prices[month] = toNumber(value)
    })
  }

  return prices
}

function normalizeStatuses(raw) {
  const statuses = {}

  if (raw && typeof raw === 'object') {
    Object.entries(raw).forEach(([month, value]) => {
      statuses[month] = String(value ?? '')
    })
  }

  return statuses
}

function normalizeItem(raw) {
  if (!raw || typeof raw !== 'object') {
    return null
  }

  const surfaceId = toSurfaceId(raw.surfaceId)

  if (surfaceId === null) {
    return null
  }

  const months = {}
  const rawMonths = raw.months

  if (rawMonths && typeof rawMonths === 'object') {
    Object.entries(rawMonths).forEach(([monthFull, value]) => {
      if (!value || typeof value !== 'object') {
        return
      }

      months[monthFull] = {
        price: toNumber(value.price),
        addedAt: value.addedAt || null,
        stale: Boolean(value.stale)
      }
    })
  }

  const item = {
    surfaceId,
    months,
    addedAt: raw.addedAt || null,
    prices: normalizePrices(raw.prices),
    statuses: normalizeStatuses(raw.statuses),
    monthTexts: normalizeMonthTexts(raw.monthTexts)
  }

  PASSPORT_FIELDS.forEach(field => {
    item[field] = raw[field] ? String(raw[field]) : ''
  })

  return item
}

// ---------------------------------------------------------------- чтение

/* Индекс по surfaceId: частые isMonthSelected/isInPortfolio больше не O(n). */
const itemsByKey = computed(() => {
  const map = new Map()

  for (const item of items.value) {
    map.set(keyOf(item.surfaceId), item)
  }

  return map
})

function findItem(surfaceId) {
  return itemsByKey.value.get(keyOf(surfaceId)) || null
}

function isInPortfolio(surfaceId) {
  return findItem(surfaceId) !== null
}

function isMonthSelected(surfaceId, monthFull) {
  const item = findItem(surfaceId)

  return Boolean(item && item.months && item.months[monthFull])
}

function isSelectionMode(surfaceId) {
  return Boolean(selectionMode[keyOf(surfaceId)])
}

// ---------------------------------------------------------------- изменение

function toggleSelectionMode(surfaceId) {
  const key = keyOf(surfaceId)

  selectionMode[key] = !selectionMode[key]
}

/*
 * Добавляет/убирает пару (поверхность, месяц).
 *
 * Если позиции с таким surfaceId ещё нет — создаёт её из объекта
 * конструкции (поля id/address/city/side/type/size/photo).
 */
function toggleMonth(surface, monthFull, price) {
  if (!surface || !monthFull) {
    return
  }

  const surfaceId = toSurfaceId(surface.id)

  if (surfaceId === null) {
    return
  }

  let item = findItem(surfaceId)

  if (!item) {
    item = {
      surfaceId,
      months: {},
      addedAt: nowIso(),
      prices: monthPricesOf(surface),
      statuses: monthStatusesOf(surface),
      monthTexts: monthTextsOf(surface)
    }

    PASSPORT_FIELDS.forEach(field => {
      item[field] = surface[field] ? String(surface[field]) : ''
    })

    items.value.push(item)
  }

  /* Позиция из localStorage могла сохраниться без снимка цен. */
  if (!Object.keys(item.prices || {}).length) {
    item.prices = monthPricesOf(surface)
  }

  if (!Object.keys(item.statuses || {}).length) {
    item.statuses = monthStatusesOf(surface)
  }

  if (!Object.keys(item.monthTexts || {}).length) {
    item.monthTexts = monthTextsOf(surface)
  }

  if (item.months[monthFull]) {
    delete item.months[monthFull]

    /*
     * Позицию НЕ удаляем, даже если снят последний месяц: конструкция
     * остаётся в портфеле, а в выводе для неё пишется «ничего не выбрано».
     */
    return
  }

  const monthPrice =
    price !== undefined
      ? toNumber(price)
      : toNumber(surface.month_prices?.[monthFull])

  item.months[monthFull] = {
    price: monthPrice,
    addedAt: nowIso(),
    stale: false
  }
}

/*
 * Переключить месяц прямо в панели портфеля — без карточки.
 *
 * Цену и статус берём из снимка позиции (prices/statuses), который
 * заполняется при добавлении поверхности и обновляется при загрузке
 * каталога. Поэтому панель работает и там, где каталог не загружен.
 */
function toggleItemMonth(surfaceId, monthFull) {
  const item = findItem(surfaceId)

  if (!item || !monthFull) {
    return
  }

  if (item.months[monthFull]) {
    delete item.months[monthFull]

    /* Позиция остаётся в списке даже без выбранных месяцев. */
    return
  }

  item.months[monthFull] = {
    price: toNumber(item.prices?.[monthFull]),
    addedAt: nowIso(),
    stale: false
  }
}

/* Известна ли цена месяца у позиции (для панели портфеля). */
function monthPriceOf(surfaceId, monthFull) {
  const item = findItem(surfaceId)

  return item ? toNumber(item.prices?.[monthFull]) : null
}

function removeSurface(surfaceId) {
  const key = keyOf(surfaceId)

  items.value = items.value.filter(item => keyOf(item.surfaceId) !== key)
  delete selectionMode[key]
}

function clear() {
  items.value = []
  title.value = ''

  Object.keys(selectionMode).forEach(key => {
    delete selectionMode[key]
  })
}

/*
 * Название портфеля снаружи (панель). Значение триммится и
 * обрезается до TITLE_MAX; сохранение в localStorage/ЛК подхватит watch.
 */
function setTitle(value) {
  title.value = normalizeTitle(value)
}

/*
 * Синхронизация с актуальным списком конструкций.
 *
 * Обновляет «паспортные» поля позиций и помечает месяц stale,
 * если он больше не «Свободно»; цену берёт из month_prices.
 */
function syncWithConstructions(constructions) {
  if (!Array.isArray(constructions)) {
    return
  }

  const byId = new Map(
    constructions.map(construction => [keyOf(construction?.id), construction])
  )

  items.value.forEach(item => {
    const construction = byId.get(keyOf(item.surfaceId))

    if (!construction) {
      return
    }

    PASSPORT_FIELDS.forEach(field => {
      item[field] = construction[field] ? String(construction[field]) : ''
    })

    /* Обновляем снимок цен/статусов по всем месяцам, не только выбранным. */
    Object.entries(monthPricesOf(construction)).forEach(([month, price]) => {
      if (price !== null) {
        item.prices[month] = price
      }
    })

    item.statuses = { ...item.statuses, ...monthStatusesOf(construction) }
    item.monthTexts = { ...item.monthTexts, ...monthTextsOf(construction) }

    Object.keys(item.months).forEach(monthFull => {
      const month = item.months[monthFull]

      if (!month) {
        return
      }

      /* Свободность — по той же логике, что на карте и в списке. */
      month.stale = !isFree(construction, monthFull)

      const price = toNumber(construction.month_prices?.[monthFull])

      if (price !== null) {
        month.price = price
      }
    })
  })
}

// ---------------------------------------------------------------- сериализация

function serialize() {
  const plain = cloneDeep(items.value)

  return {
    version: 1,
    title: normalizeTitle(title.value),
    items: Array.isArray(plain) ? plain : []
  }
}

function hydrate(data) {
  if (!data || typeof data !== 'object' || !Array.isArray(data.items)) {
    return false
  }

  const next = []

  data.items.forEach(raw => {
    const item = normalizeItem(raw)

    if (item) {
      next.push(item)
    }
  })

  items.value = next

  // Название восстанавливаем вместе со списком; нет в данных — пустая строка.
  title.value = normalizeTitle(data.title)

  return true
}

// ---------------------------------------------------------------- localStorage

function loadLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)

    if (!raw) {
      return false
    }

    return hydrate(JSON.parse(raw))
  } catch {
    return false
  }
}

function saveLocal() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(serialize()))

    return true
  } catch {
    return false
  }
}

// ---------------------------------------------------------------- синхронизация с ЛК

async function loadFromAccount() {
  const token = getToken()

  if (!token) {
    return false
  }

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (!response.ok) {
      return false
    }

    const data = await response.json()

    // Непустой серверный заголовок применяется; пустой — не затирает локальный.
    const serverTitle = normalizeTitle(data && data.title)

    accountTitle.value = serverTitle

    return hydrate({
      version: 1,
      title: serverTitle || title.value,
      items: Array.isArray(data && data.items) ? data.items : []
    })
  } catch {
    return false
  }
}

/*
 * Читает сохранённый в ЛК портфель, НЕ трогая текущий список.
 * Нужно странице личного кабинета, чтобы показать, что сохранено.
 */
async function fetchAccountPortfolio() {
  const token = getToken()

  if (!token) {
    return []
  }

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (!response.ok) {
      return []
    }

    const data = await response.json()

    /*
     * Функция только читает: не меняем общий title, иначе watch
     * автосохранения отправит текущий (возможно пустой) портфель поверх
     * серверного. Возвращаем массив позиций, как ждёт страница ЛК.
     */
    const serverTitle = normalizeTitle(data && data.title)

    accountTitle.value = serverTitle
    accountPortfolioUpdatedAt.value = (data && data.updated_at) || ''

    const list = Array.isArray(data && data.items) ? data.items : []

    return list.map(normalizeItem).filter(Boolean)
  } catch {
    return []
  }
}

/*
 * Очищает сохранённый в ЛК портфель (только список ЛК).
 * Текущий рабочий портфель в памяти не трогаем.
 */
async function clearAccountPortfolio() {
  const token = getToken()

  if (!token) {
    return false
  }

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.ok) {
      accountPortfolioUpdatedAt.value = ''

      /*
       * Чистим и локальный портфель вместе с режимами выбора: иначе на
       * карте и в списке остаются подсвеченные кнопки «Портфель» и
       * выбранные месяцы, хотя портфель уже пуст.
       */
      clear()
    }

    return response.ok
  } catch {
    return false
  }
}

async function putAccountPortfolio() {
  const token = getToken()

  if (!token) {
    return false
  }

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        title: normalizeTitle(title.value),
        items: serialize().items
      })
    })

    /* Сохранили — значит в ЛК лежит именно это название. */
    if (response.ok) {
      accountTitle.value = normalizeTitle(title.value)
    }

    return response.ok
  } catch {
    return false
  }
}

/*
 * Все PUT идут через одну цепочку: и автосохранение, и ручная кнопка
 * «Сохранить». Иначе два запроса могут завершиться не по порядку и
 * старый ответ затрёт более новый портфель на сервере.
 */
let accountSaveChain = Promise.resolve()

function saveToAccount() {
  const run = accountSaveChain.then(putAccountPortfolio)

  accountSaveChain = run.catch(() => false)

  return run
}

/*
 * Слияние двух списков по surfaceId.
 *
 * Месяцы объединяются; при конфликте остаётся запись
 * с более поздним addedAt (то же правило для позиции целиком).
 */
function mergeItems(localItems, serverItems) {
  const merged = new Map()

  function absorb(list) {
    if (!Array.isArray(list)) {
      return
    }

    list.forEach(raw => {
      const item = normalizeItem(raw)

      if (!item) {
        return
      }

      const key = keyOf(item.surfaceId)
      const existing = merged.get(key)

      if (!existing) {
        merged.set(key, item)
        return
      }

      // Паспортные поля: дополняем пустые значения.
      PASSPORT_FIELDS.forEach(field => {
        if (!existing[field] && item[field]) {
          existing[field] = item[field]
        }
      })

      // Позиция берёт более поздний addedAt.
      if ((item.addedAt || '') > (existing.addedAt || '')) {
        existing.addedAt = item.addedAt
      }

      // Месяцы: объединение, конфликт решает addedAt.
      Object.entries(item.months).forEach(([monthFull, month]) => {
        const current = existing.months[monthFull]

        if (!current || (month.addedAt || '') > (current.addedAt || '')) {
          existing.months[monthFull] = month
        }
      })
    })
  }

  absorb(localItems)
  absorb(serverItems)

  return Array.from(merged.values())
}

async function mergeFromAccount() {
  const token = getToken()

  if (!token) {
    return false
  }

  let serverItems = []
  let serverTitle = ''

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.ok) {
      const data = await response.json()
      serverItems = Array.isArray(data && data.items) ? data.items : []
      serverTitle = normalizeTitle(data && data.title)
      accountTitle.value = serverTitle
    }
  } catch {
    return false
  }

  items.value = mergeItems(items.value, serverItems)

  // Если на клиенте названия нет — берём серверное.
  if (!title.value && serverTitle) {
    title.value = serverTitle
  }

  saveLocal()

  return true
}

// ---------------------------------------------------------------- инициализация

/*
 * Подхватываем локальные данные сразу при импорте модуля (клиент).
 * Делаем это ДО включения автосохранения, чтобы начальная загрузка
 * не отправлялась на сервер и не затёрла серверный портфель.
 */
loadLocal()

/*
 * Другая вкладка изменила портфель — подхватываем её состояние и не
 * пишем его обратно (иначе вкладки затирают друг друга).
 */
let applyingExternalStorage = false

if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key !== STORAGE_KEY || !event.newValue) {
      return
    }

    try {
      applyingExternalStorage = true
      hydrate(JSON.parse(event.newValue))

      nextTick(() => {
        applyingExternalStorage = false
      })
    } catch {
      applyingExternalStorage = false
    }
  })
}

// ---------------------------------------------------------------- автосохранение

let saveTimer = null
let saveInFlight = false
let saveQueued = false

/*
 * Последовательная отправка: одновременно выполняется не больше одного
 * PUT. Иначе при быстрых изменениях более старый запрос мог завершиться
 * позже нового и затереть актуальный портфель на сервере.
 */
async function flushAccountSave() {
  if (!isAuthenticated.value) {
    return
  }

  if (saveInFlight) {
    saveQueued = true
    return
  }

  saveInFlight = true

  try {
    do {
      saveQueued = false

      const ok = await saveToAccount()

      /* Ошибку не ретраим в цикле: следующий PUT запланирует изменение. */
      if (!ok) {
        saveQueued = false
        break
      }
    } while (saveQueued && isAuthenticated.value)
  } finally {
    saveInFlight = false
  }
}

watch(
  [items, title],
  () => {
    /* Состояние из другой вкладки не пересохраняем обратно. */
    if (applyingExternalStorage) {
      return
    }

    saveLocal()

    if (!isAuthenticated.value) {
      return
    }

    if (saveTimer) {
      clearTimeout(saveTimer)
    }

    saveTimer = setTimeout(() => {
      saveTimer = null
      void flushAccountSave()
    }, SAVE_DEBOUNCE_MS)
  },
  { deep: true }
)

// ---------------------------------------------------------------- публичный API

export function usePortfolio() {
  return {
    // состояние
    items,
    title,
    accountTitle,
    count,
    totalPrice,
    selectionMode,

    // чтение
    isInPortfolio,
    isMonthSelected,
    isSelectionMode,

    // изменение
    toggleSelectionMode,
    toggleMonth,
    toggleItemMonth,
    monthPriceOf,
    removeSurface,
    clear,
    setTitle,
    syncWithConstructions,

    // (де)сериализация и хранение
    serialize,
    hydrate,
    loadLocal,
    saveLocal,

    // синхронизация с ЛК
    loadFromAccount,
    saveToAccount,
    mergeFromAccount,
    fetchAccountPortfolio,
    accountPortfolioUpdatedAt,
    clearAccountPortfolio
  }
}
