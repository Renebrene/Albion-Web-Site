import { adminAuthHeaders } from './adminMedia'

/*
 * Медиатека конструкций — это каталог превью (отдельно от медиатеки сайта).
 * Переопределение фото сохраняется во временный каталог и применяется на всём
 * сайте, но действует только до следующего обновления базы (импорта).
 */

/* Каталог превью: фото/карты конструкций из базы (/api/constructions). */
export async function fetchConstructionPreviews() {
  const response = await fetch('/api/constructions')

  if (!response.ok) {
    throw new Error(`Не удалось загрузить каталог (${response.status})`)
  }

  const data = await response.json()

  if (!Array.isArray(data)) {
    return []
  }

  const seen = new Set()
  const result = []

  for (const item of data) {
    const url = item.photo_large || item.photo || ''

    if (!url || seen.has(url)) {
      continue
    }

    seen.add(url)

    result.push({
      id: item.id,
      url,
      thumb: item.photo_thumb || item.photo || url,
      surface_hash: item.surface_hash || '',
      label:
        [item.city, item.address]
          .map(value => String(value || '').trim())
          .filter(Boolean)
          .join(', ') ||
        item.type ||
        'Конструкция'
    })
  }

  return result
}

/* Переопределяет фото конструкции (файлом или копией из каталога). */
export async function setConstructionPhotoOverride({
  surface_hash,
  media_type = 'photo',
  file,
  sourceUrl
}) {
  const formData = new FormData()

  formData.append('surface_hash', surface_hash)
  formData.append('media_type', media_type)

  if (file) {
    formData.append('file', file)
  } else if (sourceUrl) {
    formData.append('source_url', sourceUrl)
  }

  const response = await fetch('/api/admin/constructions/media/override', {
    method: 'POST',
    headers: adminAuthHeaders(),
    body: formData
  })

  if (response.status === 401) {
    sessionStorage.removeItem('albion_admin_token')
    throw new Error('Сессия истекла. Войдите заново.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error((data && data.detail) || 'Не удалось переопределить фото')
  }

  return data?.override || null
}

/* Снимает переопределение фото конструкции. */
export async function clearConstructionPhotoOverride({
  surface_hash,
  media_type = 'photo'
}) {
  const params = new URLSearchParams({ surface_hash, media_type })

  const response = await fetch(
    `/api/admin/constructions/media/override?${params}`,
    { method: 'DELETE', headers: adminAuthHeaders() }
  )

  if (!response.ok) {
    throw new Error('Не удалось снять переопределение')
  }

  return true
}

/*
 * Временное переопределение основных полей конструкции (адрес, город, район,
 * тип, размер, сторона, свет, материал, номер). Действует на всём сайте до
 * следующего обновления базы.
 */
export async function setConstructionFieldOverride({ surface_hash, fields }) {
  const response = await fetch('/api/admin/constructions/media/fields', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminAuthHeaders() },
    body: JSON.stringify({ surface_hash, fields })
  })

  if (response.status === 401) {
    sessionStorage.removeItem('albion_admin_token')
    throw new Error('Сессия истекла. Войдите заново.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error((data && data.detail) || 'Не удалось сохранить изменения')
  }

  return data?.override || null
}

/* Снимает переопределение полей конструкции. */
export async function clearConstructionFieldOverride({ surface_hash }) {
  const params = new URLSearchParams({ surface_hash })

  const response = await fetch(
    `/api/admin/constructions/media/fields?${params}`,
    { method: 'DELETE', headers: adminAuthHeaders() }
  )

  if (!response.ok) {
    throw new Error('Не удалось снять переопределение')
  }

  return true
}

export async function setConstructionMonthOverride({ surface_hash, months }) {
  const response = await fetch('/api/admin/constructions/media/months', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...adminAuthHeaders() },
    body: JSON.stringify({ surface_hash, months })
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(data?.detail || 'Не удалось сохранить цены и статусы')
  }
  return data?.override || null
}

export async function clearConstructionMonthOverride({ surface_hash }) {
  const params = new URLSearchParams({ surface_hash })
  const response = await fetch(
    `/api/admin/constructions/media/months?${params}`,
    { method: 'DELETE', headers: adminAuthHeaders() }
  )
  if (!response.ok) throw new Error('Не удалось сбросить цены и статусы')
  return true
}
