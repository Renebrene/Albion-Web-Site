const API_URL = '/api'

async function request(url, options = {}) {
  const response = await fetch(`${API_URL}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || `API error: ${response.status}`)
  }

  return data
}

export function sendChatMessage(payload) {
  return request('/chat/message', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function resetChat(sessionId) {
  return request('/chat/reset', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId })
  })
}
