const API_URL = '/api'

async function request(url) {
  const response = await fetch(`${API_URL}${url}`)

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

export async function postJson(url, body) {
  const response = await fetch(`${API_URL}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    const error = new Error(data?.detail || `API error: ${response.status}`)
    error.status = response.status
    throw error
  }

  return data
}

export function getHealth() {
  return request('/health')
}

export function getConstructions() {
  return request('/constructions')
}

export function getAbout() {
  return request('/about')
}

export function getContacts() {
  return request('/contacts')
}

export function getPage(slug) {
  return request(`/pages/${encodeURIComponent(slug)}`)
}

export function getNews() {
  return request('/news')
}

export function getNewsItem(slug) {
  return request(`/news/${encodeURIComponent(slug)}`)
}

export function getInfo() {
  return request('/info')
}
