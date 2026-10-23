import { escapeHtml } from './markerIcon'
import {
  getAvailabilityState,
  getMonthStatusLabel,
  getMonthValue,
  isFree
} from '../utils/availability'
import {
  MONTHS,
  sideLabel,
  parentSide,
  dedupeSides,
  familyOf,
  maxBlocksFor,
  groupSides
} from '../utils/constructionGroups'
import { usePortfolio } from '../composables/usePortfolio'
import { photoLabel, sanitizeFileName } from '../composables/usePhotoViewer'
import { availableMode } from '../config/availableMode'
import { showDynCount } from '../config/dynCount'

/*
 * Портфель-стор — только чтение начального состояния кнопок и месяцев
 * попапа. Дальнейшие переключения делает делегированный обработчик
 * кликов со страницы (см. AdvertisingPage.vue).
 */
const portfolio = usePortfolio()

function monthState(item, month) {
  return getAvailabilityState(item, month)
}

/* Поверхность считается «адресуемой», если у неё есть id. */
function surfaceIdOf(item) {
  const id = item?.id

  return id === undefined || id === null || id === '' ? null : id
}

function monthCell(item, month) {
  const surfaceId = surfaceIdOf(item)
  const selected =
    surfaceId !== null && portfolio.isMonthSelected(surfaceId, month.full)

  /*
   * Выбрать можно только свободный месяц: у занятых/резервных не ставим
   * data-pf-month, поэтому клик по ним ничего не делает. Снять уже
   * выбранный месяц можно всегда.
   */
  const locked = !selected && !isFree(item, month.full)

  const pfAttrs =
    surfaceId !== null && !locked
      ? ` data-pf-month="${escapeHtml(String(surfaceId))}|${escapeHtml(month.full)}"`
      : ''

  return `
    <button
      type="button"
      class="popup-month ${monthState(item, month.full)}${selected ? ' is-selected' : ''}${locked ? ' is-locked' : ''}"
      aria-pressed="${selected ? 'true' : 'false'}"
      title="${escapeHtml(getMonthStatusLabel(item, month.full))}"${pfAttrs}
    >
      ${escapeHtml(month.short)}
    </button>
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
  const surfaceId = surfaceIdOf(item)

  return `
    <div class="popup-months popup-months--video">
      ${MONTHS.map(month => {
        const state = monthState(item, month.full)
        const raw = getMonthValue(item, month.full)
        const label = state === 'busy' ? 'Занято' : 'Свободно'
        const title = raw
          ? `${label} (${raw})`
          : getMonthStatusLabel(item, month.full)

        const selected =
          surfaceId !== null && portfolio.isMonthSelected(surfaceId, month.full)

        /*
         * Занятый месяц выбрать нельзя: не ставим data-pf-month, иначе
         * клик уходил бы в обработчик и молча игнорировался, а клетка
         * выглядела активной. Уже выбранный месяц снять можно всегда.
         */
        const locked = !selected && !isFree(item, month.full)

        const pfAttrs =
          surfaceId !== null && !locked
            ? ` data-pf-month="${escapeHtml(String(surfaceId))}|${escapeHtml(month.full)}"`
            : ''

        return `
          <button
            type="button"
            class="popup-month ${state} popup-month--video${selected ? ' is-selected' : ''}${locked ? ' is-locked' : ''}"
            aria-pressed="${selected ? 'true' : 'false'}"
            title="${escapeHtml(title)}"${pfAttrs}
          >
            ${escapeHtml(month.short)}
          </button>
        `
      }).join('')}
    </div>
  `
}

function promoPrice(item) {
  return String(item?.promoPrice ?? item?.promo_price ?? '').trim()
}

function priceBlock(item) {
  const price = item?.price
  const promo = promoPrice(item)

  const hasPrice =
    price !== undefined && price !== null && String(price).trim() !== ''

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
      Сторона ${escapeHtml(side)}
    </span>
  `
}

function typeBlock(item) {
  const type = String(item?.type || 'Конструкция').trim()

  const size = String(item?.size || '').trim()

  return `
    <div class="popup-type">
      <strong>${escapeHtml(type)}</strong>
      ${size ? `<span class="popup-size">${escapeHtml(size)}</span>` : ''}
    </div>
  `
}

