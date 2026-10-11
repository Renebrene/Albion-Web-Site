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

/*
 * Поверхность активна (розовая кнопка, кликабельные месяцы), если она
 * уже в портфеле или для неё включён режим выбора. Портфель переживает
 * перезагрузку (localStorage), режим — нет, поэтому учитываем оба.
 */
function isSurfaceActive(id) {
  return (
    id !== null &&
    id !== undefined &&
    id !== '' &&
    (portfolio.isInPortfolio(id) || portfolio.isSelectionMode(id))
  )
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
    <div
      class="popup-month ${monthState(item, month.full)}${selected ? ' is-selected' : ''}${locked ? ' is-locked' : ''}"
      title="${escapeHtml(getMonthStatusLabel(item, month.full))}"${pfAttrs}
    >
      ${escapeHtml(month.short)}
    </div>
  `
}

/*
 * Кнопка «Портфель» — одна на секцию попапа (после блока месяцев).
 * Если у поверхности нет id — разметку не добавляем, попап не ломаем.
 */
function portfolioBlock(item) {
  const surfaceId = surfaceIdOf(item)

  if (surfaceId === null) {
    return ''
  }

  const active = isSurfaceActive(surfaceId)

  return `
    <div class="popup-portfolio">
      <button
        type="button"
        class="popup-pf-toggle${active ? ' is-active' : ''}"
        data-pf-toggle="${escapeHtml(String(surfaceId))}"
        title="${active ? 'Убрать из портфеля' : 'Добавить в портфель'}"
      >
        <i class="material-icons popup-pf-icon">work_outline</i>
        <span class="popup-pf-label">Портфель</span>
      </button>
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

        const pfAttrs =
          surfaceId !== null
            ? ` data-pf-month="${escapeHtml(String(surfaceId))}|${escapeHtml(month.full)}"`
            : ''

        return `
          <div
            class="popup-month ${state} popup-month--video${selected ? ' is-selected' : ''}"
            title="${escapeHtml(title)}"${pfAttrs}
          >
            ${escapeHtml(month.short)}
          </div>
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
   * API отдаёт варианты одного фото: photo (card, 1000px),
   * photo_thumb (400px) и photo_large (2400px). Бэкенд может ещё
   * не отдавать thumb/large — тогда подставляем photo (фолбэк),
   * поэтому разметка не ломается на любом наборе полей.
   */
  const thumb = item?.photo_thumb || item?.photo || ''
  const card = item?.photo || thumb

  /* Крупный вариант карты-схемы — чтобы окно просмотра (как в портфеле)
     могло показать и сохранить карту рядом с фото. */
  const mapLarge = String(
    item?.map_large || item?.map_card || item?.map_thumb || item?.map || ''
  ).trim()

  if (!thumb) {
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
    item?.photo_thumb && `${escapeHtml(item.photo_thumb)} 400w`,
    item?.photo && `${escapeHtml(item.photo)} 1000w`,
    item?.photo_large && `${escapeHtml(item.photo_large)} 2400w`
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
        src="${escapeHtml(thumb)}"
        srcset="${srcset}"
        sizes="(max-width: 480px) 340px, 780px"
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

/*
 * Режим выбора месяцев для СЕКЦИИ попапа.
 *
 * У каждой «половины» карточки своя кнопка «Портфель», поэтому режим
 * включается по секции: активная сторона не делает кликабельными
 * месяцы соседней.
 */
function groupActive(items) {
  return (items || []).some(item => isSurfaceActive(surfaceIdOf(item)))
}

/* ---------------------------------------------------------------- блоки */

/* Статичная сторона: обычная карточка */
function sideCard(item) {
  const mode = isSurfaceActive(surfaceIdOf(item)) ? ' pf-mode' : ''

  return `
    <section class="popup-side-card${mode}">
      <div class="popup-side-top">
        ${sideBlock(item)}
        ${priceBlock(item)}
      </div>
      ${typeBlock(item)}
      ${featuresBlock(item, false)}
      ${photoBlock(item)}
      ${monthBlock(item)}
      ${portfolioBlock(item)}
    </section>
  `
}

/* Динамическая сторона: фото первой поверхности + строки месяцев.
 * Букву стороны (A(1), A(2)…) перед месяцами не пишем.
 * В режиме «по сторонам» — одна строка: месяц свободен, если свободна
 * хоть одна поверхность, иначе продано (резерв не показываем). */
function sideAggMonthCell(group, month) {
  const anyFree = (group.items || []).some(item => isFree(item, month.full))
  const state = anyFree ? 'free' : 'busy'
  const title = anyFree ? 'Свободно' : 'Продано'

  return `
    <div class="popup-month ${state}" title="${escapeHtml(title)}">
      ${escapeHtml(month.short)}
    </div>
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
  const mode = groupActive(group.items) ? ' pf-mode' : ''

  return `
    <section class="popup-side-card popup-side-card--dynamic${mode}">
      <div class="popup-side-top">
        ${sideBlock({ ...first, side: parentSide(sideLabel(first), first.type) })}
        ${priceBlock(first)}
      </div>
      ${typeBlock(first)}
      ${featuresBlock(first, true, group.items.length)}
      ${photoBlock(first)}
      ${dynamicRowsBlock(group)}
      ${portfolioBlock(first)}
    </section>
  `
}

/* Видеоэкран: всегда динамический, месяцы в одну строку */
function videoBlock(item) {
  const mode = isSurfaceActive(surfaceIdOf(item)) ? ' pf-mode' : ''

  return `
    <section class="popup-side-card popup-side-card--video${mode}">
      <div class="popup-side-top">
        ${sideBlock(item)}
        ${priceBlock(item)}
      </div>
      ${typeBlock(item)}
      ${featuresBlock(item, true)}
      ${photoBlock(item)}
      ${videoMonthBlock(item)}
      ${portfolioBlock(item)}
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
export function popupLayout(input) {
  const items = normalizeSides(input)

  if (!items.length) {
    return 'single'
  }

  const sides = dedupeSides(items)
  const maxBlocks = maxBlocksFor(familyOf(sides))
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

  // Семейство определяет число блоков:
  // пиллар — до 3, пилон/скроллер — 2,
  // адреса с щитом/призматроном/видеоэкраном — 2 (или 1, если одна сторона).
  const maxBlocks = maxBlocksFor(familyOf(sides))

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

      parts.push(String(id ?? ''), isSurfaceActive(id) ? '1' : '0', months)
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
   * см. groupActive()/isSurfaceActive() в построителях блоков.
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
