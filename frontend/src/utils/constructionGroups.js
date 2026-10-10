/*
 * Общие правила группировки рекламных сторон.
 *
 * Используется и попапом интерактивной карты (popupContent),
 * и закладкой «Список» на странице рекламных возможностей.
 * Здесь только чистая логика — без HTML, без DOM, без Leaflet.
 */

export const MONTHS = [
  { full: 'Август', short: 'АВГ' },
  { full: 'Сентябрь', short: 'СЕН' },
  { full: 'Октябрь', short: 'ОКТ' },
  { full: 'Ноябрь', short: 'НОЯ' },
  { full: 'Декабрь', short: 'ДЕК' }
]

/*
 * Терминология:
 *   Конструкция = Адрес + номер (один объект, одна координата);
 *   Сторона     = A, B, C, а на разделительной полосе — A1, A2 (без индекса);
 *   Поверхность = A(1), A(2), A1(2)… (индекс в скобках) — лежит на стороне.
 *
 * Динамическая сторона содержит несколько поверхностей, статическая — одну.
 */
export function sideLabel(item) {
  return String(item?.side || '')
    .toUpperCase()
    .trim()
}

/* Формат «щит»: любая подпись — это СТОРОНА (щит статичен, поверхностей нет). */
function isShieldFormat(type) {
  return String(type || '').toLowerCase().includes('щит')
}

/* Формат «экран»: голая A1 — СТОРОНА, но A(1) — уже поверхность. */
function isScreenFormat(type) {
  return String(type || '').toLowerCase().includes('экран')
}

/* Динамика = на стороне несколько поверхностей.
 * Индекс в скобках (A(1), A1(2)) — поверхность (кроме щита).
 * Голая A1/A2 — поверхность вне щита и экрана. */
export function isDynamicSide(side, type) {
  const value = String(side || '').toUpperCase().trim()

  if (isShieldFormat(type)) {
    return false
  }

  if (/\(\d+\)/.test(value)) {
    return true
  }

  if (/^[A-ZА-Я]+\d+$/.test(value)) {
    return !isScreenFormat(type)
  }

  return false
}

/* Сторона = подпись без индекса поверхности. Подписи не нормализуем —
 * показываем как в базе.
 *
 * Щит: любая подпись — сторона («A», «B», «A(1)», «A1»…).
 *
 * Остальные: «A1(2)» → «A1», «A(3)» → «A»; голая «A1» → «A»
 * (у экрана голая «A1» — сторона, остаётся «A1»). */
export function parentSide(side, type) {
  const value = String(side || '').toUpperCase().trim()

  if (isShieldFormat(type)) {
    return value
  }

  if (/\(\d+\)/.test(value)) {
    return value.replace(/\(\d+\)\s*$/, '').trim()
  }

  if (/^[A-ZА-Я]+\d+$/.test(value)) {
    return isScreenFormat(type) ? value : value.replace(/\d+$/, '')
  }

  return value
}

/*
 * Убираем дубликаты по стороне В ПРЕДЕЛАХ формата (порядок сохраняем):
 * одна и та же буква у разных форматов — это разные блоки.
 */
export function dedupeSides(items) {
  const sides = []

  for (const item of items) {
    const side = sideLabel(item)
    const type = String(item?.type || '').trim().toUpperCase()

    const exists = sides.some(existing => {
      const existingSide = sideLabel(existing)
      const existingType = String(existing?.type || '').trim().toUpperCase()

      return (
        side &&
        existingSide &&
        side === existingSide &&
        type === existingType
      )
    })

    if (!exists) {
      sides.push(item)
    }
  }

  return sides
}

/*
 * Семейство определяет число блоков:
 * пиллар — до 3, пилон/скроллер — 2,
 * адреса с щитом/призматроном/видеоэкраном — 2 (или 1, если одна сторона).
 */
export function familyOf(items) {
  const types = items.map(item =>
    String(item?.type || '').trim().toLowerCase()
  )

  if (types.some(type => type.includes('пиллар'))) {
    return 'pillar'
  }

  if (types.some(type => type.includes('пилон'))) {
    return 'pylon'
  }

  if (types.some(type => type.includes('скроллер'))) {
    return 'scroller'
  }

  return 'address'
}

export function maxBlocksFor(family) {
  return family === 'pillar' ? 3 : 2
}

/*
 * Группируем поверхности по ФОРМАТУ и СТОРОНЕ:
 * «Призматрон A(1)+A(2)+A(3)» → сторона A, «Щит B» → отдельная сторона B.
 * Так разные форматы на одном адресе не смешиваются и не теряются.
 *
 * kind:
 *   'video'   — видеоэкран (всегда динамический, одна строка месяцев);
 *   'dynamic' — на стороне несколько поверхностей;
 *   'static'  — одна поверхность.
 */
export function groupSides(items) {
  const groups = []

  for (const item of items) {
    const type = String(item?.type || '').trim().toLowerCase()
    const parent = parentSide(sideLabel(item), item.type)
    const group = groups.find(
      existing => existing.parent === parent && existing.type === type
    )

    if (group) {
      group.items.push(item)
    } else {
      groups.push({ type, parent, items: [item] })
    }
  }

  return groups.map(group => {
    const first = group.items[0]
    const type = String(first?.type || '').trim().toLowerCase()

    let kind

    if (type.includes('видеоэкран')) {
      kind = 'video'
    } else if (
      group.items.length > 1 ||
      group.items.some(item => isDynamicSide(sideLabel(item), item.type))
    ) {
      kind = 'dynamic'
    } else {
      kind = 'static'
    }

    return {
      type: group.type,
      parent: group.parent,
      items: group.items,
      kind
    }
  })
}

/*
 * Одна точка = одна карточка.
 *
 * Ключ точки — КООРДИНАТА (округление до 5 знаков). Подпись адреса и
 * номер конструкции в ключ не входят: у одной точки они могут отличаться.
 * Без координат — откат на адрес, чтобы не слить разные объекты.
 */
export function groupByPoint(items) {
  const points = []

  for (const item of items) {
    const lat = Number(item?.lat)
    const lng = Number(item?.lng)
    const type = String(item?.type || '').toLowerCase()

    let key

    /* Видеоэкран — самостоятельная сущность: по одному адресу у него две
     * стороны, но это ДВА отдельных экрана, поэтому каждый экран — отдельная
     * точка (не сливаем их по координате). */
    if (type.includes('видеоэкран')) {
      key = `video|${item?.id ?? item?.construction_id ?? points.length}`
    } else if (Number.isFinite(lat) && Number.isFinite(lng)) {
      key = `${lat.toFixed(5)}|${lng.toFixed(5)}`
    } else {
      const city = String(item?.city || '').trim().toLowerCase()
      const address = String(item?.address || item?.name || '')
        .trim()
        .toLowerCase()

      key = `noc|${city}|${address}`
    }

    let point = points.find(existing => existing.key === key)

    if (!point) {
      point = { key, items: [] }
      points.push(point)
    }

    point.items.push(item)
  }

  return points
}
