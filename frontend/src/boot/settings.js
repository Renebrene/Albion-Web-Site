// Загрузка и применение настроек внешнего вида публичного сайта.
//
// Бэкенд отдаёт значения строкового типа: GET /api/settings →
// { font_family, font_heading, font_size_base, heading_weight,
//   color_accent, color_background, color_text,
//   radius_cards, radius_buttons }
//
// Функция выставляет CSS-переменные на <html>, от которых зависят
// базовые стили (см. src/css/app.scss). При любой ошибке тихо выходим,
// оставляя значения по умолчанию, объявленные в :root.

import { setMapEngine } from '../config/mapConfig'
import {
  mapDotColors,
  setMapDotColors,
  setMapColorMode
} from '../config/mapColors'
import { setAvailableMode } from '../config/availableMode'
import { setShowDynCount } from '../config/dynCount'
import { setLazyPopups } from '../config/lazyPopups'
import { setUrlStateMode, setUrlStateTokenFormat } from '../config/urlStateMode'
import { applySiteFonts } from '../config/fontLoader'

const SYSTEM_FONT_STACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif"

function resolveFont(value) {
  if (!value || value === 'system') {
    return SYSTEM_FONT_STACK
  }

  // Пользовательское имя шрифта с фолбэком на Inter
  return `'${value}', Inter, sans-serif`
}

function resolveSize(value) {
  const size = Number.parseInt(value, 10)

  if (Number.isFinite(size) && size > 0) {
    return `${size}px`
  }

  return null
}

async function loadAndApply() {
  let settings

  try {
    const response = await fetch('/api/settings')

    if (!response.ok) {
      return null
    }

    settings = await response.json()
  } catch {
    /* оставляем дефолты из :root */
    return null
  }

  return applyAppearanceSettings(settings)
}

/*
 * Применяет объект настроек (ключи схемы → CSS-переменные и реактивные
 * конфиги). Публичный: админка вызывает его сразу после сохранения, чтобы
 * смена, например, режима доступности (`available_mode`) отражалась на
 * открытых страницах без перезагрузки.
 */
export function applyAppearanceSettings(settings) {
  if (!settings || typeof settings !== 'object') {
    return null
  }

  const root = document.documentElement
  const set = (name, value) => {
    if (value !== undefined && value !== null && value !== '') {
      root.style.setProperty(name, value)
    }
  }

  set('--albion-font-family', resolveFont(settings.font_family))
  set('--albion-font-heading', resolveFont(settings.font_heading))

  const fontSize = resolveSize(settings.font_size_base)
  if (fontSize) {
    set('--albion-font-size', fontSize)
  }

  set('--albion-heading-weight', settings.heading_weight)
  set('--albion-accent', settings.color_accent)
  set('--albion-bg', settings.color_background)
  set('--albion-text', settings.color_text)
  set('--albion-radius-cards', settings.radius_cards)
  set('--albion-radius-buttons', settings.radius_buttons)

  /* Оператор карты: 'osm' | 'yandex' (см. config/mapConfig.js). */
  setMapEngine(settings.map_engine)

  /* Логика цвета точек: 'three' | 'two' (см. config/mapColors.js). */
  setMapColorMode(settings.map_color_mode)

  /* Доступность в списке: 'surfaces' | 'sides' (см. config/availableMode.js). */
  setAvailableMode(settings.available_mode)

  /* Показ количества поверхностей у динамики (см. config/dynCount.js). */
  setShowDynCount(settings.show_dyn_count)

  /* Ленивые попапы карты (см. config/lazyPopups.js). */
  setLazyPopups(settings.map_lazy_popups)

  /* Формат ссылок: читаемый или компактный токен (см. config/urlStateMode.js). */
  setUrlStateMode(settings.url_state_mode)
  setUrlStateTokenFormat(settings.url_state_token_format)

  /*
   * Цвета точек на карте (см. config/mapColors.js). Применяем и в JS
   * (маркеры Leaflet/Яндекс), и как CSS-переменные — их используют
   * подписи статусов в попапах, чтобы палитра совпадала с точками.
   */
  setMapDotColors(settings)
  set('--albion-map-free', mapDotColors.value.free)
  set('--albion-map-busy', mapDotColors.value.busy)
  set('--albion-map-mixed', mapDotColors.value.mixed)

  /*
   * Веб-шрифты (Inter/Roboto/PT Sans/…) больше не в бандле — подгружаем
   * нужное семейство с Google Fonts только если выбран не 'system'.
   */
  applySiteFonts(settings)

  return settings
}

/*
 * Один запрос настроек на всё приложение (кэшируем промис).
 * Карта дожидается его, чтобы узнать выбранного оператора.
 */
let settingsPromise = null

export function ensureSiteSettings() {
  if (!settingsPromise) {
    settingsPromise = loadAndApply()
  }

  return settingsPromise
}

export function applySiteSettings() {
  return ensureSiteSettings()
}

/*
 * Живое обновление настроек: когда вкладка снова получает фокус, тихо
 * перечитываем их с сервера. Так правки, сделанные в админке в другой
 * вкладке, применяются на уже открытой публичной странице сразу же.
 * Админские страницы пропускаем — чтобы не спорить с формой настроек.
 */
let lastSettingsRefresh = 0

function refreshSettingsOnFocus() {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return
  }

  if (window.location.pathname.startsWith('/administration')) {
    return
  }

  const now = Date.now()

  if (now - lastSettingsRefresh < 2000) {
    return
  }

  lastSettingsRefresh = now

  fetch('/api/settings')
    .then(response => (response.ok ? response.json() : null))
    .then(settings => {
      if (settings) {
        applyAppearanceSettings(settings)
      }
    })
    .catch(() => {
      /* офлайн/ошибка — оставляем текущие значения */
    })
}

if (typeof window !== 'undefined' && typeof document !== 'undefined') {
  window.addEventListener('focus', refreshSettingsOnFocus)

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      refreshSettingsOnFocus()
    }
  })
}

export default applySiteSettings
