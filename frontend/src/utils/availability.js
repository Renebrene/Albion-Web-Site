export function normalizeAvailability(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
}

export function getMonthValue(item, month) {
  return (
    item?.months?.[month] ??
    item?.statuses?.[month] ??
    ''
  )
}

export function getAvailabilityState(item, month) {
  const raw = String(
    getMonthValue(item, month)
  ).trim()

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
  if (
    value.includes('резерв') ||
    value.includes('утверж')
  ) {
    return 'reserve'
  }

  // Продано / занято
  if (
    value.includes('продан') ||
    value.includes('занят')
  ) {
    return 'busy'
  }

  // Для видеоэкранов 100% = занято
  if (value === '100%') {
    return 'busy'
  }

  // Процент загрузки менее 100% = свободно
  const percent = value.match(
    /(\d+(?:[.,]\d+)?)\s*%/
  )

  if (percent) {
    return Number(
      percent[1].replace(',', '.')
    ) >= 100
      ? 'busy'
      : 'free'
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
