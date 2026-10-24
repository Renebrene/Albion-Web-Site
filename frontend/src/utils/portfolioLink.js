/*
 * Портфель в ссылке: ?pf=v1-…
 *
 * Ссылка несёт ТОЛЬКО портфель — позиции (id поверхности) и выбранные
 * месяцы. Фильтры, режим и точка остаются в ?s=/?city=… (utils/urlState.js):
 * получателю важно увидеть те же позиции, а не повторить чужую выдачу.
 *
 * Формат: v1-<Base64Url | Base32 от UTF-8 JSON>, алфавит — из настроек
 * сайта (`url_state_token_format`), как и у ?s=.
 * Месяцы кодируются индексами по календарю (utils/constructionGroups.js),
 * поэтому кириллица в URL не попадает: примерно 3 символа на месяц.
 *
 * Предел длины выше, чем у состояния фильтров (512), потому что портфель —
 * список, а не набор фильтров. Замер: 20 позиций по 3 месяца — 725 знаков
 * (Base32), то есть ~36 знаков на позицию; 2000 знаков хватает примерно на
 * 55 позиций и остаётся далеко от пределов браузеров и nginx (8 КБ на
 * строку заголовка). Переполнение — понятная ошибка, ссылка не генерируется
 * (требование doc/url-state.md, §3).
 */

import { MONTH_ORDER } from './constructionGroups'
import {
  FORMAT_BASE32,
  FORMAT_BASE64URL,
  decodeBytes,
  detectFormat,
  encodeBytes
} from './tokenCodec'

const TOKEN_VERSION = 'v1-'
const MAX_TOKEN_LENGTH = 2000

/* Как в usePortfolio: длиннее название в ссылке не нужно. */
const TITLE_MAX = 120

/* Нечисловой id (на случай строковых ключей) — обрезаем, чтобы не раздувать токен. */
const ID_MAX = 40

function monthNumber(name) {
  const index = MONTH_ORDER.indexOf(String(name || ''))

  return index === -1 ? 0 : index + 1
}

function monthName(number) {
  return MONTH_ORDER[number - 1] || ''
}

function toId(value) {
  const text = String(value ?? '').trim()

  if (!text) {
    return null
  }

  return /^\d+$/.test(text) ? Number(text) : text.slice(0, ID_MAX)
}

function toPayload(source) {
  const items = Array.isArray(source?.items) ? source.items : []
  const payload = { v: 1, p: [] }

  const title = String(source?.title || '')
    .trim()
    .slice(0, TITLE_MAX)

  if (title) {
    payload.t = title
  }

  items.forEach(item => {
    const id = toId(item?.surfaceId)

    if (id === null) {
      return
    }

    const months = Object.keys(item?.months || {})
      .map(monthNumber)
      .filter(Boolean)
      .sort((left, right) => left - right)

    payload.p.push([id, months])
  })

  return payload
}

function fromPayload(payload) {
  if (!payload || typeof payload !== 'object' || payload.v !== 1) {
    return null
  }

  if (!Array.isArray(payload.p) || !payload.p.length) {
    return null
  }

  const items = payload.p
    .map(entry => {
      if (!Array.isArray(entry)) {
        return null
      }

      const surfaceId = toId(entry[0])

      if (surfaceId === null) {
        return null
      }

      const months = (Array.isArray(entry[1]) ? entry[1] : [])
        .map(value => monthName(Number(value)))
        .filter(Boolean)

      return { surfaceId: String(surfaceId), months }
    })
    .filter(Boolean)

  if (!items.length) {
    return null
  }

  return {
    items,
    title: String(payload.t || '')
      .trim()
      .slice(0, TITLE_MAX)
  }
}

export function encodePortfolioLink(source, format = FORMAT_BASE64URL) {
  const json = JSON.stringify(toPayload(source))
  const bytes = new TextEncoder().encode(json)
  const token = `${TOKEN_VERSION}${encodeBytes(bytes, format)}`

  if (token.length > MAX_TOKEN_LENGTH) {
    throw new Error('Портфель слишком большой для ссылки')
  }

  return token
}

export function decodePortfolioLink(token) {
  const text = String(token || '').trim()

  if (!text.startsWith(TOKEN_VERSION)) {
    return null
  }

  const body = text.slice(TOKEN_VERSION.length)

  if (!body || body.length > MAX_TOKEN_LENGTH) {
    return null
  }

  const formats = [
    detectFormat(body),
    detectFormat(body) === FORMAT_BASE32 ? FORMAT_BASE64URL : FORMAT_BASE32
  ]

  for (const format of formats) {
    try {
      const payload = JSON.parse(
        new TextDecoder().decode(decodeBytes(body, format))
      )
      const shared = fromPayload(payload)

      if (shared) {
        return shared
      }
    } catch {
      /* пробуем следующий алфавит */
    }
  }

  return null
}

export const PORTFOLIO_LINK_LIMIT = MAX_TOKEN_LENGTH
