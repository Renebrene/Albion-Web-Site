import { escapeHtml } from './markerIcon'
import {
  getAvailabilityState,
  getMonthStatusLabel,
  getMonthValue
} from '../utils/availability'

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

/* Классификация сторон: динамические — буква с индексом A(1)/A2 */
function sideLabel(item) {
  return String(item?.side || '')
    .toUpperCase()
    .trim()
}

function isDynamicSide(side) {
  return /\(\d+\)/.test(side) || /^[A-ZА-Я]+\d+$/.test(side)
}

function parentSide(side) {
  const match = String(side || '').match(/^([A-ZА-Я]+)/)
  return match ? match[1] : side
}

function monthCell(item, month) {
  return `
    <div
      class="popup-month ${monthState(item, month.full)}"
      title="${escapeHtml(getMonthStatusLabel(item, month.full))}"
    >
      ${escapeHtml(month.short)}
    </div>
  `
}

function monthBlock(item) {
  return `
    <div class="popup-months">
      ${MONTHS.map(month => monthCell(item, month)).join('')}
    </div>
  `
}

/* Видеоэкран: одна строка месяцев, занято = 100%, иначе свободно */
function videoMonthBlock(item) {
  return `
    <div class="popup-months popup-months--video">
      ${MONTHS.map(month => {
        const state = monthState(item, month.full)
        const raw = getMonthValue(item, month.full)
        const label = state === 'busy' ? 'Занято' : 'Свободно'
        const title = raw
          ? `${label} (${raw})`
          : getMonthStatusLabel(item, month.full)

        return `
          <div
            class="popup-month ${state} popup-month--video"
            title="${escapeHtml(title)}"
          >
            ${escapeHtml(month.short)}
          </div>
        `
      }).join('')}
    </div>
  `
}

function promoPrice(item) {
  return String(
    item?.promoPrice ??
    item?.promo_price ??
    ''
  ).trim()
}

function priceBlock(item) {
  const price = item?.price
  const promo = promoPrice(item)

  const hasPrice = (
    price !== undefined &&
    price !== null &&
    String(price).trim() !== ''
  )

  const hasPromo = promo !== ''

  if (!hasPrice && !hasPromo) {
    return ''
  }

  return `
    <div class="popup-price">
      ${
        hasPrice
          ? `
            <span class="popup-price-value ${hasPromo ? 'is-old' : ''}">
              ${escapeHtml(price)}
            </span>
            <span class="popup-price-currency">₽</span>
            <span class="popup-price-period">/ мес.</span>
          `
          : ''
      }

      ${
        hasPromo
          ? `
            <div class="promo-price">
              <span class="promo-price-value">
                ${escapeHtml(promo)}
              </span>
              <span class="promo-price-currency">₽</span>
              <span class="promo-price-note">акционная цена</span>
            </div>
          `
          : ''
      }
    </div>
  `
}

