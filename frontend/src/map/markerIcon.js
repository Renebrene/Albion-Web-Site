import L from 'leaflet'
import { getAvailabilityState, getMonthValue } from '../utils/availability'

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

const ALL_MONTHS = [
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь'
]

function isVideoScreen(item) {
  return String(item?.type || '')
    .trim()
    .toLowerCase()
    .includes('видеоэкран')
}

/*
 * Нормализуем состояние одного месяца.
 *
 * Для видеоэкранов:
 * 100% / Продано / Занято = ЗАНЯТО
 * всё остальное = СВОБОДНО
 *
 * Для остальных конструкций:
 * Продано / Занято = ЗАНЯТО
 * всё остальное считаем свободным,
 * кроме Резерв / Утверждение — они тоже являются
 * свободными с точки зрения общей цветовой индикации.
 */
function isBusy(item, value) {
  const raw = String(value ?? '').trim()

  if (!raw) {
    return false
  }

  const state = getAvailabilityState(
    {
      ...item,
      months: item?.months,
      statuses: {
        ...(item?.statuses || {}),
        __marker_value__: raw
      }
    },
    '__marker_value__'
  )

  return state === 'busy'
}


/*
 * Цвет конструкции определяется ТОЛЬКО
 * по месяцам, выбранным пользователем.
 *
 * ВСЕ заняты → красный
 * ВСЕ свободны → зелёный
 * часть занята + часть свободна → оранжевый
 */
function getColor(item, selectedMonths = []) {
  const months =
    Array.isArray(selectedMonths) && selectedMonths.length
      ? selectedMonths
      : ALL_MONTHS

  const states = months.map(month => ({
    month,
    busy: isBusy(item, getMonthValue(item, month))
  }))

  const busyCount = states.filter(state => state.busy).length

  // Все выбранные месяцы заняты
  if (busyCount === states.length) {
    return '#e24b42'
  }

  // Ни одного занятого месяца
  if (busyCount === 0) {
    return '#2ea66d'
  }

  // Есть и занятые, и свободные
  return '#e6a51c'
}

export function markerIcon(item, selectedMonths = []) {
  const color = getColor(item, selectedMonths)

  return L.divIcon({
    className: 'albion-dot-wrapper',

    html: `
      <div
        class="albion-dot"
        style="background:${color}"
        title="${escapeHtml(
          item?.address ||
          item?.name ||
          ''
        )}"
      ></div>
    `,

    iconSize: [16, 16],
    iconAnchor: [8, 8]
  })
}
