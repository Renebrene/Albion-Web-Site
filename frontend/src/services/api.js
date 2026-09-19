const API_URL = '/api'

async function request(url) {
  const response = await fetch(`${API_URL}${url}`)

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
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
