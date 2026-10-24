import { computed, nextTick, reactive, ref, watch } from 'vue'

import { useAccount } from './useAccount'
import { isFree } from '../utils/availability'
import {
  groupByPoint,
  groupSides,
  sideLabel,
  parentSide
} from '../utils/constructionGroups'

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
 *     // Позиция — СТОРОНА: конкретная поверхность (A(1), A(2)…) не хранится
 *     // и не показывается. Продажи ведут менеджеры и сами обновляют данные
 *     // на сайте, поэтому портфелю достаточно месяца и его цены.
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

// Результат последней попытки сохранить портфель в ЛК ('' — ошибки нет).
const accountSaveError = ref('')

/*
 * Ошибка чтения портфеля из ЛК: '' — ошибки нет. Нужна, чтобы отличать
 * «на сервере пусто» от «не удалось получить данные» — раньше оба случая
 * выглядели как пустой портфель.
 */
const accountPortfolioError = ref('')

/*
 * Клиентские метки удалений: surfaceId -> ISO-время удаления.
 *
 * Сервер хранит только { title, items } и режет лишние поля, поэтому
 * метка живёт в localStorage. Нужна, чтобы неудачное сохранение удаления
 * не «воскрешало» позицию при следующем слиянии с сервером.
 */
const deletedAt = ref({})

// Старые метки удалений больше не нужны: позиций с такими датами нет.
const TOMBSTONE_TTL_MS = 30 * 24 * 60 * 60 * 1000

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
 * Портфель хранит и этот снимок, и снимок `statuses`: getMonthValue
 * разбирает их вместе (статус — из `statuses`, проценты загрузки — из
 * `months`). Оба нужны, иначе статусы в панели разойдутся с картой
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

  /*
   * Подпись стороны — сразу без индекса поверхности: у записей, сохранённых
   * до перехода на «позиция = сторона», в side лежит A(2)/A1(2), и на
   * странице портфеля (там нет каталога, а значит и syncWithConstructions)
   * она так и осталась бы поверхностью.
   */
  item.side = parentSide(item.side, item.type)

  return item
}

/*
 * Метки удалений из хранилища: только валидные ISO-даты не старше TTL.
 */
