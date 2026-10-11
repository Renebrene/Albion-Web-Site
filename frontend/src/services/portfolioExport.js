import { unref } from 'vue'

import { useAccount } from '../composables/useAccount'
import { usePortfolio } from '../composables/usePortfolio'
import { MONTHS } from '../utils/constructionGroups'

/*
 * Экспорт/печать/почта/чат для портфеля.
 *
 * Все функции работают с текущим портфелем (singleton usePortfolio).
 * Второй аргумент `sourceItems` необязателен: если его не передать,
 * берётся актуальный список из портфеля через serialize().
 *
 * Название портфеля и реквизиты ЛК можно передать в options:
 *   { title, requisites }. Если не переданы — берутся из стора
 *   портфеля и аккаунта; при отсутствии — фолбэк и пустой блок.
 */

const API_URL = '/api'

// Прежний заголовок — фолбэк, когда название портфеля не задано.
const FALLBACK_TITLE = 'Портфель Albion'

// Максимальная длина названия — как в usePortfolio.
const TITLE_MAX = 120

/* Получатель писем портфеля — общий ящик отдела рекламы. */
const MAIL_TO = 'reclama@albion.su'

const { serialize, title: portfolioTitle } = usePortfolio()

/*
 * Реквизиты ЛК для шапки печати и подписи в тексте.
 * Пары «поле — подпись» задают и порядок вывода.
 */
const REQUISITE_FIELDS = [
  ['organization', 'Организация'],
  ['inn', 'ИНН'],
  ['kpp', 'КПП'],
  ['address', 'Адрес'],
  ['phone', 'Телефон'],
  ['email', 'E-mail'],
  ['contact', 'Контактное лицо']
]

/* Название портфеля: аргумент -> стор -> фолбэк. */
function resolveTitle(value) {
  if (value !== undefined && value !== null) {
    const text = String(value).trim().slice(0, TITLE_MAX)

    if (text) {
      return text
    }
  }

  const stored = unref(portfolioTitle)

  if (stored && String(stored).trim()) {
    return String(stored).trim().slice(0, TITLE_MAX)
  }

  return FALLBACK_TITLE
}

/*
 * Реквизиты: привести к объекту из строк (без крайних пробелов).
 * Принимает ref/plain, устойчиво к отсутствию useAccount().requisites.
 */
function normalizeRequisites(value) {
  const source = unref(value)
  const result = {}

  REQUISITE_FIELDS.forEach(([key]) => {
    const raw = source && typeof source === 'object' ? source[key] : ''

    result[key] = raw === null || raw === undefined ? '' : String(raw).trim()
  })

  return result
}

/* Непустые реквизиты в порядке REQUISITE_FIELDS. */
function requisitesEntries(value) {
  const source = normalizeRequisites(value)

  return REQUISITE_FIELDS.map(([key, label]) => ({
    key,
    label,
    value: source[key]
  })).filter(entry => entry.value !== '')
}

/* Реквизиты по умолчанию: из options, иначе из ЛК (если есть). */
function resolveRequisites(options) {
  if (options && typeof options === 'object' && options.requisites) {
    return normalizeRequisites(options.requisites)
  }

  return normalizeRequisites(useAccount().requisites)
}

/* Достаёт title/requisites из options с учётом второго аргумента-опций. */
function resolveOptions(sourceItems, options) {
  if (options && typeof options === 'object') {
    return options
  }

  if (
    sourceItems &&
    !Array.isArray(sourceItems) &&
    typeof sourceItems === 'object'
  ) {
    return sourceItems
  }

  return {}
}

// ---------------------------------------------------------------- утилиты

/* Приводит цену к числу («100 000», «1 500,50» -> 100000, 1500.5). */
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

/* Формат цен — как в проекте (Intl.NumberFormat, ru-RU). */
export function formatPrice(value) {
  const num = toNumber(value)

  if (num === null) {
    return '—'
  }

  return new Intl.NumberFormat('ru-RU').format(num)
}

