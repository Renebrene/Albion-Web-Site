/*
 * Разделы-теги медиатеки сайта.
 *
 * Загрузчик каждой страницы проставляет свой раздел по умолчанию:
 * новости → «Новости», слайды главной → «Слайдеры» и т.д. Потом в
 * медиахранилище теги можно править (см. AdministrationMediaPage).
 *
 * Медиа рекламных конструкций это не касается — у них своя подсистема.
 */
import { adminAuthHeaders } from '../services/adminMedia'

/* Раздел по типу страницы — единый список для загрузчиков. */
export const MEDIA_SECTION = {
  news: 'Новости',
  slides: 'Слайдеры',
  home: 'Главная',
  menu: 'Прочее',
  tiles: 'Прочее',
  contacts: 'Контакты',
  office: 'Офис',
  employees: 'Сотрудники',
  info: 'Информация',
  about: 'О компании',
  geography: 'География',
  documents: 'Документы',
  users: 'Пользователи',
  media: 'Медиа'
}

const cache = {}

/* id раздела по имени: ищем существующий, иначе создаём. */
export async function mediaCategoryId(name) {
  const key = String(name || '').trim()

  if (!key) {
    return null
  }

  if (cache[key]) {
    return cache[key]
  }

  const list = await fetch('/api/admin/media/categories', {
    headers: adminAuthHeaders()
  }).then(response => (response.ok ? response.json() : null))

  const existing = (list?.categories || []).find(item => item.name === key)

  if (existing) {
    cache[key] = existing.id
    return existing.id
  }

  const body = new URLSearchParams()
  body.append('name', key)

  const created = await fetch('/api/admin/media/categories', {
    method: 'POST',
    headers: adminAuthHeaders(),
    body
  }).then(response => (response.ok ? response.json() : null))

  const id = created?.category?.id ?? null

  if (id) {
    cache[key] = id
  }

  return id
}
