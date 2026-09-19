import { escapeHtml } from './markerIcon'
import { getAvailabilityState, getMonthValue } from '../utils/availability'

const MONTHS = [
  { full: 'Август', short: 'АВГ' },
  { full: 'Сентябрь', short: 'СЕН' },
  { full: 'Октябрь', short: 'ОКТ' },
  { full: 'Ноябрь', short: 'НОЯ' },
  { full: 'Декабрь', short: 'ДЕК' }
]

function monthState(item, month) {
  return getAvailabilityState(item, month)
}

function monthBlock(item) {
  return `
    <div class="popup-months">
      ${MONTHS.map(month => `
        <div
          class="popup-month ${monthState(item, month.full)}"
          title="${escapeHtml(getMonthValue(item, month.full) || 'Нет данных')}"
        >
          ${escapeHtml(month.short)}
        </div>
      `).join('')}
    </div>
  `
}

function priceBlock(item) {
  if (
    item?.price === undefined ||
    item?.price === null ||
    String(item.price).trim() === ''
  ) {
    return ''
  }

  return `
    <div class="popup-price">
      <span class="popup-price-value">
        ${escapeHtml(item.price)}
      </span>
      <span class="popup-price-currency">₽</span>
      <span class="popup-price-period">/ мес.</span>
    </div>
  `
}

function sideBlock(item) {
  const side = String(item?.side || '')
    .trim()
    .toUpperCase()

  if (!side) return ''

  return `
    <div class="popup-side">
      <span class="popup-side-label">СТОРОНА</span>
      <strong class="popup-side-value popup-side-${escapeHtml(side)}">
        ${escapeHtml(side)}
      </strong>
    </div>
  `
}

function typeBlock(item) {
  const type = String(
    item?.type || 'Конструкция'
  ).trim()

  const size = String(
    item?.size || ''
  ).trim()

  return `
    <div class="popup-type">
      <strong>${escapeHtml(type)}</strong>
      ${
        size
          ? `<span class="popup-size">${escapeHtml(size)}</span>`
          : ''
      }
    </div>
  `
}

function photoBlock(item) {
  if (!item?.photo) {
    return `
      <div class="popup-photo popup-photo-empty">
        Фото
      </div>
    `
  }

  return `
    <a
      class="popup-photo"
      href="${escapeHtml(item.photo)}"
      target="_blank"
      rel="noopener noreferrer"
    >
      <img
        src="${escapeHtml(item.photo)}"
        alt=""
        loading="lazy"
      >
    </a>
  `
}

function sideCard(item) {
  return `
    <section class="popup-side-card">

      <div class="popup-side-top">
        ${sideBlock(item)}
        ${priceBlock(item)}
      </div>

      ${typeBlock(item)}

      ${photoBlock(item)}

      ${monthBlock(item)}

    </section>
  `
}

function commonHeader(items) {
  const first = items[0] || {}

  const city = String(
    first?.city || ''
  ).trim()

  const address = String(
    first?.address ||
    first?.name ||
    ''
  ).trim()

  return `
    <div class="popup-header">

      ${
        city
          ? `
            <div class="popup-title">
              <strong>${escapeHtml(city)}</strong>
            </div>
          `
          : ''
      }

      ${
        address
          ? `
            <div class="popup-address">
              ${escapeHtml(address)}
            </div>
          `
          : ''
      }

    </div>
  `
}

function normalizeSides(input) {
  if (Array.isArray(input)) {
    return input.filter(Boolean)
  }

  if (input && typeof input === 'object') {
    return [input]
  }

  return []
}

export function popupContent(input) {
  const items = normalizeSides(input)

  if (!items.length) {
    return `
      <div class="popup-empty">
        Нет данных
      </div>
    `
  }

  const sides = []

  for (const item of items) {
    const side = String(item?.side || '')
      .trim()
      .toUpperCase()

    const exists = sides.some(existing => {
      const existingSide = String(existing?.side || '')
        .trim()
        .toUpperCase()

      return (
        side &&
        existingSide &&
        side === existingSide
      )
    })

    if (!exists) {
      sides.push(item)
    }
  }

  const firstType = String(sides[0]?.type || '')
    .trim()
    .toLowerCase()

  const isThreeSideConstruction =
    firstType.includes('пиллар') ||
    firstType.includes('призматрон')

  const maxSides = isThreeSideConstruction ? 3 : 2

  const visibleSides = sides.slice(0, maxSides)

  const popupClass =
    visibleSides.length === 3
      ? 'popup-triple'
      : visibleSides.length > 1
        ? 'popup-double'
        : 'popup-single'

  return `
    <div class="popup ${popupClass}">

      ${commonHeader(visibleSides)}

      <div class="popup-sides">

        ${visibleSides
          .map(sideCard)
          .join('')}

      </div>

    </div>
  `
}
