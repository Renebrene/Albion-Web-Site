import { computed, ref } from 'vue'

/*
 * Реактивное состояние личного кабинета.
 *
 * Состояние общее для всего приложения (singleton): модульные ref
 * создаются один раз, поэтому логин в шапке и данные на странице
 * /account всегда синхронны.
 */

const TOKEN_KEY = 'albion_account_token'
const API_URL = '/api'

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const account = ref(null)
const requests = ref([])
const loading = ref(false)
const error = ref('')

/*
 * Реквизиты для распечатки/копирования портфеля. Хранятся на бэкенде
 * (поле requisites у пользователя) и попадают в общий вывод портфеля.
 */
const REQUISITE_FIELDS = [
  'organization',
  'inn',
  'kpp',
  'address',
  'phone',
  'email',
  'contact'
]

function emptyRequisites() {
  const result = {}

  for (const field of REQUISITE_FIELDS) {
    result[field] = ''
  }

  return result
}

/*
 * Приводит любой ответ бэкенда к полному объекту реквизитов.
 * Неизвестные/отсутствующие поля становятся пустыми строками —
 * так фронтенд не падает, пока бэкенд ещё не отдаёт requisites.
 */
function normalizeRequisites(source) {
  const result = emptyRequisites()

  if (!source || typeof source !== 'object') {
    return result
  }

  for (const field of REQUISITE_FIELDS) {
    const value = source[field]

    result[field] = value === undefined || value === null ? '' : String(value)
  }

  return result
}

const requisites = ref(emptyRequisites())

const isAuthenticated = computed(() => Boolean(token.value))

function setToken(value) {
  token.value = value || ''

  if (value) {
    localStorage.setItem(TOKEN_KEY, value)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

/*
 * Единая обёртка над fetch:
 * - ошибки сервера приходят как JSON { detail },
 * - 4xx поднимаются как Error(detail).
 */
async function apiRequest(path, { method = 'GET', body, auth = false } = {}) {
  const headers = {}

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  if (auth && token.value) {
    headers.Authorization = `Bearer ${token.value}`
  }

  const options = { method, headers }

  if (body !== undefined) {
    options.body = JSON.stringify(body)
  }

  let response

  try {
    response = await fetch(`${API_URL}${path}`, options)
  } catch {
    throw new Error('Не удалось соединиться с сервером. Проверьте подключение.')
  }

  let data = null
  const contentType = response.headers.get('content-type') || ''

  if (contentType.includes('application/json')) {
    try {
      data = await response.json()
    } catch {
      data = null
    }
  }

  if (!response.ok) {
    throw new Error(
      (data && data.detail) || `Ошибка сервера (${response.status})`
    )
  }

  return data || {}
}

/* Общий сброс/установка состояния загрузки и ошибки. */
async function run(task) {
  loading.value = true
  error.value = ''

  try {
    return await task()
  } catch (exc) {
    error.value = exc && exc.message ? exc.message : 'Произошла ошибка'
    throw exc
  } finally {
    loading.value = false
  }
}

function clearError() {
  error.value = ''
}

async function login(loginValue, passwordValue) {
  return run(async () => {
    const data = await apiRequest('/account/login', {
      method: 'POST',
      body: { login: loginValue, password: passwordValue }
    })

    setToken(data.token)
    account.value = data.user || null
    requisites.value = normalizeRequisites(
      (data.user && data.user.requisites) || data.requisites
    )
    return data
  })
}

async function register({ login: loginValue, password, secret_phrase }) {
  return run(async () => {
    const data = await apiRequest('/account/register', {
      method: 'POST',
      body: { login: loginValue, password, secret_phrase }
    })

    setToken(data.token)
    account.value = data.user || null
    requisites.value = normalizeRequisites(
      (data.user && data.user.requisites) || data.requisites
    )
    return data
  })
}

async function logout() {
  loading.value = true
  error.value = ''

  try {
    if (token.value) {
      await apiRequest('/account/logout', { method: 'POST', auth: true })
    }
  } catch {
    /* даже при ошибке сервера локально выходим */
  } finally {
    setToken('')
    account.value = null
    requests.value = []
    requisites.value = emptyRequisites()
    loading.value = false
  }
}

async function loadMe() {
  if (!token.value) {
    account.value = null
    requests.value = []
    requisites.value = emptyRequisites()
    return null
  }

  try {
    return await run(async () => {
      const data = await apiRequest('/account/me', { auth: true })

      account.value = data.user || null
      requests.value = Array.isArray(data.requests) ? data.requests : []
      requisites.value = normalizeRequisites(
        (data.user && data.user.requisites) || data.requisites
      )
      return data
    })
  } catch {
    /* недействительный/просроченный токен — чистим молча */
    setToken('')
    account.value = null
    requests.value = []
    requisites.value = emptyRequisites()
    return null
  }
}

async function recover({ login: loginValue, secret_phrase, new_password }) {
  return run(async () => {
    const data = await apiRequest('/account/recover', {
      method: 'POST',
      body: { login: loginValue, secret_phrase, new_password }
    })

    return data
  })
}

/*
 * Создание заявки в ЛК.
 *
 * Требует авторизации. При успехе новая заявка сразу попадает в
 * общий список requests (свежие сверху — как отдаёт бэкенд).
 */
async function createRequest({ title, surface_id, payload } = {}) {
  return run(async () => {
    const body = { title: title || '' }

    if (surface_id !== undefined && surface_id !== null) {
      body.surface_id = surface_id
    }

    if (payload !== undefined && payload !== null) {
      body.payload = payload
    }

    const data = await apiRequest('/account/requests', {
      method: 'POST',
      auth: true,
      body
    })

    const request = data.request || null

    if (request) {
      requests.value = [request, ...requests.value]
    }

    return request
  })
}

/*
 * Сохранение реквизитов (Bearer-токен).
 *
 * Отправляем объект из 7 строковых полей; бэкенд возвращает сохранённый
 * объект. Если ответ обёрнут ({ requisites: {...} }) — разворачиваем,
 * а если полей в ответе нет, считаем сохранённым то, что отправили.
 */
async function saveRequisites(data) {
  return run(async () => {
    const payload = normalizeRequisites(data)

    const saved = await apiRequest('/account/requisites', {
      method: 'PUT',
      auth: true,
      body: payload
    })

    const candidate = (saved && saved.requisites) || saved
    const hasFields =
      candidate &&
      typeof candidate === 'object' &&
      REQUISITE_FIELDS.some(field => candidate[field] !== undefined)

    const result = normalizeRequisites(hasFields ? candidate : payload)

    requisites.value = result
    return result
  })
}

export function useAccount() {
  return {
    account,
    requests,
    requisites,
    isAuthenticated,
    loading,
    error,

    login,
    register,
    logout,
    recover,
    loadMe,
    createRequest,
    saveRequisites,
    clearError
  }
}
