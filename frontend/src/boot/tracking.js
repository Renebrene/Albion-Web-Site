/*
 * Учёт заходов на страницы.
 *
 * SPA делает клиентскую навигацию, поэтому сервер не видит переходы между
 * страницами — шлём визит сами из router.afterEach на публичный
 * POST /api/track (sendBeacon, чтобы запрос не задерживал переход).
 *
 * Что НЕ трекаем:
 *   • админку (/administration) — это служебные страницы;
 *   • повтор того же пути подряд;
 *   • автоматизацию (navigator.webdriver) — чтобы тесты не портили статистику.
 *
 * IP на сервере не сохраняется; в БД попадают только путь, страна (по IP
 * в момент визита) и необратимый хеш посетителя.
 */
export default ({ router }) => {
  if (typeof window === 'undefined') {
    return
  }

  let lastPath = ''

  function shouldSkip(path) {
    if (!path || path.startsWith('/api') || path.startsWith('/storage')) {
      return true
    }

    // Админка — служебный раздел.
    if (path.startsWith('/administration')) {
      return true
    }

    // Автоматизация (headless/CI) не должна попадать в статистику.
    if (navigator.webdriver) {
      return true
    }

    // Один и тот же маршрут подряд (повторная навигация) не считаем.
    if (path === lastPath) {
      return true
    }

    return false
  }

  function externalReferrer() {
    const value = document.referrer || ''

    if (!value) {
      return null
    }

    try {
      const ref = new URL(value)

      // Внутренние переходы источником не считаем.
      if (ref.origin === window.location.origin) {
        return null
      }

      return value
    } catch {
      return null
    }
  }

  function sendVisit(path) {
    const body = JSON.stringify({
      path,
      referrer: externalReferrer()
    })

    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([body], { type: 'application/json' })

        if (navigator.sendBeacon('/api/track', blob)) {
          return
        }
      }
    } catch {
      /* фолбэк ниже */
    }

    try {
      fetch('/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true
      }).catch(() => {})
    } catch {
      /* трекинг не должен ломать навигацию */
    }
  }

  router.afterEach(to => {
    const path = to.fullPath || to.path || ''

    if (shouldSkip(path)) {
      return
    }

    lastPath = path
    sendVisit(path)
  })
}
