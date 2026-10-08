import { usePortfolio } from '../composables/usePortfolio'
import { MONTHS } from '../utils/constructionGroups'

/*
 * Экспорт/печать/почта/чат для портфеля.
 *
 * Все функции работают с текущим портфелем (singleton usePortfolio).
 * Второй аргумент `sourceItems` необязателен: если его не передать,
 * берётся актуальный список из портфеля через serialize().
 */

const API_URL = '/api'
const EXPORT_TITLE = 'Портфель Albion'

/* Получатель писем портфеля — общий ящик отдела рекламы. */
const MAIL_TO = 'reclama@albion.su'

const { serialize } = usePortfolio()

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
export function portfolioText(sourceItems) {
  const items = resolveItems(sourceItems)

  if (!items.length) {
    return 'Портфель Albion пуст.'
  }

  const lines = ['Портфель Albion', '']

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
 * Тело: { title, items, with_photos }. Ответ — файл (blob).
 */
export async function downloadPortfolio(format, sourceItems, options) {
  const value = extensionFor(format)
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
        title: EXPORT_TITLE,
        items,
        with_photos: withPhotos
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
function buildPrintHtml(items, withPhotos = false) {
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
      const photo = !withPhotos && item.photo
        ? `<div class="photo">Фото: <a href="${escapeHtml(item.photo)}">${escapeHtml(item.photo)}</a></div>`
        : ''

      const photoCell = withPhotos
        ? `<td class="photo-cell">${
            item.photo
              ? `<img class="photo-thumb" src="${escapeHtml(item.photo)}" alt="">`
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
  <title>${escapeHtml(EXPORT_TITLE)}</title>
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
  <h1>${escapeHtml(EXPORT_TITLE)}</h1>
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
 * Второй аргумент: { withPhotos } — добавить колонку с превью фото.
 */
export function printPortfolio(sourceItems, options) {
  const withPhotos = resolveWithPhotos(sourceItems, options)
  const items = Array.isArray(sourceItems)
    ? sourceItems
    : resolveItems(sourceItems)
  const html = buildPrintHtml(items, withPhotos)

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
export function emailPortfolio(sourceItems) {
  const items = resolveItems(sourceItems)
  const subject = EXPORT_TITLE
  const body = portfolioText(items)

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
export async function chatDraft(sourceItems) {
  const text = portfolioText(sourceItems)
  const copied = await copyToClipboard(text)

  return { text, copied }
}
