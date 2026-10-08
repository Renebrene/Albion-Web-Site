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

    if (months.length) {
      const monthText = months
        .map(month => {
          const price =
            month.price === null ? '' : ` — ${formatPrice(month.price)} ₽`
          const stale = month.stale ? ' (статус изменился)' : ''

          return `${month.full}${price}${stale}`
        })
        .join('; ')

      lines.push(`   Месяцы: ${monthText}`)
    }

    lines.push(`   Сумма: ${formatPrice(itemSum(item))} ₽`)

    if (item.photo) {
      lines.push(`   Фото: ${item.photo}`)
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

/* Расширение файла по формату экспорта. */
function extensionFor(format) {
  const value = String(format || '').toLowerCase()

  if (['xlsx', 'docx', 'pdf'].includes(value)) {
    return value
  }

  return 'bin'
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
 * Флаг «Добавлять фото».
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
 * Выгрузка портфеля в файл.
 * POST /api/portfolio/export?format=xlsx|docx|pdf
 * Тело: { title, items, with_photos, requisites }. Ответ — файл (blob).
 * options: { withPhotos, title, requisites }.
 */
export async function downloadPortfolio(format, sourceItems, options) {
  const value = extensionFor(format)
  const opts = resolveOptions(sourceItems, options)
  const withPhotos = resolveWithPhotos(sourceItems, options)
  const items = Array.isArray(sourceItems)
    ? sourceItems
    : resolveItems(sourceItems)

  const response = await fetch(
    `${API_URL}/portfolio/export?format=${encodeURIComponent(value)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: resolveTitle(opts.title),
        items,
        with_photos: withPhotos,
        requisites: resolveRequisites(opts)
      })
    }
  )

  if (!response.ok) {
    throw new Error(`Не удалось сформировать файл (${response.status})`)
  }

  const blob = await response.blob()

  triggerDownload(blob, `albion-portfolio.${value}`)
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

/* Собирает HTML печатной версии портфеля. */
function buildPrintHtml(items, withPhotos = false, title, requisites) {
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
        : '—'

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

      return `
        <tr>
          <td class="num">${index + 1}</td>
          ${photoCell}
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
  const totalColspan = withPhotos ? 3 : 2

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
 * Печать портфеля: открываем новое окно с печатной версией.
 * Если всплывающее окно заблокировано — печатаем через скрытый iframe.
 * Второй аргумент: { withPhotos, title, requisites }.
 */
export function printPortfolio(sourceItems, options) {
  const opts = resolveOptions(sourceItems, options)
  const withPhotos = resolveWithPhotos(sourceItems, options)
  const items = Array.isArray(sourceItems)
    ? sourceItems
    : resolveItems(sourceItems)
  const html = buildPrintHtml(
    items,
    withPhotos,
    resolveTitle(opts.title),
    resolveRequisites(opts)
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
