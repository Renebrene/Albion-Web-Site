export function normalizeAvailability(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
}

/*
 * Заглушка «Доступность» из выгрузки (там это статус LOAD): статуса в ней нет,
 * а реальное значение — проценты загрузки — лежит в `months`.
 */
const LOAD_PLACEHOLDER = 'доступность'

/*
 * Статус месяца. Главный источник — `statuses`: это нормализованный статус
 * из выгрузки, и только в него попадают временные правки администратора
 * (переопределения месяца в разделе «Конструкции»). Раньше приоритет был
 * у `months`, поэтому такие правки на сайте не были видны вовсе: `months`
 * непустой, а `??` не пропускает пустую строку.
 *
 * `months` остаётся источником там, где статуса нет: у видеоэкранов он
 * содержит проценты загрузки («8%», «33%»), у части строк — «Резерв до …».
 *
 * Все состояния сайта считаются отсюда (карта, попап, список, портфель,
 * чат, фильтр месяцев), поэтому правило одно на всех.
 */
export function getMonthValue(item, month) {
  const status = String(item?.statuses?.[month] ?? '').trim()

  if (status && normalizeAvailability(status) !== LOAD_PLACEHOLDER) {
    return status
  }

  return item?.months?.[month] ?? ''
}

export function getAvailabilityState(item, month) {
  const raw = String(getMonthValue(item, month)).trim()

  // Нет данных = СВОБОДНО
  if (!raw) {
    return 'free'
  }

  const value = normalizeAvailability(raw)

  // Явно свободно
  if (value === 'свободно') {
    return 'free'
  }

  // Резерв / утверждение
  if (value.includes('резерв') || value.includes('утверж')) {
    return 'reserve'
  }

  // Продано / занято
  if (value.includes('продан') || value.includes('занят')) {
    return 'busy'
  }

  // Для видеоэкранов 100% = занято
  if (value === '100%') {
    return 'busy'
  }

  // Процент загрузки менее 100% = свободно
  const percent = value.match(/(\d+(?:[.,]\d+)?)\s*%/)

  if (percent) {
    return Number(percent[1].replace(',', '.')) >= 100 ? 'busy' : 'free'
  }

  // Любое другое непустое значение считаем занятым.
  return 'busy'
}

export function isFree(item, month) {
  return getAvailabilityState(item, month) === 'free'
}

export function isBusy(item, month) {
  return getAvailabilityState(item, month) === 'busy'
}

/* Человекочитаемая подсказка для статуса месяца. */
export function getMonthStatusLabel(item, month) {
  const state = getAvailabilityState(item, month)

  if (state === 'busy') {
    return 'Продано'
  }

  if (state === 'reserve') {
    return 'Звоните для уточнения статуса'
  }

  return 'Свободно'
}
