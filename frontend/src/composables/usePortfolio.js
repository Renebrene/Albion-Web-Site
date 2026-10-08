import { computed, reactive, ref, watch } from 'vue'

import { useAccount } from './useAccount'

/*
 * Портфель — корзина избранных поверхностей.
 *
 * Состояние общее для всего приложения (singleton): модульные ref
 * создаются один раз, поэтому список избранного в шапке, на карточке
 * поверхности и на странице портфеля всегда синхронны.
 *
 * Позиция портфеля:
 *   {
 *     surfaceId, address, city, side, type, size, photo,
 *     months: { [monthFull]: { price, addedAt, stale } },
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

// «Паспортные» поля позиции, которые берутся из конструкции.
const PASSPORT_FIELDS = ['address', 'city', 'side', 'type', 'size', 'photo']

// Экземпляр ЛК нужен для реактивной проверки авторизации.
const { isAuthenticated } = useAccount()

// ---------------------------------------------------------------- состояние

const items = ref([])

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

// Пустой статус и «Свободно» (в любом регистре) считаются свободными.
function isFreeStatus(value) {
  const status = String(value ?? '')
    .trim()
    .toLowerCase()

  return status === '' || status === 'свободно'
}

/*
 * Нормализует plain-позицию к внутреннему виду.
 * Возвращает null, если surfaceId не является числом.
 */
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
    addedAt: raw.addedAt || null
  }

  PASSPORT_FIELDS.forEach(field => {
    item[field] = raw[field] ? String(raw[field]) : ''
  })

  return item
}

// ---------------------------------------------------------------- чтение

function findItem(surfaceId) {
  const key = keyOf(surfaceId)

  return items.value.find(item => keyOf(item.surfaceId) === key) || null
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
      addedAt: nowIso()
    }

    PASSPORT_FIELDS.forEach(field => {
      item[field] = surface[field] ? String(surface[field]) : ''
    })

    items.value.push(item)
  }

  if (item.months[monthFull]) {
    delete item.months[monthFull]

    /*
     * Снят последний месяц — позиция больше не нужна: убираем её
     * целиком, чтобы счётчик отражал реальное число выбранных
     * поверхностей.
     */
    if (Object.keys(item.months).length === 0) {
      removeSurface(surfaceId)
    }

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

function removeSurface(surfaceId) {
  const key = keyOf(surfaceId)

  items.value = items.value.filter(item => keyOf(item.surfaceId) !== key)
  delete selectionMode[key]
}

function clear() {
  items.value = []

  Object.keys(selectionMode).forEach(key => {
    delete selectionMode[key]
  })
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

    Object.keys(item.months).forEach(monthFull => {
      const month = item.months[monthFull]

      if (!month) {
        return
      }

      month.stale = !isFreeStatus(construction.statuses?.[monthFull])

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

    return hydrate({
      version: 1,
      items: Array.isArray(data && data.items) ? data.items : []
    })
  } catch {
    return false
  }
}

async function saveToAccount() {
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
      body: JSON.stringify({ items: serialize().items })
    })

    return response.ok
  } catch {
    return false
  }
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

  try {
    const response = await fetch(`${API_URL}/account/portfolio`, {
      headers: { Authorization: `Bearer ${token}` }
    })

    if (response.ok) {
      const data = await response.json()
      serverItems = Array.isArray(data && data.items) ? data.items : []
    }
  } catch {
    return false
  }

  items.value = mergeItems(items.value, serverItems)
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

// ---------------------------------------------------------------- автосохранение

let saveTimer = null

watch(
  items,
  () => {
    saveLocal()

    if (!isAuthenticated.value) {
      return
    }

    if (saveTimer) {
      clearTimeout(saveTimer)
    }

    saveTimer = setTimeout(() => {
      saveTimer = null
      saveToAccount()
    }, SAVE_DEBOUNCE_MS)
  },
  { deep: true }
)

// ---------------------------------------------------------------- публичный API

export function usePortfolio() {
  return {
    // состояние
    items,
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
    removeSurface,
    clear,
    syncWithConstructions,

    // (де)сериализация и хранение
    serialize,
    hydrate,
    loadLocal,
    saveLocal,

    // синхронизация с ЛК
    loadFromAccount,
    saveToAccount,
    mergeFromAccount
  }
}
