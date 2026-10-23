/*
 * Общие помощники админ-медиатеки: авторизация, загрузка файла в хранилище
 * сайта и построение URL превью. Используются компонентом MediaSourceButtons
 * и медиа-полями, чтобы не дублировать логику по страницам.
 */

import { adminHeaders } from './adminApi'

export function adminAuthHeaders() {
  return adminHeaders()
}

/*
 * Публичный URL медиа. Сервер в режиме albion отдаёт `url` с внешней
 * ссылкой; для старых записей и локального режима — /storage/<path>.
 */
export function mediaUrl(item) {
  if (!item) return ''
  if (item.url) return item.url

  return item.storage_path ? `/storage/${item.storage_path}` : ''
}

/* То же для варианта изображения (large/card/thumb). */
export function variantUrl(variant) {
  if (!variant) return ''
  if (variant.url) return variant.url

  return variant.storage_path ? `/storage/${variant.storage_path}` : ''
}

/* URL превью: для картинок/видео берём миниатюру (thumb/card), иначе сам файл. */
export function adminMediaThumbUrl(item) {
  if (!item) return ''

  const variants = Array.isArray(item.variants) ? item.variants : []
  const thumb = variants.find(variant => variant.variant === 'thumb')
  const card = variants.find(variant => variant.variant === 'card')
  const chosen = thumb || card

  if (chosen) return variantUrl(chosen)

  return mediaUrl(item)
}

/* Приводит ответ API к удобному виду и добавляет готовый URL. */
export function normalizeAdminMedia(raw) {
  if (!raw || raw.id == null) return null

  const storagePath = raw.storage_path || ''

  return {
    id: raw.id,
    original_name: raw.original_name || raw.name || '',
    storage_path: storagePath,
    mime_type: raw.mime_type || '',
    preview_path: raw.preview_path || null,
    storage_backend: raw.storage_backend || 'local',
    external_url: raw.external_url || null,
    external_key: raw.external_key || null,
    variants: Array.isArray(raw.variants) ? raw.variants : [],
    url: raw.url || (storagePath ? `/storage/${storagePath}` : '')
  }
}

/*
 * Загружает файл в медиатеку сайта (POST /api/admin/media).
 * Возвращает нормализованный медиа-объект; при ошибке бросает Error(detail).
 */
export async function uploadAdminMedia(
  file,
  { categoryId, originalName } = {}
) {
  const formData = new FormData()

  formData.append('file', file)
  formData.append('original_name', originalName || file.name || 'upload')

  const categories = Array.isArray(categoryId)
    ? categoryId
    : categoryId != null
      ? [categoryId]
      : []

  categories.forEach(id => formData.append('category_id', String(id)))

  const response = await fetch('/api/admin/media', {
    method: 'POST',
    headers: adminAuthHeaders(),
    body: formData
  })

  if (response.status === 401) {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    throw new Error('Сессия истекла. Войдите заново.')
  }

  const data = await response.json().catch(() => null)

  if (!response.ok) {
    throw new Error((data && data.detail) || 'Не удалось загрузить файл')
  }

  const media = normalizeAdminMedia(data?.media)

  if (!media) {
    throw new Error('Сервер не вернул данные файла')
  }

  return media
}