/* Возвращает список позиций: переданный или актуальный из портфеля. */
function resolveItems(sourceItems) {
  if (Array.isArray(sourceItems)) {
    return sourceItems
  }

  return serialize().items
}

/*
 * Выбранные месяцы позиции в порядке MONTHS.
 * Возвращает [{ full, short, price, stale }].
 * Месяцы, которых нет в MONTHS, добавляются в конец.
 */
export function selectedMonths(item) {
  const months = (item && item.months) || {}
  const known = new Set(MONTHS.map(month => month.full))
  const result = []

  MONTHS.forEach(({ full, short }) => {
    const value = months[full]

    if (value) {
      result.push({
        full,
        short,
        price: toNumber(value.price),
        stale: Boolean(value.stale)
      })
    }
  })

  Object.entries(months).forEach(([full, value]) => {
    if (!known.has(full) && value) {
      result.push({
        full,
        short: full.slice(0, 3).toUpperCase(),
        price: toNumber(value.price),
        stale: Boolean(value.stale)
      })
    }
  })

  return result
}

/* Сумма цены позиции по всем выбранным месяцам. */
export function itemSum(item) {
  return selectedMonths(item).reduce(
    (sum, month) => sum + (month.price || 0),
    0
  )
}

/* Итоговая сумма всего портфеля. */
export function totalSum(items) {
  return (items || []).reduce((sum, item) => sum + itemSum(item), 0)
}

/* Подпись позиции: «город, адрес». */
function addressLabel(item) {
  const city = String((item && item.city) || '').trim()
  const address = String((item && item.address) || '').trim()

  return [city, address].filter(Boolean).join(', ') || 'Адрес не указан'
}

// ---------------------------------------------------------------- текст

/*
 * Текстовая версия портфеля — для буфера обмена, почты и черновика чата.
 */
export function portfolioText(sourceItems, options) {
  const items = resolveItems(sourceItems)
  const opts = resolveOptions(sourceItems, options)
  const withMaps = resolveWithMaps(sourceItems, options)
  const headTitle = resolveTitle(opts.title)
  const reqEntries = requisitesEntries(resolveRequisites(opts))

  if (!items.length) {
    return `${headTitle} пуст.`
  }

  const lines = [headTitle, '']

  items.forEach((item, index) => {
    const months = selectedMonths(item)

    lines.push(
      `${index + 1}. ${item.type || 'Формат не указан'} — ${addressLabel(item)}`
    )

    if (item.side) {
      lines.push(`   Сторона: ${item.side}`)
    }

    if (item.size) {
      lines.push(`   Размер: ${item.size}`)
    }

    const monthText = months.length
      ? months
          .map(month => {
            const price =
              month.price === null ? '' : ` — ${formatPrice(month.price)} ₽`
            const stale = month.stale ? ' (статус изменился)' : ''

            return `${month.full}${price}${stale}`
          })
          .join('; ')
      : 'ничего не выбрано'

    lines.push(`   Месяцы: ${monthText}`)

    lines.push(`   Сумма: ${formatPrice(itemSum(item))} ₽`)

    if (item.photo) {
      lines.push(`   Фото: ${item.photo}`)
    }

    /* Ссылка на карту — по публичному полю map, если оно есть. */
    if (withMaps && item.map) {
      lines.push(`   Карта: ${item.map}`)
    }
  })

  lines.push('')
  lines.push(`Позиций: ${items.length}`)
  lines.push(`Итого: ${formatPrice(totalSum(items))} ₽`)

  // Реквизиты — в конце, только непустые поля.
  if (reqEntries.length) {
    lines.push('')
    reqEntries.forEach(entry => {
      lines.push(`${entry.label}: ${entry.value}`)
    })
  }

  return lines.join('\n')
}

// ---------------------------------------------------------------- скачивание

