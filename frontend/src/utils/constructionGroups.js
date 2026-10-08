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

/* Классификация сторон: динамические — буква с индексом A(1)/A2 */
export function sideLabel(item) {
  return String(item?.side || '')
    .toUpperCase()
    .trim()
}

export function isDynamicSide(side) {
  return /\(\d+\)/.test(side) || /^[A-ZА-Я]+\d+$/.test(side)
}

export function parentSide(side) {
  const match = String(side || '').match(/^([A-ZА-Я]+)/)
  return match ? match[1] : side
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
 * Группируем по ФОРМАТУ и родительской стороне:
 * «Призматрон A(1)+A(2)+A(3)» → один блок, «Щит B» → отдельный.
 * Так разные форматы на одном адресе не смешиваются и не теряются.
 *
 * kind:
 *   'video'   — формат видеоэкран;
 *   'dynamic' — в группе >1 записи или есть динамическая сторона;
 *   'static'  — иначе.
 */
export function groupSides(items) {
  const groups = []

  for (const item of items) {
    const type = String(item?.type || '').trim().toLowerCase()
    const parent = parentSide(sideLabel(item))
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
      group.items.some(item => isDynamicSide(sideLabel(item)))
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
 * Одна точка (адрес с координатами) = одна карточка.
 * Ключ нормализован: город/адрес в нижнем регистре,
 * координаты округлены до 5 знаков.
 */
export function groupByPoint(items) {
  const points = []

  for (const item of items) {
    const city = String(item?.city || '').trim().toLowerCase()
    const address = String(item?.address || '').trim().toLowerCase()

    const lat = Number(item?.lat)
    const lng = Number(item?.lng)

    const latKey = Number.isFinite(lat) ? lat.toFixed(5) : ''
    const lngKey = Number.isFinite(lng) ? lng.toFixed(5) : ''

    const key = `${city}|${address}|${latKey}|${lngKey}`

    let point = points.find(existing => existing.key === key)

    if (!point) {
      point = { key, items: [] }
      points.push(point)
    }

    point.items.push(item)
  }

  return points
}
