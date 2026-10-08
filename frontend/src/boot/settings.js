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

export async function applySiteSettings() {
  let settings

  try {
    const response = await fetch('/api/settings')

    if (!response.ok) {
      return
    }

    settings = await response.json()
  } catch (exc) {
    /* оставляем дефолты из :root */
    return
  }

  if (!settings || typeof settings !== 'object') {
    return
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
}

export default applySiteSettings
