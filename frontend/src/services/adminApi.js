/*
 * Единая точка админских запросов.
 *
 * Токен админки живёт в sessionStorage. Раньше его читали напрямую в 20+
 * местах и каждый раз вручную собирали заголовок — забыть его было легко,
 * а обработка 401 разъезжалась по страницам. Теперь все ходят через этот
 * модуль, и когда админка переедет на cookie-сессии (TZ 2.1), менять
 * придётся только здесь.
 */

const ADMIN_TOKEN_KEY = 'albion_admin_token'

/* Адрес страницы входа: туда уводим при истёкшей сессии. */
const ADMIN_LOGIN_PATH = '/administration'

export function getAdminToken() {
  try {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY) || ''
  } catch {
    /* приватный режим или запрет хранилища — считаем, что токена нет */
    return ''
  }
}

export function setAdminToken(token) {
  try {
    sessionStorage.setItem(ADMIN_TOKEN_KEY, token)
  } catch {
    /* токен проживёт до перезагрузки */
  }
}

export function clearAdminToken() {
  try {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
  } catch {
    /* чистить нечего */
  }
}

/* Заголовки админского запроса. Без токена — без Authorization. */
export function adminHeaders(extra = {}) {
  const token = getAdminToken()

  return token ? { ...extra, Authorization: `Bearer ${token}` } : { ...extra }
}

/*
 * 401 значит, что сессия истекла или токен отозван. Показывать на
 * странице «Unauthorized» бессмысленно — уводим на вход. Перезагрузка
 * здесь уместна: состояние админки уже недействительно.
 */
function handleUnauthorized() {
  clearAdminToken()

  if (typeof window === 'undefined') {
    return
  }

  if (!window.location.pathname.startsWith(ADMIN_LOGIN_PATH)) {
    window.location.assign(ADMIN_LOGIN_PATH)
  }
}

/* fetch с токеном и единой реакцией на 401. */
export async function adminFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: adminHeaders(options.headers || {})
  })

  if (response.status === 401) {
    handleUnauthorized()
  }

  return response
}

/*
 * adminFetch + JSON. Не-ok превращаем в Error с `detail` от сервера —
 * так страницы показывают понятный текст, а не «HTTP 500».
 */
export async function adminRequest(path, options = {}) {
  const response = await adminFetch(path, options)

  if (!response.ok) {
    let detail = response.statusText

    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch {
      /* ответ не JSON */
    }

    throw new Error(detail)
  }

  return response.json()
}