function photoBlock(item) {
  /*
   * API отдаёт два превью и large:
   *   photo       — card 640px (2× ширины карточки),
   *   photo_thumb — thumb 400px,
   *   photo_large — large 1600px.
   * Любой вариант может отсутствовать — подставляем соседний.
   */
  const thumb = item?.photo_thumb || ''
  const card = item?.photo || thumb
  const preview = card || thumb

  /*
   * Крупный вариант карты-схемы — чтобы окно просмотра (как в портфеле)
   * могло показать и сохранить карту рядом с фото.
   * `item.map` — исходная ссылка на страницу Яндекс.Диска, а не файл:
   * как src она не работает (и блокируется CSP), поэтому не берём её.
   */
  const mapLarge = String(
    item?.map_large || item?.map_card || item?.map_thumb || ''
  ).trim()

  if (!preview) {
    /* Нет фото, но есть карта — по клику откроем карту в общем окне. */
    if (mapLarge) {
      return `
        <div
          class="popup-photo popup-photo-empty"
          style="cursor: pointer;"
          data-photo
          data-photo-map="${escapeHtml(mapLarge)}"
          title="Открыть карту"
        >
          Фото
        </div>
      `
    }

    return `
      <div class="popup-photo popup-photo-empty">
        Фото
      </div>
    `
  }

  const large = item?.photo_large || card

  const srcset = [
    thumb && `${escapeHtml(thumb)} 400w`,
    item?.photo && `${escapeHtml(item.photo)} 640w`,
    item?.photo_large && `${escapeHtml(item.photo_large)} 1600w`
  ]
    .filter(Boolean)
    .join(', ')

  /*
   * Клик по фото открывает общее окно (usePhotoViewer), а не новую
   * вкладку: делегированный обработчик ловит `[data-photo]` и читает
   * url/title/filename из data-атрибутов. Название — «адрес + сторона».
   */
  const label = photoLabel({
    city: item?.city,
    address: item?.address,
    side: sideLabel(item)
  })
  const fileName = sanitizeFileName(label, large)

  return `
    <div
      class="popup-photo"
      style="cursor: pointer;"
      role="button"
      tabindex="0"
      title="${mapLarge ? 'Открыть фото и карту' : 'Открыть фото'}"
      data-photo
      data-photo-url="${escapeHtml(large)}"
      data-photo-map="${escapeHtml(mapLarge)}"
      data-photo-title="${escapeHtml(label)}"
      data-photo-filename="${escapeHtml(fileName)}"
    >
      <img
        src="${escapeHtml(preview)}"
        srcset="${srcset}"
        sizes="(max-width: 760px) 90vw, 280px"
        alt=""
        loading="lazy"
        decoding="async"
        width="1000"
        height="563"
      >
    </div>
  `
}

