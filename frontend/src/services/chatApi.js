const API_URL = '/api'

/*
 * Ответ ассистента может идти долго (LLM-fallback). Бэкенд ограничивает
 * этапы (20 с на ответ + 5 с в очереди), а прокси — 60 с, поэтому клиент
 * ждёт столько же, а не бесконечно: зависший запрос оставлял чат
 * заблокированным навсегда (loading не снимался).
 */
const REQUEST_TIMEOUT_MS = 60000
const RESET_TIMEOUT_MS = 15000

function requestError(message, code) {
  const error = new Error(message)

  error.code = code

  return error
}

async function request(url, options = {}) {
  const {
    signal: externalSignal,
    timeoutMs = REQUEST_TIMEOUT_MS,
    ...rest
  } = options

  const controller = new AbortController()
  let timedOut = false

  const abortFromExternal = () => controller.abort()

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort()
    } else {
      externalSignal.addEventListener('abort', abortFromExternal, {
        once: true
      })
    }
  }

  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  try {
    const response = await fetch(`${API_URL}${url}`, {
      ...rest,
      headers: {
        'Content-Type': 'application/json',
        ...rest.headers
      },
      signal: controller.signal
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      throw new Error(data.detail || `API error: ${response.status}`)
    }

    return data
  } catch (error) {
    /* Таймаут отличается от ручной отмены: в первом случае сообщение
       пользователя остаётся в истории, во втором — откатывается. */
    if (timedOut) {
      throw requestError('Помощник не ответил вовремя', 'timeout')
    }

    if (error?.name === 'AbortError') {
      throw requestError('Запрос отменён', 'aborted')
    }

    throw error
  } finally {
    clearTimeout(timer)
    externalSignal?.removeEventListener('abort', abortFromExternal)
  }
}

export function sendChatMessage(payload, signal) {
  return request('/chat/message', {
    method: 'POST',
    signal,
    body: JSON.stringify(payload)
  })
}

export function resetChat(sessionId) {
  return request('/chat/reset', {
    method: 'POST',
    timeoutMs: RESET_TIMEOUT_MS,
    body: JSON.stringify({ session_id: sessionId })
  })
}
