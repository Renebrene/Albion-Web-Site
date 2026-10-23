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

/*
 * Cookie-сессии (TZ 2.1). Токен сессии лежит в HttpOnly-cookie и JS его
 * не видит; рядом сервер ставит два читаемых: CSRF-токен для заголовка
 * X-CSRF-Token и маркер «сессия есть» — по нему гвард роутера решает,
 * пускать ли на админскую страницу (настоящую проверку делает сервер).
 */
const ADMIN_CSRF_COOKIE = 'albion_admin_csrf'
const ADMIN_AUTH_COOKIE = 'albion_admin_auth'

/* Адрес страницы входа: туда уводим при истёкшей сессии. */
const ADMIN_LOGIN_PATH = '/administration'

function readCookie(name) {
  if (typeof document === 'undefined') {
    return ''
  }

  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=([^;]*)`)
  )

  return match ? decodeURIComponent(match[1]) : ''
}

function expireCookie(name) {
  if (typeof document !== 'undefined') {
    document.cookie = `${name}=; max-age=0; path=/`
  }
}

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

/*
 * Есть ли сессия админки: либо cookie-маркер, либо старый Bearer-токен
 * (пока режим не переключён). Проверка только для навигации — данные
 * всё равно защищает сервер.
 */
export function hasAdminSession() {
  return Boolean(readCookie(ADMIN_AUTH_COOKIE) || getAdminToken())
}

/* Полный выход на клиенте: токен и читаемые cookie сессии. */
export function clearAdminSession() {
  clearAdminToken()
  expireCookie(ADMIN_CSRF_COOKIE)
  expireCookie(ADMIN_AUTH_COOKIE)
}

/*
 * Заголовки админского запроса: Bearer (если остался токен) и CSRF для
 * cookie-режима.
 */
export function adminHeaders(extra = {}) {
  const headers = { ...extra }
  const token = getAdminToken()

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const csrf = readCookie(ADMIN_CSRF_COOKIE)

  if (csrf) {
    headers['X-CSRF-Token'] = csrf
  }

  return headers
}

/*
 * 401 значит, что сессия истекла или токен отозван. Показывать на
 * странице «Unauthorized» бессмысленно — уводим на вход. Перезагрузка
 * здесь уместна: состояние админки уже недействительно.
 */
function handleUnauthorized() {
  clearAdminSession()

  if (typeof window === 'undefined') {
    return
  }

  if (!window.location.pathname.startsWith(ADMIN_LOGIN_PATH)) {
    window.location.assign(ADMIN_LOGIN_PATH)
  }
}

/*
 * fetch с авторизацией и единой реакцией на 401.
 *
 * credentials задаём явно: в cookie-режиме сессия уходит только с
 * same-origin-запросами.
 */
export async function adminFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: 'same-origin',
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
