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
    loading.value = false
  }
}

async function loadMe() {
  if (!token.value) {
    account.value = null
    requests.value = []
    return null
  }

  try {
    return await run(async () => {
      const data = await apiRequest('/account/me', { auth: true })

      account.value = data.user || null
      requests.value = Array.isArray(data.requests) ? data.requests : []
      return data
    })
  } catch {
    /* недействительный/просроченный токен — чистим молча */
    setToken('')
    account.value = null
    requests.value = []
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

export function useAccount() {
  return {
    account,
    requests,
    isAuthenticated,
    loading,
    error,

    login,
    register,
    logout,
    recover,
    loadMe,
    clearError
  }
}
