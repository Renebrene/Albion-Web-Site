/*
 * SVG-значки рекламных конструкций для крупного масштаба карты.
 *
 * Модели лежат в папке `icons/` проекта и названы по формату
 * конструкции: billbord, digital, pillar, pilon, prismatron, scroller.
 * Копии для сборки — в `src/assets/construction-icons/`; их импортирует
 * Vite как строку, чтобы подкрашивать табло цветом доступности.
 * Рамка, стрелки и опора остаются чёрными, как в исходных моделях.
 *
 * Чтобы использовать другие модели, достаточно заменить файлы в
 * `src/assets/construction-icons/` — остальная логика (размер, якорь,
 * анимация появления) не меняется.
 */
import L from 'leaflet'

import billbordSvg from '../assets/construction-icons/billbord.svg?raw'
import digitalSvg from '../assets/construction-icons/digital.svg?raw'
import pillarSvg from '../assets/construction-icons/pillar.svg?raw'
import pilonSvg from '../assets/construction-icons/pilon.svg?raw'
import prismatronSvg from '../assets/construction-icons/prismatron.svg?raw'
import scrollerSvg from '../assets/construction-icons/scroller.svg?raw'

/* С какого зума вместо точек показываем модели конструкций. */
export const CONSTRUCTION_ICONS_MIN_ZOOM = 16

/* Цвет табло в исходных SVG; заменяется на цвет доступности. */
const SOURCE_PANEL_COLOR = '#E31E24'

const MODELS = {
  /* Щит: широкая панель на стойке (250 × 212). */
  billbord: {
    svg: billbordSvg,
    width: 40,
    ratio: 250 / 212
  },

  /* Видеоэкран с треугольником (129 × 139). */
  digital: {
    svg: digitalSvg,
    width: 34,
    ratio: 129 / 139
  },

  /* Пиллар: вертикальная панель на основании (99 × 152). */
  pillar: {
    svg: pillarSvg,
    width: 28,
    ratio: 99 / 152
  },

  /* Пилон: вертикальный щит на опоре (122 × 214). */
  pilon: {
    svg: pilonSvg,
    width: 26,
    ratio: 122 / 214
  },

  /* Призматрон: щит с рёбрами (250 × 212). */
  prismatron: {
    svg: prismatronSvg,
    width: 40,
    ratio: 250 / 212
  },

  /* Скроллер: горизонтальная панель на стойке (125 × 105). */
  scroller: {
    svg: scrollerSvg,
    width: 38,
    ratio: 125 / 105
  }
}

function iconKind(type) {
  const value = String(type || '')
    .trim()
    .toLowerCase()

  if (value.includes('видео') || value.includes('экран')) return 'digital'
  if (value.includes('пиллар')) return 'pillar'
  if (value.includes('пилон')) return 'pilon'
  if (value.includes('призма')) return 'prismatron'
  if (value.includes('скролл')) return 'scroller'
  if (value.includes('сити')) return 'pilon'

  return 'billbord'
}

/* Подставляем цвет доступности вместо красного табло исходной модели. */
function colorize(svg, color) {
  return String(svg).replaceAll(SOURCE_PANEL_COLOR, color)
}

/*
 * Готовый divIcon для Leaflet.
 *
 * animate — включить анимацию «вырастания из точки» (при переходе карты
 * на крупный зум или при появлении новой конструкции). При обычной смене
 * цвета/фильтра анимацию не перезапускаем.
 */
export function constructionIcon({ type, color, animate = false }) {
  const model = MODELS[iconKind(type)] || MODELS.billbord

  const width = model.width
  const height = Math.round(width / model.ratio)

  return L.divIcon({
    className: 'albion-construction-wrapper',

    html: `
      <div class="albion-construction-icon${animate ? ' is-growing' : ''}" aria-hidden="true">
        ${colorize(model.svg, color)}
      </div>
    `,

    iconSize: [width, height],
    iconAnchor: [width / 2, height],
    popupAnchor: [0, -height + 6]
  })
}