function featuresBlock(item, isDynamic, surfaceCount = 0) {
  const light = String(item?.light || '')
    .trim()
    .toLowerCase()
  const hasLight = ['да', 'yes', 'true', '1'].includes(light)

  const dyn = Boolean(isDynamic)

  /* Кол-во поверхностей стороны — как «динамика (5)» в списке.
     Показываем только у динамики (не у видеоэкрана: он сюда не попадает)
     и только если это разрешено настройкой show_dyn_count. */
  const count =
    showDynCount.value && Number(surfaceCount) > 0
      ? `<span class="dyn-count">(${escapeHtml(String(surfaceCount))})</span>`
      : ''

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
        <span class="feature-dyn">
          <span class="dyn-word ${dyn ? '' : 'is-active'}">статика</span>
          <span class="dyn-sep">/</span>
          <span class="dyn-word ${dyn ? 'is-active' : ''}">динамика</span>${count}
        </span>
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
      ${featuresBlock(item, false)}
      ${photoBlock(item)}
      ${monthBlock(item)}
    </section>
  `
}

/* Динамическая сторона: фото первой поверхности + строки месяцев.
 * Букву стороны (A(1), A(2)…) перед месяцами не пишем.
 * В режиме «по сторонам» — одна строка: месяц свободен, если свободна
 * хоть одна поверхность, иначе продано (резерв не показываем). */
function sideAggMonthCell(group, month) {
  const freeIds = (group.items || [])
    .filter(item => isFree(item, month.full))
    .map(item => surfaceIdOf(item))
    .filter(id => id !== null)

  const anyFree = freeIds.length > 0
  const state = anyFree ? 'free' : 'busy'
  const title = anyFree ? 'Свободно' : 'Продано'

  /*
   * В режиме «по сторонам» отдельной ячейки на каждую поверхность нет,
   * поэтому агрегированная ячейка несёт СПИСОК id свободных поверхностей
   * стороны. Клик добавляет/убирает месяц сразу у всех (см. onDocumentClick).
   * Без этого из динамической половины в портфель нельзя было ничего добавить.
   */
  const selected = freeIds.some(id => portfolio.isMonthSelected(id, month.full))

  const pfAttrs = freeIds.length
    ? ` data-pf-month="${escapeHtml(freeIds.join(','))}|${escapeHtml(month.full)}"`
    : ''

  return `
    <button
      type="button"
      class="popup-month ${state}${selected ? ' is-selected' : ''}${freeIds.length ? '' : ' is-locked'}"
      aria-pressed="${selected ? 'true' : 'false'}"
      title="${escapeHtml(title)}"${pfAttrs}
    >
      ${escapeHtml(month.short)}
    </button>
  `
}

function dynamicRowsBlock(group) {
  if (availableMode.value === 'sides') {
    return `
      <div class="popup-dynamic-rows">
        <div class="popup-dynamic-row">
          ${MONTHS.map(month => sideAggMonthCell(group, month)).join('')}
        </div>
      </div>
    `
  }

  return `
    <div class="popup-dynamic-rows">
      ${group.items
        .map(
          item => `
        <div class="popup-dynamic-row">
          <span class="popup-dynamic-side">${escapeHtml(sideLabel(item))}</span>
          ${MONTHS.map(month => monthCell(item, month)).join('')}
        </div>
      `
        )
        .join('')}
    </div>
  `
}

function dynamicBlock(group) {
  const first = group.items[0]

  return `
    <section class="popup-side-card popup-side-card--dynamic">
      <div class="popup-side-top">
        ${sideBlock({ ...first, side: parentSide(sideLabel(first), first.type) })}
        ${priceBlock(first)}
      </div>
      ${typeBlock(first)}
      ${featuresBlock(first, true, group.items.length)}
      ${photoBlock(first)}
      ${dynamicRowsBlock(group)}
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
      ${featuresBlock(item, true)}
      ${photoBlock(item)}
      ${videoMonthBlock(item)}
    </section>
  `
}

function renderGroup(group) {
  const first = group.items[0]

  if (group.kind === 'video') {
    return videoBlock(first)
  }

  if (group.kind === 'dynamic') {
    return dynamicBlock(group)
  }

  return sideCard(first)
}

/* ---------------------------------------------------------------- шапка */

function commonHeader(items) {
  const first = items[0] || {}

  const address = String(first?.address || first?.name || '').trim()

  const place = String(first?.city || first?.district || '').trim()

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

/*
 * Класс раскладки попапа — по ЧИСЛУ ВИДИМЫХ ГРУПП сторон, а не по сырому
 * числу сторон.
 *
 * Единый источник и для разметки (popupContent), и для выбора движком
 * ширины/обёртки маркера. Иначе получается рассинхрон: например, призматрон
 * A(1)+A(2)+A(3) — это 3 «сырые» стороны (движок считал попап двойным и
 * давал широкую обёртку/балон), хотя popupContent схлопывает их в одну
 * карточку → попап шире контента, пустое поле.
 */
const THREE_SIDE_SHIELD = {
  city: 'ростов-на-дону',
  address: 'стадионная ул.- фрунзе панно',
  number: '801'
}

function hasThreeSideShieldException(items) {
  return items.some(item => {
    const city = String(item?.city || '')
      .trim()
      .toLowerCase()
    const address = String(item?.address || '')
      .trim()
      .toLowerCase()
    const number = String(item?.number || '').trim()

    return (
      city === THREE_SIDE_SHIELD.city &&
      address === THREE_SIDE_SHIELD.address &&
      number === THREE_SIDE_SHIELD.number
    )
  })
}

function maxPopupBlocks(items) {
  return hasThreeSideShieldException(items) ? 3 : maxBlocksFor(familyOf(items))
}

export function popupLayout(input) {
  const items = normalizeSides(input)

  if (!items.length) {
    return 'single'
  }

  const sides = dedupeSides(items)
  const maxBlocks = maxPopupBlocks(sides)
  const count = Math.min(groupSides(sides).length, maxBlocks)

  return count === 3 ? 'triple' : count > 1 ? 'double' : 'single'
}

/*
 * Нормализация и группировка входа попапа — общая для разметки и для
 * сигнатуры кэша (см. popupContent / signatureOf).
 */
function prepare(input) {
  const items = normalizeSides(input)

  if (!items.length) {
    return { empty: true }
  }

  // Убираем дубликаты по стороне В ПРЕДЕЛАХ формата (порядок сохраняем):
  // одна и та же буква у разных форматов — это разные блоки.
  const sides = dedupeSides(items)

  // Семейство определяет число блоков; для конструкции 801 есть узкое
  // исключение, позволяющее показать все три отдельные стороны щита.
  const maxBlocks = maxPopupBlocks(sides)

  // Группируем по ФОРМАТУ и родительской стороне:
  // «Призматрон A(1)+A(2)+A(3)» → один блок, «Щит B» → отдельный.
  // Так разные форматы на одном адресе не смешиваются и не теряются.
  const groups = groupSides(sides)

  const visibleGroups = groups.slice(0, maxBlocks)
  const allSides = visibleGroups.flatMap(group => group.items)

  const layout = popupLayout(items)

  return { empty: false, layout, visibleGroups, allSides }
}

/*
 * Ключ кэша разметки: состав видимых групп + состояние портфеля для их
 * поверхностей + настройки внешнего вида. Если ничего из этого не
 * изменилось, готовую разметку можно не пересобирать.
 */
function signatureOf(ctx) {
  const parts = [
    ctx.layout,
    availableMode.value ? '1' : '0',
    showDynCount.value ? '1' : '0'
  ]

  for (const group of ctx.visibleGroups) {
    for (const item of group.items) {
      const id = surfaceIdOf(item)

      let months = ''

      for (const month of MONTHS) {
        months +=
          id !== null && portfolio.isMonthSelected(id, month.full) ? '1' : '0'
      }

      parts.push(String(id ?? ''), months)
    }
  }

  return parts.join('|')
}

/*
 * Кэш готовой разметки. Разметка зависит от состава группы, портфеля и
 * настроек внешнего вида — всё это входит в ключ, поэтому «протухнуть»
 * без смены ключа она не может. Ограничиваем размер, чтобы карта не
 * росла бесконечно.
 */
const contentCache = new Map()
const CONTENT_CACHE_MAX = 400

/*
 * Сброс кэша разметки. Нужен при загрузке нового набора конструкций:
 * тот же id поверхности может прийти уже с другими ценой/фото/статусом,
 * а ключ кэша этого не различает (внутри одного набора данных поля
 * поверхности не меняются).
 */
export function clearPopupContentCache() {
  contentCache.clear()
}

/* Собирает разметку попапа из подготовленного контекста. */
function buildContent(ctx) {
  const popupClass = `popup-${ctx.layout}`

  /*
   * Режим выбора включается не на корне, а на секции стороны —
   * состояние выбранных месяцев входит в signatureOf().
   */
  return `
    <div class="popup ${popupClass}">

      ${commonHeader(ctx.allSides)}

      <div class="popup-sides">

        ${ctx.visibleGroups.map(renderGroup).join('')}

      </div>

    </div>
  `
}

export function popupContent(input) {
  const ctx = prepare(input)

  if (ctx.empty) {
    return `
      <div class="popup-empty">
        Нет данных
      </div>
    `
  }

  const key = signatureOf(ctx)

  const cached = contentCache.get(key)

  if (cached !== undefined) {
    return cached
  }

  const html = buildContent(ctx)

  if (contentCache.size >= CONTENT_CACHE_MAX) {
    contentCache.clear()
  }

  contentCache.set(key, html)

  return html
}