/* Все форматы выгрузки (см. backend/services/portfolio_export.py). */
const EXPORT_FORMATS = [
  'xls',
  'xlsx',
  'doc',
  'docx',
  'pdf',
  'odt',
  'ods',
  'rtf',
  'csv',
  'txt',
  'md',
  'json'
]

/* Расширение файла по формату экспорта. */
function extensionFor(format) {
  const value = String(format || '').toLowerCase()

  return EXPORT_FORMATS.includes(value) ? value : 'bin'
}

/*
 * Инициирует скачивание blob через временную ссылку <a download>.
 */
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = filename
  link.style.display = 'none'

  document.body.appendChild(link)
  link.click()

  // Даём браузеру время начать загрузку, затем убираем мусор.
  window.setTimeout(() => {
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, 0)
}

/*
 * Флаг «Фото».
 * Поддерживаем оба вызова:
 *   downloadPortfolio(format, { withPhotos })       — опции вторым аргументом;
 *   downloadPortfolio(format, items, { withPhotos }) — опции третьим.
 */
function resolveWithPhotos(sourceItems, options) {
  if (options && typeof options === 'object') {
    return Boolean(options.withPhotos)
  }

  if (
    sourceItems &&
    !Array.isArray(sourceItems) &&
    typeof sourceItems === 'object'
  ) {
    return Boolean(sourceItems.withPhotos)
  }

  return false
}

/*
 * Флаг «Карта». Та же схема вызова, что и у resolveWithPhotos.
 */
function resolveWithMaps(sourceItems, options) {
  if (options && typeof options === 'object') {
    return Boolean(options.withMaps)
  }

  if (
    sourceItems &&
    !Array.isArray(sourceItems) &&
    typeof sourceItems === 'object'
  ) {
    return Boolean(sourceItems.withMaps)
  }

  return false
}

/*
 * Флаг «Полный вывод». Меняет только раскладку (фото и карта в один ряд
 * шириной 7.5 см, одинаковая высота). Та же схема вызова, что у фото/карты.
 */
function resolveFullOutput(sourceItems, options) {
  if (options && typeof options === 'object') {
    return Boolean(options.fullOutput)
  }

  if (
    sourceItems &&
    !Array.isArray(sourceItems) &&
    typeof sourceItems === 'object'
  ) {
    return Boolean(sourceItems.fullOutput)
  }

  return false
}

/*
 * Выгрузка портфеля в файл.
 * POST /api/portfolio/export?format=xlsx|docx|pdf
 * Тело: { title, items, with_photos, with_maps, full_output, requisites }.
 * Ответ — файл (blob).
 * options: { withPhotos, withMaps, fullOutput, title, requisites }.
 */
/*
 * Запрашивает собранный файл портфеля у backend и возвращает blob.
 * payload: { title, withPhotos, withMaps, fullOutput, requisites }.
 */
