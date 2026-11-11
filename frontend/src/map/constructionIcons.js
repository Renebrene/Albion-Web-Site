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

/*
 * На скольких последних уровнях увеличения показываем модели конструкций.
 * Порог считается от фактического maxZoom карты (для OSM это 19 → 17–19).
 */
export const CONSTRUCTION_ICONS_LAST_ZOOMS = 3

/* Цвет табло в исходных SVG; заменяется на цвет доступности. */
const SOURCE_PANEL_COLOR = '#E31E24'

/* Общая высота всех значков: ширина считается по пропорциям модели. */
const ICON_HEIGHT = 34

/*
 * Разброс анимации появления/исчезновения: значки не «прыгают» все
 * одновременно. Задержка и скорость — в миллисекундах, разные для
 * каждой иконки.
 */
const ANIMATION_DELAY_MAX = 180
const ANIMATION_DURATION_MIN = 280
const ANIMATION_DURATION_MAX = 500

function animationTiming() {
  const delay = Math.round(Math.random() * ANIMATION_DELAY_MAX)
  const duration = Math.round(
    ANIMATION_DURATION_MIN +
      Math.random() * (ANIMATION_DURATION_MAX - ANIMATION_DURATION_MIN)
  )

  return { delay, duration }
}

const MODELS = {
  /* Щит: широкая панель на стойке (250 × 212). */
  billbord: {
    svg: billbordSvg,
    ratio: 250 / 212
  },

  /* Видеоэкран с треугольником (129 × 139). */
  digital: {
    svg: digitalSvg,
    ratio: 129 / 139
  },

  /* Пиллар: вертикальная панель на основании (99 × 152). */
  pillar: {
    svg: pillarSvg,
    ratio: 99 / 152
  },

  /* Пилон: вертикальный щит на опоре (122 × 214). */
  pilon: {
    svg: pilonSvg,
    ratio: 122 / 214
  },

  /* Призматрон: щит с рёбрами (250 × 212). */
  prismatron: {
    svg: prismatronSvg,
    ratio: 250 / 212
  },

  /* Скроллер: горизонтальная панель на стойке (125 × 105). */
  scroller: {
    svg: scrollerSvg,
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

/* Одна грань значка: своя модель конструкции. */
function faceHtml(type, color, className) {
  const model = MODELS[iconKind(type)] || MODELS.billbord

  return `
    <div class="albion-construction-face ${className}">
      ${colorize(model.svg, color)}
    </div>
  `
}

/*
 * Готовый divIcon для Leaflet.
 *
 * types — форматы, стоящие в одной точке. Если их два, значок получает две
 * грани: при повороте показывается модель соответствующего формата
 * (как у призматрона), а не зеркальное отражение той же картинки.
 *
 * animate — включить анимацию «вырастания из точки». При обычной смене
 * цвета/фильтра анимацию не перезапускаем.
 */
export function constructionIcon({
  type,
  types,
  color,
  animate = false,
  spin = false
}) {
  const formats = (Array.isArray(types) && types.length ? types : [type]).slice(
    0,
    2
  )

  const frontType = formats[0]
  const backType = formats[1]

  const model = MODELS[iconKind(frontType)] || MODELS.billbord

  /* Высота едина у всех форматов, ширина — по пропорциям модели. */
  const height = ICON_HEIGHT
  const width = Math.round(height * model.ratio)

  const classes = [
    'albion-construction-icon',
    animate ? 'is-growing' : '',
    spin && backType ? 'is-spinning' : ''
  ]
    .filter(Boolean)
    .join(' ')

  const faces =
    spin && backType
      ? faceHtml(frontType, color, 'is-front') +
        faceHtml(backType, color, 'is-back')
      : faceHtml(frontType, color, 'is-front')

  const timing = animationTiming()

  return L.divIcon({
    className: 'albion-construction-wrapper',

    html: `
      <div
        class="${classes}"
        style="--albion-icon-delay:${timing.delay}ms;--albion-icon-duration:${timing.duration}ms"
        aria-hidden="true"
      >
        ${faces}
      </div>
    `,

    iconSize: [width, height],
    iconAnchor: [width / 2, height],
    popupAnchor: [0, -height + 6]
  })
}
