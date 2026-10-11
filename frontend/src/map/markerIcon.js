import L from 'leaflet'
import { getAvailabilityState, getMonthValue } from '../utils/availability'
import { mapDotColors } from '../config/mapColors'
import { MONTHS } from '../utils/constructionGroups'

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
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
        ...item?.statuses,
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
      : MONTHS.map(month => month.full)

  const states = months.map(month => ({
    month,
    busy: isBusy(item, getMonthValue(item, month))
  }))

  const busyCount = states.filter(state => state.busy).length

  // Все выбранные месяцы заняты
  if (busyCount === states.length) {
    return mapDotColors.value.busy
  }

  // Ни одного занятого месяца
  if (busyCount === 0) {
    return mapDotColors.value.free
  }

  // Есть и занятые, и свободные
  return mapDotColors.value.mixed
}

export function markerIcon(item, selectedMonths = []) {
  const color = getColor(item, selectedMonths)

  return L.divIcon({
    className: 'albion-dot-wrapper',

    html: `
      <div
        class="albion-dot"
        style="background:${color}"
        title="${escapeHtml(item?.address || item?.name || '')}"
      ></div>
    `,

    iconSize: [16, 16],
    iconAnchor: [8, 8]
  })
}
