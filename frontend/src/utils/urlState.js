/*
 * Компактное состояние каталога для ссылки ?s=...
 *
 * Формат: v1-<base64url | base32 от UTF-8 JSON>.
 * Задача — не «шифрование», а самодостаточная строка, которую браузер
 * разбирает без запросов к серверу. Читаемая схема (?city=...&type=...)
 * остаётся основной; этот кодек используется в режиме compact.
 *
 * Версия в префиксе позволяет менять раскладку без поломки старых ссылок.
 */

import {
  FORMAT_BASE32,
  FORMAT_BASE64URL,
  decodeBytes,
  detectFormat,
  encodeBytes
} from './tokenCodec'

const TOKEN_VERSION = 'v1-'
const MAX_TOKEN_LENGTH = 512
const MAX_QUERY_LENGTH = 100
const MAX_ADDRESS_LENGTH = 200

const MODES = new Set(['map', 'list', 'point'])

function toArray(value) {
  if (value === undefined || value === null || value === '') {
    return []
  }

  const list = Array.isArray(value) ? value : [value]

  return list
    .flatMap(item => String(item).split(','))
    .map(item => item.trim())
    .filter(Boolean)
}

function toNumber(value) {
  const num = Number(value)

  return Number.isFinite(num) ? num : null
}

function validPoint(value) {
  const lat = toNumber(value?.lat)
  const lng = toNumber(value?.lng)

  if (lat === null || lng === null) {
    return null
  }

  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
    return null
  }

  return { lat, lng }
}

function normalizeState(input) {
  const source = input && typeof input === 'object' ? input : {}

  return {
    mode: MODES.has(source.mode) ? source.mode : 'map',
    cities: toArray(source.cities),
    types: toArray(source.types),
    months: toArray(source.months),
    monthLogic: source.monthLogic === 'AND' ? 'AND' : 'OR',
    searchQuery: String(source.searchQuery || '')
      .trim()
      .slice(0, MAX_QUERY_LENGTH),
    address: String(source.address || '')
      .trim()
      .slice(0, MAX_ADDRESS_LENGTH),
    point: validPoint(source.point),
    radius:
      toNumber(source.radius) !== null && toNumber(source.radius) > 0
        ? toNumber(source.radius)
        : null
  }
}

/* JSON с короткими ключами: меньше служебных символов. */
function stateToPayload(state) {
  const payload = {
    v: 1,
    m: state.mode,
    c: state.cities,
    t: state.types,
    mo: state.months,
    l: state.monthLogic
  }

  if (state.searchQuery) payload.q = state.searchQuery
  if (state.address) payload.a = state.address
  if (state.point) payload.p = [state.point.lat, state.point.lng]
  if (state.radius) payload.r = state.radius

  return payload
}

function payloadToState(payload) {
  if (!payload || typeof payload !== 'object') {
    return null
  }

  return normalizeState({
    mode: payload.m,
    cities: payload.c,
    types: payload.t,
    months: payload.mo,
    monthLogic: payload.l,
    searchQuery: payload.q,
    address: payload.a,
    point: Array.isArray(payload.p)
      ? { lat: payload.p[0], lng: payload.p[1] }
      : payload.p,
    radius: payload.r
  })
}

export function encodeUrlState(state, format = FORMAT_BASE64URL) {
  const normalized = normalizeState(state)
  const json = JSON.stringify(stateToPayload(normalized))
  const bytes = new TextEncoder().encode(json)
  const token = `${TOKEN_VERSION}${encodeBytes(bytes, format)}`

  if (token.length > MAX_TOKEN_LENGTH) {
    throw new Error('Состояние ссылки слишком велико')
  }

  return token
}

export function decodeUrlState(token) {
  const text = String(token || '').trim()

  if (!text.startsWith(TOKEN_VERSION)) {
    return null
  }

  const body = text.slice(TOKEN_VERSION.length)

  if (!body) {
    return null
  }

  const formats = [
    detectFormat(body),
    detectFormat(body) === FORMAT_BASE32 ? FORMAT_BASE64URL : FORMAT_BASE32
  ]

  for (const format of formats) {
    try {
      const bytes = decodeBytes(body, format)
      const payload = JSON.parse(new TextDecoder().decode(bytes))
      const state = payloadToState(payload)

      if (state) {
        return state
      }
    } catch {
      /* пробуем следующий алфавит */
    }
  }

  return null
}

/*
 * Текст состояния для админской панели проверки: удобно сравнить
 * исходные фильтры и результат декодирования.
 */
export function describeUrlState(state) {
  return JSON.stringify(normalizeState(state), null, 2)
}