function sideBlock(item) {
  const side = sideLabel(item)

  if (!side) return ''

  return `
    <span class="popup-side-badge" title="Сторона">
      ${escapeHtml(side)}
    </span>
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

function featuresBlock(item) {
  const light = String(item?.light || '').trim().toLowerCase()
  const hasLight = [
    'да',
    'yes',
    'true',
    '1'
  ].includes(light)

  return `
    <div class="popup-features">
      <div
        class="popup-feature"
        title="${hasLight ? 'Подсветка есть' : 'Без подсветки'}"
      >
        <span class="feature-picto lightbulb ${hasLight ? 'on' : 'off'}">💡</span>
        <span class="feature-label">подсветка</span>
      </div>

      <div class="popup-feature" title="статика/динамика">
        <span class="feature-picto feature-placeholder"></span>
        <span class="feature-label">статика/динамика</span>
      </div>
    </div>
  `
}

/* ---------------------------------------------------------------- блоки */

/* Статичная сторона: обычная карточка */
function sideCard(item) {
  return `
    <section class="popup-side-card">
      <div class="popup-side-top">
        ${sideBlock(item)}
        ${priceBlock(item)}
      </div>
      ${typeBlock(item)}
      ${photoBlock(item)}
      ${featuresBlock(item)}
      ${monthBlock(item)}
    </section>
  `
}

/* Динамическая сторона: фото первой поверхности + строки A(1)/A(2)/A(3) */
function dynamicRowsBlock(group) {
  return `
    <div class="popup-dynamic-rows">
      ${group.items.map(item => `
        <div class="popup-dynamic-row">
          <span class="popup-dynamic-side">${escapeHtml(sideLabel(item))}</span>
          ${MONTHS.map(month => monthCell(item, month)).join('')}
        </div>
      `).join('')}
    </div>
  `
}

function dynamicBlock(group) {
  const first = group.items[0]

  return `
    <section class="popup-side-card popup-side-card--dynamic">
      <div class="popup-side-top">
        ${sideBlock({ ...first, side: parentSide(sideLabel(first)) })}
        ${priceBlock(first)}
      </div>
      ${typeBlock(first)}
      ${photoBlock(first)}
      ${dynamicRowsBlock(group)}
      ${featuresBlock(first)}
    </section>
  `
}

/* Видеоэкран: всегда динамический, месяцы в одну строку */
function videoBlock(item) {
  return `
    <section class="popup-side-card popup-side-card--video">
      <div class="popup-side-top">
        ${sideBlock(item)}
        ${priceBlock(item)}
      </div>
      ${typeBlock(item)}
      ${photoBlock(item)}
      ${videoMonthBlock(item)}
      ${featuresBlock(item)}
    </section>
  `
}

function renderGroup(group) {
  const first = group.items[0]
  const type = String(first?.type || '')
    .trim()
    .toLowerCase()

  if (type.includes('видеоэкран')) {
    return videoBlock(first)
  }

  const isDynamicGroup =
    group.items.length > 1 ||
    group.items.some(item => isDynamicSide(sideLabel(item)))

  if (isDynamicGroup) {
    return dynamicBlock(group)
  }

  return sideCard(first)
}

/* ---------------------------------------------------------------- шапка */

function commonHeader(items) {
  const first = items[0] || {}

  const address = String(
    first?.address ||
    first?.name ||
    ''
  ).trim()

  const place = String(
    first?.city ||
    first?.district ||
    ''
  ).trim()

  return `
    <div class="popup-header">

      ${
        address
          ? `
            <div class="popup-title">
              <strong>${escapeHtml(address)}</strong>
            </div>
          `
          : ''
      }

      ${
        place
          ? `
            <div class="popup-address">
              ${escapeHtml(place)}
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

  // Убираем дубликаты по полной стороне (порядок сохраняем).
  const sides = []

  for (const item of items) {
    const side = sideLabel(item)

    const exists = sides.some(existing => {
      const existingSide = sideLabel(existing)

      return side && existingSide && side === existingSide
    })

    if (!exists) {
      sides.push(item)
    }
  }

  // Семейство определяет число блоков:
  // пиллар — до 3, пилон/скроллер — 2,
  // адреса с щитом/призматроном/видеоэкраном — 2 (или 1, если одна сторона).
  const types = sides.map(item =>
    String(item?.type || '').trim().toLowerCase()
  )

  const family = types.some(type => type.includes('пиллар'))
    ? 'pillar'
    : types.some(type => type.includes('пилон'))
      ? 'pylon'
      : types.some(type => type.includes('скроллер'))
        ? 'scroller'
        : 'address'

  const maxBlocks = family === 'pillar' ? 3 : 2

  // Группируем по родительской стороне (A(1) и A(2) → блок «A»).
  const groups = []

  for (const item of sides) {
    const parent = parentSide(sideLabel(item))
    const group = groups.find(existing => existing.parent === parent)

    if (group) {
      group.items.push(item)
    } else {
      groups.push({ parent, items: [item] })
    }
  }

  const visibleGroups = groups.slice(0, maxBlocks)
  const allSides = visibleGroups.flatMap(group => group.items)

  const popupClass =
    visibleGroups.length === 3
      ? 'popup-triple'
      : visibleGroups.length > 1
        ? 'popup-double'
        : 'popup-single'

  return `
    <div class="popup ${popupClass}">

      ${commonHeader(allSides)}

      <div class="popup-sides">

        ${visibleGroups
          .map(renderGroup)
          .join('')}

      </div>

    </div>
  `
}