async function requestPortfolioFile(format, items, payload) {
  const response = await fetch(
    `${API_URL}/portfolio/export?format=${encodeURIComponent(format)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: payload.title,
        items,
        with_photos: payload.withPhotos,
        with_maps: payload.withMaps,
        full_output: payload.fullOutput,
        requisites: payload.requisites
      })
    }
  )

  if (!response.ok) {
    throw new Error(`Не удалось сформировать файл (${response.status})`)
  }

  return {
    blob: await response.blob(),
    filename: responseFilename(response)
  }
}

/*
 * Имя файла из заголовка Content-Disposition (сервер отдаёт его с датой).
 * Пусто — если заголовок недоступен; тогда вызывающий подставляет своё имя.
 */
function responseFilename(response) {
  const header = response.headers.get('Content-Disposition') || ''
  const match = header.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)

  return match ? match[1].trim() : ''
}

export async function downloadPortfolio(format, sourceItems, options) {
  const value = extensionFor(format)
  const opts = resolveOptions(sourceItems, options)
  const withPhotos = resolveWithPhotos(sourceItems, options)
  const withMaps = resolveWithMaps(sourceItems, options)
  const fullOutput = resolveFullOutput(sourceItems, options)
  const items = Array.isArray(sourceItems)
    ? sourceItems
    : resolveItems(sourceItems)

  const { blob, filename } = await requestPortfolioFile(value, items, {
    title: resolveTitle(opts.title),
    withPhotos,
    withMaps,
    fullOutput,
    requisites: resolveRequisites(opts)
  })

  triggerDownload(blob, filename || `albion-portfolio.${value}`)
}

// ---------------------------------------------------------------- печать

/* Экранирование HTML для печатной версии. */
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/*
 * «Полный вывод» для печати: позиция строкой текста, ниже фото и карта
 * в один ряд по ширине A4 (каждое 7.5 см, одинаковая высота 5 см,
 * object-fit: cover — не растягиваем). Одно изображение — тоже 7.5 см.
 */
function buildFullPrintHtml(items, withPhotos, withMaps, title, requisites) {
  const headTitle = resolveTitle(title)
  const reqEntries = requisitesEntries(requisites)

  const requisitesBlock = reqEntries.length
    ? `<div class="requisites">${reqEntries
        .map(
          entry =>
            `<span class="req"><span class="req-label">${escapeHtml(entry.label)}:</span> ${escapeHtml(entry.value)}</span>`
        )
        .join('')}</div>`
    : ''

  const blocks = items
    .map((item, index) => {
      const months = selectedMonths(item)

      const monthText = months.length
        ? months
            .map(month => {
              const price =
                month.price === null ? '' : ` (${formatPrice(month.price)} ₽)`
              const stale = month.stale ? ' ⚠' : ''

              return `${escapeHtml(month.full)}${escapeHtml(price)}${stale}`
            })
            .join(', ')
        : 'ничего не выбрано'

      const metaParts = []

      if (item.side) {
        metaParts.push(`Сторона: ${escapeHtml(item.side)}`)
      }

      if (item.size) {
        metaParts.push(`Размер: ${escapeHtml(item.size)}`)
      }

      /* Крупные варианты — для печати в 7.5 см; фолбэк на обычные. */
      const photoUrl =
        withPhotos && (item.photo_large || item.photo_thumb || item.photo || '')
      const mapUrl =
        withMaps && (item.map_large || item.map_card || item.map_thumb || '')

      /* Фото шире карты (9 см против 7.5), высота у обоих одна. */
      const images = [
        photoUrl
          ? `<img class="full-thumb full-thumb--photo" src="${escapeHtml(photoUrl)}" alt="">`
          : '',
        mapUrl
          ? `<img class="full-thumb full-thumb--map" src="${escapeHtml(mapUrl)}" alt="">`
          : ''
      ]
        .filter(Boolean)
        .join('')

      const imagesBlock = images
        ? `<div class="full-images">${images}</div>`
        : ''

      const metaBlock = metaParts.length
        ? `<div class="full-meta">${metaParts.join(' · ')}</div>`
        : ''

      return `
        <div class="full-item">
          <div class="full-head">${index + 1}. ${escapeHtml(
            item.type || 'Формат не указан'
          )} — ${escapeHtml(addressLabel(item))}</div>
          ${metaBlock}
          ${imagesBlock}
          <div class="full-months">Месяцы: ${monthText}</div>
          <div class="full-sum">Сумма: ${escapeHtml(
            formatPrice(itemSum(item))
          )} ₽</div>
        </div>
      `
    })
    .join('')

  return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(headTitle)}</title>
  <style>
    * { box-sizing: border-box; }
    @page { size: A4; margin: 1.5cm; }
    body {
      margin: 0;
      padding: 32px 40px;
      font-family: Arial, Helvetica, sans-serif;
      color: #17212b;
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    .meta { margin: 0 0 20px; color: #71808c; font-size: 12px; }
    .requisites {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 18px;
      margin: 0 0 16px;
      color: #52606a;
      font-size: 12px;
      line-height: 1.5;
    }
    .req { white-space: nowrap; }
    .req-label { color: #71808c; }
    .full-item {
      padding: 12px 0;
      border-bottom: 1px solid #e5e9ec;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .full-head { font-size: 14px; font-weight: 700; }
    .full-meta, .full-months {
      margin-top: 2px;
      color: #52606a;
      font-size: 12px;
    }
    .full-sum { margin-top: 2px; font-size: 13px; font-weight: 700; }
    /* Фото и карта — в один ряд; одинаковый бокс, без растягивания. */
    .full-images {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5cm;
      margin: 8px 0 4px;
    }
    /* Фото и карта — одинаковые: 8 × 5 см, ряд ровный. */
    .full-thumb {
      display: block;
      width: 8cm;
      height: 5cm;
      object-fit: cover;
      border: 1px solid #e3e8ec;
      border-radius: 4px;
    }
    .full-total {
      margin-top: 16px;
      font-size: 14px;
      font-weight: 700;
      text-align: right;
    }
    @media print {
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <h1>${escapeHtml(headTitle)}</h1>
  ${requisitesBlock}
  <p class="meta">Позиций: ${items.length} · Сформировано: ${escapeHtml(new Date().toLocaleString('ru-RU'))}</p>
  <div class="full-list">${blocks}</div>
  <div class="full-total">Итого: ${escapeHtml(formatPrice(totalSum(items)))} ₽</div>
</body>
</html>`
}

/* Собирает HTML печатной версии портфеля. */
export function buildPrintHtml(
  items,
  withPhotos = false,
  withMaps = false,
  fullOutput = false,
  title,
  requisites
) {
  if (fullOutput) {
    return buildFullPrintHtml(items, withPhotos, withMaps, title, requisites)
  }

  const headTitle = resolveTitle(title)
  const reqEntries = requisitesEntries(requisites)

  /* Блок реквизитов под заголовком — только непустые поля. */
  const requisitesBlock = reqEntries.length
    ? `<div class="requisites">${reqEntries
        .map(
          entry =>
            `<span class="req"><span class="req-label">${escapeHtml(entry.label)}:</span> ${escapeHtml(entry.value)}</span>`
        )
        .join('')}</div>`
    : ''

  const rows = items
    .map((item, index) => {
      const months = selectedMonths(item)

      const monthText = months.length
        ? months
            .map(month => {
              const price =
                month.price === null ? '' : ` (${formatPrice(month.price)} ₽)`
              const stale = month.stale ? ' ⚠' : ''

              return `${escapeHtml(month.full)}${escapeHtml(price)}${stale}`
            })
            .join(', ')
        : 'ничего не выбрано'

      /* Без колонки «Фото» показываем прежнюю ссылку на фото. */
      const photo =
        !withPhotos && item.photo
          ? `<div class="photo">Фото: <a href="${escapeHtml(item.photo)}">${escapeHtml(item.photo)}</a></div>`
          : ''

      /*
       * Для превью 70 px хватает миниатюры: картинка card весит ~136 КБ,
       * thumb — ~34 КБ. Если миниатюры нет (старые позиции), берём card.
       */
      const thumbUrl = item.photo_thumb || item.photo

      const photoCell = withPhotos
        ? `<td class="photo-cell">${
            thumbUrl
              ? `<img class="photo-thumb" src="${escapeHtml(thumbUrl)}" alt="">`
              : ''
          }</td>`
        : ''

      /* Карта-схема — локальный файл; card крупнее thumb, берём первым. */
      const mapUrl = item.map_card || item.map_large || item.map_thumb

      const mapCell = withMaps
        ? `<td class="photo-cell">${
            mapUrl
              ? `<img class="photo-thumb" src="${escapeHtml(mapUrl)}" alt="">`
              : ''
          }</td>`
        : ''

      return `
        <tr>
          <td class="num">${index + 1}</td>
          ${photoCell}
          ${mapCell}
          <td>
            <div class="format">${escapeHtml(item.type || '—')}</div>
            <div class="address">${escapeHtml(addressLabel(item))}</div>
            <div class="side">Сторона: ${escapeHtml(item.side || '—')}</div>
            <div class="months">Месяцы: ${monthText}</div>
            ${photo}
          </td>
          <td class="sum">${escapeHtml(formatPrice(itemSum(item)))} ₽</td>
        </tr>
      `
    })
    .join('')

  const photoHead = withPhotos ? '<th>Фото</th>' : ''
  const mapHead = withMaps ? '<th>Карта</th>' : ''
  const totalColspan = 2 + (withPhotos ? 1 : 0) + (withMaps ? 1 : 0)

  return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(headTitle)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 32px 40px;
      font-family: Arial, Helvetica, sans-serif;
      color: #17212b;
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    .meta { margin: 0 0 20px; color: #71808c; font-size: 12px; }
    .requisites {
      display: flex;
      flex-wrap: wrap;
      gap: 2px 18px;
      margin: 0 0 16px;
      color: #52606a;
      font-size: 12px;
      line-height: 1.5;
    }
    .req { white-space: nowrap; }
    .req-label { color: #71808c; }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      border-bottom: 1px solid #e5e9ec;
      padding: 10px 8px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }
    th { font-size: 11px; text-transform: uppercase; color: #71808c; }
    .num { width: 32px; color: #71808c; font-weight: 700; }
    .format { font-weight: 700; }
    .address { margin-top: 2px; }
    .side, .months, .photo {
      margin-top: 2px;
      color: #52606a;
      font-size: 12px;
    }
    .photo-cell { width: 82px; }
    .photo-thumb {
      display: block;
      width: 70px;
      height: auto;
      border-radius: 4px;
    }
    .sum { white-space: nowrap; font-weight: 700; text-align: right; }
    tfoot td {
      border: none;
      padding-top: 16px;
      font-weight: 700;
      font-size: 14px;
    }
    .total-label { text-align: right; }
    .total-sum { text-align: right; white-space: nowrap; }
    @media print {
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <h1>${escapeHtml(headTitle)}</h1>
  ${requisitesBlock}
  <p class="meta">Позиций: ${items.length} · Сформировано: ${escapeHtml(new Date().toLocaleString('ru-RU'))}</p>
  <table>
    <thead>
      <tr>
        <th>№</th>
        ${photoHead}
        ${mapHead}
        <th>Поверхность</th>
        <th>Сумма</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
    <tfoot>
      <tr>
        <td colspan="${totalColspan}" class="total-label">Итого:</td>
        <td class="total-sum">${escapeHtml(formatPrice(totalSum(items)))} ₽</td>
      </tr>
    </tfoot>
  </table>
</body>
</html>`
}

/*
 * Печать портфеля — это PDF, собранный из той же «doc»-раскладки
 * (тот же backend-экспорт, что «DOC»/«PDF»). Открываем PDF в новом окне
 * и вызываем системную печать. Если PDF не удалось получить (или окно
 * заблокировано) — откат на прежнюю печать из HTML.
 * options: { withPhotos, withMaps, fullOutput, title, requisites }.
 */
export async function printPortfolio(sourceItems, options) {
  const opts = resolveOptions(sourceItems, options)
  const withPhotos = resolveWithPhotos(sourceItems, options)
  const withMaps = resolveWithMaps(sourceItems, options)
  const fullOutput = resolveFullOutput(sourceItems, options)
  const items = Array.isArray(sourceItems)
    ? sourceItems
    : resolveItems(sourceItems)
  const title = resolveTitle(opts.title)
  const requisites = resolveRequisites(opts)

  /*
   * Окно открываем СИНХРОННО — до await. Иначе блокировщик всплывающих
   * окон обрежет window.open, вызванный уже вне обработчика клика.
   * Затем навигируем это окно на готовый PDF.
   */
  const win = window.open('', '_blank')

  try {
    const { blob } = await requestPortfolioFile('pdf', items, {
      title,
      withPhotos,
      withMaps,
      fullOutput,
      requisites
    })

    const url = URL.createObjectURL(blob)

    if (win) {
      win.location.href = url

      if (win.focus) {
        win.focus()
      }

      // Даём просмотрщику PDF отрисоваться, затем системная печать.
      window.setTimeout(() => {
        try {
          win.print()
        } catch {
          /* просмотрщик PDF сам предложит печать */
        }
      }, 1000)

      window.setTimeout(() => URL.revokeObjectURL(url), 60000)

      return
    }

    URL.revokeObjectURL(url)

    // Всплывающее окно заблокировано — печатаем HTML-версию.
    printPortfolioHtml(
      items,
      withPhotos,
      withMaps,
      fullOutput,
      title,
      requisites
    )
  } catch {
    if (win) {
      try {
        win.close()
      } catch {
        /* окно уже закрыто */
      }
    }

    printPortfolioHtml(
      items,
      withPhotos,
      withMaps,
      fullOutput,
      title,
      requisites
    )
  }
}

/* Прежняя печать: HTML-версия в новом окне или скрытом iframe. */
function printPortfolioHtml(
  items,
  withPhotos,
  withMaps,
  fullOutput,
  title,
  requisites
) {
  const html = buildPrintHtml(
    items,
    withPhotos,
    withMaps,
    fullOutput,
    title,
    requisites
  )

  const win = window.open('', '_blank', 'width=900,height=700')

  if (win) {
    win.document.open()
    win.document.write(html)
    win.document.close()
    win.focus()

    // Даём окну отрисоваться, затем вызываем системную печать.
    window.setTimeout(() => {
      win.print()
    }, 300)

    return
  }

  const iframe = document.createElement('iframe')

  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'

  document.body.appendChild(iframe)

  const doc = iframe.contentWindow.document

  doc.open()
  doc.write(html)
  doc.close()

  iframe.contentWindow.focus()
  iframe.contentWindow.print()

  window.setTimeout(() => {
    document.body.removeChild(iframe)
  }, 1000)
}

// ---------------------------------------------------------------- почта

/* Открывает почтовый клиент с готовым письмом (только клиент, без сервера). */
export function emailPortfolio(sourceItems, options) {
  const items = resolveItems(sourceItems)
  const opts = resolveOptions(sourceItems, options)
  const subject = resolveTitle(opts.title)
  const body = portfolioText(items, opts)

  window.location.href = `mailto:${MAIL_TO}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

// ---------------------------------------------------------------- буфер обмена

/*
 * Копирует текст в буфер обмена.
 * navigator.clipboard требует https/localhost; для прочих случаев
 * используем скрытый textarea + document.execCommand('copy').
 */
export async function copyToClipboard(text) {
  const value = String(text ?? '')

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value)

      return true
    } catch {
      /* уходим в фолбэк ниже */
    }
  }

  try {
    const area = document.createElement('textarea')

    area.value = value
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.top = '-1000px'
    area.style.opacity = '0'

    document.body.appendChild(area)
    area.select()

    const ok = document.execCommand('copy')

    document.body.removeChild(area)

    return ok
  } catch {
    return false
  }
}

/*
 * Готовит черновик обращения для «Умного чата»:
 * копирует текст в буфер и возвращает его для передачи в query.
 */
export async function chatDraft(sourceItems, options) {
  const text = portfolioText(sourceItems, options)
  const copied = await copyToClipboard(text)

  return { text, copied }
}