function normalizeTombstones(raw) {
  const now = Date.now()
  const result = {}

  if (raw && typeof raw === 'object') {
    Object.entries(raw).forEach(([key, value]) => {
      const stamp = String(value || '')
      const time = Date.parse(stamp)

      if (Number.isFinite(time) && now - time < TOMBSTONE_TTL_MS) {
        result[key] = stamp
      }
    })
  }

  return result
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

/* Явное включение/выключение режима выбора (без «слепого» toggle). */
function setSelectionMode(surfaceId, enabled) {
  const key = keyOf(surfaceId)

  if (enabled) {
    selectionMode[key] = true
  } else {
    delete selectionMode[key]
  }
}

/* Создаёт позицию из конструкции, если её ещё нет; иначе — существующую. */
function ensureItem(surface) {
  const surfaceId = toSurfaceId(surface?.id)

  if (surfaceId === null) {
    return null
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

  /* Позицию добавили заново — метка удаления больше не действует. */
  if (deletedAt.value[keyOf(surfaceId)]) {
    delete deletedAt.value[keyOf(surfaceId)]
  }

  return item
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

  const item = ensureItem(surface)

  if (!item) {
    return
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

// ------------------------------------------------------------ сторона целиком

/* Поверхности группы (записи каталога) — только те, у которых есть id. */
function surfaceListOf(items) {
  return (Array.isArray(items) ? items : []).filter(
    item => toSurfaceId(item?.id) !== null
  )
}

/*
 * Месяц стороны выбран, если он стоит у ЛЮБОЙ её поверхности: позиция
 * в портфеле одна, а поверхность у каждого месяца своя.
 */
function isSideMonthSelected(items, monthFull) {
  return surfaceListOf(items).some(surface =>
    isMonthSelected(toSurfaceId(surface.id), monthFull)
  )
}

/* Занято, если снимать нечего и ни одна поверхность стороны не свободна. */
function isSideMonthLocked(items, monthFull) {
  const surfaces = surfaceListOf(items)

  if (!surfaces.length) {
    return true
  }

  return (
    !isSideMonthSelected(surfaces, monthFull) &&
    !surfaces.some(surface => isFree(surface, monthFull))
  )
}

/* Паспорт позиции берём от стороны, а не от поверхности A(1): в панели
   строка читается как «Сторона: A», а не «Сторона: A(1)». */
function sidePassport(surface) {
  return { ...surface, side: parentSide(sideLabel(surface), surface.type) }
}

/*
 * Клик по месяцу СТОРОНЫ (карточка списка, попап карты, поиск по точке).
 *
 * В портфеле — одна позиция на сторону, конкретная поверхность (A(1), A(2)…)
 * не хранится и не показывается: продажи ведут менеджеры и сами обновляют
 * данные на сайте. Цену месяца берём у свободной поверхности стороны
 * (свободная в каждом месяце бывает своя), а сам id поверхности оставляем
 * только как ключ позиции.
 *
 * Снятие убирает месяц со всех поверхностей стороны — иначе позиция
 * осталась бы «выбранной» после клика.
 */
function toggleSideMonth(items, monthFull) {
  const surfaces = surfaceListOf(items)

  if (!surfaces.length || !monthFull) {
    return false
  }

  const selected = surfaces.filter(surface =>
    isMonthSelected(toSurfaceId(surface.id), monthFull)
  )

  if (selected.length) {
    selected.forEach(surface =>
      toggleItemMonth(toSurfaceId(surface.id), monthFull)
    )

    return true
  }

  const target = surfaces.find(surface => isFree(surface, monthFull))

  if (!target) {
    return false
  }

  const representative =
    surfaces.find(surface => isInPortfolio(toSurfaceId(surface.id))) || target
  const item = ensureItem(sidePassport(representative))

  if (!item) {
    return false
  }

  item.months[monthFull] = {
    price: toNumber(target.month_prices?.[monthFull]),
    addedAt: nowIso(),
    stale: false
  }

  return true
}

/*
 * Удаляет позицию и возвращает снимок для undo.
 * null — если позиции уже нет.
 */
function removeSurface(surfaceId) {
  const key = keyOf(surfaceId)
  const current = findItem(surfaceId)

  if (!current) {
    return null
  }

  const snapshot = {
    index: items.value.findIndex(item => keyOf(item.surfaceId) === key),
    selectionMode: Boolean(selectionMode[key]),
    item: normalizeItem(cloneDeep(current))
  }

  items.value = items.value.filter(item => keyOf(item.surfaceId) !== key)
  delete selectionMode[key]

  /* Метка удаления: даже если PUT не доедет, слияние не вернёт позицию. */
  deletedAt.value[key] = nowIso()

  return snapshot
}

/* Возвращает позицию, удалённую removeSurface(), на прежнее место. */
function restoreSurface(snapshot) {
  const item = snapshot ? normalizeItem(cloneDeep(snapshot.item)) : null

  if (!item) {
    return false
  }

  if (!findItem(item.surfaceId)) {
    const index = Math.max(
      0,
      Math.min(Number(snapshot.index) || 0, items.value.length)
    )

    items.value.splice(index, 0, item)
  }

  /* Отмена удаления снимает метку. */
  delete deletedAt.value[keyOf(item.surfaceId)]

  if (snapshot.selectionMode) {
    selectionMode[keyOf(item.surfaceId)] = true
  }

  return true
}

function clear() {
  const stamp = nowIso()

  /*
   * Очистка — это удаление всех позиций: отмечаем их, чтобы слияние не
   * вернуло их, если автосохранение не успеет или не сможет доехать.
   *
   * Метки ставим только в аккаунте: они страхуют именно серверную копию.
   * Выход из аккаунта тоже чистит портфель (см. AppHeader.handleLogout), но
   * там токен уже снят — без этой проверки метки оставались бы в браузере
   * и на следующем входе стирали бы серверные позиции владельца.
   */
  if (isAuthenticated.value) {
    items.value.forEach(item => {
      deletedAt.value[keyOf(item.surfaceId)] = stamp
    })
  }

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
 * Снимок цен и статусов по СТОРОНЕ: месяц «свободен», если свободна хотя
 * бы одна её поверхность — та же логика, что на карточке и в попапе
 * (sideAggMonthCell). У стороны с одной поверхностью снимок совпадает
 * с её собственным.
 */
function sideSnapshots(surfaces) {
  const prices = {}
  const statuses = {}
  const monthTexts = {}
  const months = new Set()

  surfaces.forEach(surface => {
    Object.keys(monthPricesOf(surface)).forEach(month => months.add(month))
    Object.keys(monthStatusesOf(surface)).forEach(month => months.add(month))
    Object.keys(monthTextsOf(surface)).forEach(month => months.add(month))
  })

  months.forEach(month => {
    const source =
      surfaces.find(surface => isFree(surface, month)) || surfaces[0]

    const price = toNumber(source.month_prices?.[month])

    if (price !== null) {
      prices[month] = price
    }

    statuses[month] = monthStatusesOf(source)[month] || ''
    monthTexts[month] = monthTextsOf(source)[month] || ''
  })

  return { prices, statuses, monthTexts }
}

/*
 * surfaceId → все поверхности той же СТОРОНЫ (формат + сторона в точке).
 * Нужен, чтобы позиция-сторона считалась по стороне целиком, а не по
 * одной поверхности, чей id оказался в позиции.
 */
function buildSideGroups(constructions) {
  const map = new Map()

  groupByPoint(constructions).forEach(point => {
    groupSides(point.items || []).forEach(group => {
      const surfaces = group.items || []

      surfaces.forEach(surface => {
        const id = toSurfaceId(surface?.id)

        if (id !== null) {
          map.set(keyOf(id), surfaces)
        }
      })
    })
  })

  return map
}

/*
 * Синхронизация с актуальным списком конструкций.
 *
 * Обновляет «паспортные» поля позиций, снимок цен/статусов и помечает
 * месяц stale, если сторона больше не свободна ни одной поверхностью.
 */
function syncWithConstructions(constructions) {
  if (!Array.isArray(constructions)) {
    return
  }

  const byId = new Map(
    constructions.map(construction => [keyOf(construction?.id), construction])
  )
  const sideGroups = buildSideGroups(constructions)

  /*
   * Это обновление снимков из каталога, а не действие пользователя:
   * помечаем, чтобы watcher не отправлял PUT в ЛК.
   */
  applyingCatalogSync = true

  items.value.forEach(item => {
    const construction = byId.get(keyOf(item.surfaceId))

    if (!construction) {
      return
    }

    PASSPORT_FIELDS.forEach(field => {
      item[field] = construction[field] ? String(construction[field]) : ''
    })

    /* Подпись стороны без индекса поверхности: «A», а не «A(1)». */
    item.side = parentSide(item.side, item.type)

    const siblings = sideGroups.get(keyOf(item.surfaceId)) || [construction]
    const snapshots = sideSnapshots(siblings)

    /* Обновляем снимок цен/статусов по всем месяцам, не только выбранным. */
    item.prices = { ...item.prices, ...snapshots.prices }
    item.statuses = { ...item.statuses, ...snapshots.statuses }
    item.monthTexts = { ...item.monthTexts, ...snapshots.monthTexts }

    Object.keys(item.months).forEach(monthFull => {
      const month = item.months[monthFull]

      if (!month) {
        return
      }

      /* Свободность — по стороне целиком, как на карте и в списке. */
      month.stale = !siblings.some(surface => isFree(surface, monthFull))

      const price = snapshots.prices[monthFull]

      if (price !== undefined) {
        month.price = price
      }
    })
  })

  /* Сбрасываем после flush watcher'ов: они выполняются асинхронно. */
  nextTick(() => {
    applyingCatalogSync = false
  })
}

/*
 * Портфель из ссылки (?pf=…): список { surfaceId, months }.
 *
 * Позиции собираются обычным toggleMonth по загруженному каталогу — он
 * сам заполняет паспортные поля и снимки цен/статусов, поэтому «призрачных»
 * позиций удалённых конструкций не появляется. Цены и stale после этого
 * дозаполнит syncWithConstructions на странице.
 *
 * replace=true — заменить текущий портфель, иначе дополнить: месяцы,
 * которые уже выбраны, пропускаем (toggleMonth на выбранном месяце его
 * СНИМАЕТ, а не добавляет).
 */
function applyShared(shared, constructions, { replace = false } = {}) {
  const list = Array.isArray(shared?.items) ? shared.items : []
  const catalog = Array.isArray(constructions) ? constructions : []
  /* unavailable — месяцы из ссылки, которые уже заняты: их не добавить. */
  const result = { added: 0, months: 0, skipped: 0, unavailable: 0 }

  if (replace) {
    clear()
  }

  const byId = new Map(
    catalog.map(construction => [keyOf(construction?.id), construction])
  )
  const sideGroups = buildSideGroups(catalog)

  list.forEach(sharedItem => {
    const sharedSurface = byId.get(keyOf(sharedItem?.surfaceId))

    if (!sharedSurface) {
      result.skipped += 1
      return
    }

    /*
     * Единица портфеля — сторона, поэтому месяц ищем и добавляем по стороне:
     * у получателя та же сторона могла быть уже открыта другой поверхностью
     * (свободная в каждом месяце бывает своя), и проверка по одному
     * surfaceId добавляла вторую строку на ту же сторону с двойной суммой.
     */
    const group = sideGroups.get(keyOf(sharedItem.surfaceId)) || [sharedSurface]

    const existed = group.some(surface =>
      isInPortfolio(toSurfaceId(surface?.id))
    )

    const monthsToAdd = (
      Array.isArray(sharedItem.months) ? sharedItem.months : []
    ).filter(monthFull => monthFull && !isSideMonthSelected(group, monthFull))

    /*
     * toggleSideMonth возвращает false, если месяц занят: раньше это
     * молча ничего не добавляло, и о недоступных месяцах никто не узнавал.
     */
    const applyMonth = monthFull => {
      if (!toggleSideMonth(group, monthFull)) {
        result.unavailable += 1
      }
    }

    if (existed) {
      /* Позиция стороны уже есть — дополняем её месяцами. */
      monthsToAdd.forEach(applyMonth)
    } else if (monthsToAdd.length) {
      applyMonth(monthsToAdd[0])
      monthsToAdd.slice(1).forEach(applyMonth)
    } else {
      /* Позиция без выбранных месяцев тоже ценна: «ничего не выбрано». */
      ensureItem(sidePassport(sharedSurface))
    }

    if (
      !existed &&
      group.some(surface => isInPortfolio(toSurfaceId(surface?.id)))
    ) {
      result.added += 1
    }

    result.months += monthsToAdd.length
  })

  if (shared?.title) {
    setTitle(shared.title)
  }

  return result
}

// ---------------------------------------------------------------- сериализация

function serialize() {
  const plain = cloneDeep(items.value)

  return {
    version: 1,
    title: normalizeTitle(title.value),
    items: Array.isArray(plain) ? plain : [],
    /* Только для localStorage: сервер это поле не принимает. */
    deletedAt: { ...deletedAt.value }
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

  // Метки удалений (старые и битые отбрасываем).
  deletedAt.value = normalizeTombstones(data.deletedAt)

  /*
   * Режимы выбора чистим вместе со списком: после подмены портфеля
   * (другая вкладка, слияние) оставались ключи позиций, которых уже нет,
   * и isSelectionMode() продолжал считать их активными.
   */
  Object.keys(selectionMode).forEach(key => {
    delete selectionMode[key]
  })

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
      accountPortfolioError.value = `Не удалось загрузить портфель (код ${response.status}).`

      return []
    }

    accountPortfolioError.value = ''

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
    accountPortfolioError.value = 'Нет связи с сервером — портфель не загружен.'

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

      /* Сервер только что очищен: отменяем отложенные сохранения и повторы. */
      if (saveTimer) {
        clearTimeout(saveTimer)
        saveTimer = null
      }

      resetAccountSaveRetry()

      /*
       * clear() вызовет watcher — пустой портфель обратно не отправляем.
       * Если локально уже было пусто, watcher не сработает: снимаем
       * флаг на следующем тике, чтобы он не погасил будущее сохранение.
       */
      suppressNextAccountSave = true

      /*
       * Чистим и локальный портфель вместе с режимами выбора: иначе на
       * карте и в списке остаются подсвеченные кнопки «Портфель» и
       * выбранные месяцы, хотя портфель уже пуст.
       */
      clear()

      nextTick(() => {
        suppressNextAccountSave = false
      })
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
 * Позиция удалена на этом устройстве и удаление ещё в силе?
 *
 * Если серверная запись добавлена ПОЗЖЕ метки удаления (портфель собрали
 * заново с другого устройства), метка устарела — снимаем её.
 */
function isTombstoned(item) {
  const key = keyOf(item.surfaceId)
  const deleted = deletedAt.value[key]

  if (!deleted) {
    return false
  }

  if (item.addedAt && item.addedAt > deleted) {
    delete deletedAt.value[key]

    return false
  }

  return true
}

/*
 * Слияние двух списков по surfaceId.
 *
 * Месяцы объединяются; при конфликте остаётся запись
 * с более поздним addedAt (то же правило для позиции целиком).
 */
function mergeItems(localItems, serverItems) {
  const merged = new Map()

  function absorb(list, skipTombstoned = false) {
    if (!Array.isArray(list)) {
      return
    }

    list.forEach(raw => {
      const item = normalizeItem(raw)

      if (!item) {
        return
      }

      if (skipTombstoned && isTombstoned(item)) {
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

  /* Серверные позиции, удалённые здесь, не воскрешаем. */
  absorb(serverItems, true)

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

    if (!response.ok) {
      accountPortfolioError.value = `Не удалось загрузить портфель (код ${response.status}).`

      return false
    }

    accountPortfolioError.value = ''

    const data = await response.json()
    serverItems = Array.isArray(data && data.items) ? data.items : []
    serverTitle = normalizeTitle(data && data.title)
    accountTitle.value = serverTitle
  } catch {
    accountPortfolioError.value = 'Нет связи с сервером — портфель не загружен.'

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

/*
 * Подавление автосохранения в ЛК:
 * - applyingCatalogSync — каталог обновил снимки цен/статусов (это не
 *   пользовательское изменение, PUT не нужен);
 * - suppressNextAccountSave — портфель только что очищен в ЛК через
 *   DELETE, отправлять обратно пустой портфель незачем.
 */
let applyingCatalogSync = false
let suppressNextAccountSave = false

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

/* Повторы после неудачного PUT: 5 с -> 15 с -> 30 с, дальше раз в 30 с. */
const SAVE_RETRY_DELAYS_MS = [5000, 15000, 30000]
let retryTimer = null
let retryAttempt = 0

function scheduleAccountSaveRetry() {
  if (!isAuthenticated.value || retryTimer) {
    return
  }

  const delay =
    SAVE_RETRY_DELAYS_MS[
      Math.min(retryAttempt, SAVE_RETRY_DELAYS_MS.length - 1)
    ]

  retryAttempt += 1
  accountSaveError.value =
    'Не удалось сохранить портфель в личном кабинете. Повторяем…'

  retryTimer = setTimeout(() => {
    retryTimer = null
    void flushAccountSave()
  }, delay)
}

/* Отменяет запланированные повторы и снимает ошибку сохранения. */
function resetAccountSaveRetry() {
  if (retryTimer) {
    clearTimeout(retryTimer)
    retryTimer = null
  }

  retryAttempt = 0
  accountSaveError.value = ''
}

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

      if (ok) {
        retryAttempt = 0
        accountSaveError.value = ''
      } else {
        /*
         * Тихий провал недопустим: удаление, не доехавшее до сервера,
         * «воскресало» при следующем слиянии. Повторяем и показываем
         * причину; метки удалений (deletedAt) страхуют от повторов.
         */
        saveQueued = false
        scheduleAccountSaveRetry()
        break
      }
    } while (saveQueued && isAuthenticated.value)
  } finally {
    saveInFlight = false
  }
}

/*
 * Выход из аккаунта отменяет повторы: сохранять больше некуда, а старая
 * ошибка не должна всплывать при следующем открытии панели.
 *
 * Там же снимаем и метки удалений: они привязаны к аккаунту, под которым
 * ставились, и в браузере общего компьютера достались бы следующему
 * пользователю — его собственные серверные позиции выглядели бы как
 * удалённые и пропали бы при слиянии.
 */
watch(isAuthenticated, value => {
  if (value) {
    return
  }

  resetAccountSaveRetry()

  if (Object.keys(deletedAt.value).length) {
    deletedAt.value = {}
    saveLocal()
  }
})

watch(
  [items, title],
  () => {
    /* Состояние из другой вкладки не пересохраняем обратно. */
    if (applyingExternalStorage) {
      return
    }

    saveLocal()

    /*
     * Снимки цен/статусов из каталога сохраняем только локально: иначе
     * каждый заход на сайт отправлял бы PUT в ЛК без изменений.
     */
    if (applyingCatalogSync) {
      return
    }

    /* После DELETE в ЛК сервер уже пуст — PUT пустого портфеля не нужен. */
    if (suppressNextAccountSave) {
      suppressNextAccountSave = false

      return
    }

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
    isSideMonthSelected,
    isSideMonthLocked,

    // изменение
    toggleSelectionMode,
    setSelectionMode,
    toggleMonth,
    toggleSideMonth,
    toggleItemMonth,
    removeSurface,
    restoreSurface,
    clear,
    setTitle,
    syncWithConstructions,
    applyShared,

    // (де)сериализация и хранение
    serialize,
    hydrate,
    loadLocal,
    saveLocal,

    // синхронизация с ЛК
    saveToAccount,
    mergeFromAccount,
    fetchAccountPortfolio,
    accountPortfolioUpdatedAt,
    accountSaveError,
    accountPortfolioError,
    clearAccountPortfolio
  }
}
