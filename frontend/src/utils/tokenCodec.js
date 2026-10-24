/*
 * Кодирование байтов в текст для ссылок (?s=, ?pf=).
 *
 * Задача не «шифрование», а самодостаточная строка, которую браузер
 * разбирает без запросов к серверу. Base64Url компактнее, Base32 —
 * удобнее диктовать голосом (нет регистра и похожих символов).
 *
 * Здесь только чистые функции: их используют и состояние фильтров
 * (utils/urlState.js), и портфель (utils/portfolioLink.js).
 */

const BASE32_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'

export const FORMAT_BASE64URL = 'base64url'
export const FORMAT_BASE32 = 'base32'

/* Значение из настроек сайта: всё, кроме base32, считаем base64url. */
export function normalizeFormat(value) {
  return value === FORMAT_BASE32 ? FORMAT_BASE32 : FORMAT_BASE64URL
}

function bytesToBase64Url(bytes) {
  let binary = ''

  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }

  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function base64UrlToBytes(text) {
  const normalized = String(text).replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }

  return bytes
}

function bytesToBase32(bytes) {
  let value = 0
  let bits = 0
  let output = ''

  for (const byte of bytes) {
    value = (value << 8) | byte
    bits += 8

    while (bits >= 5) {
      bits -= 5
      output += BASE32_ALPHABET[(value >>> bits) & 31]
    }
  }

  if (bits > 0) {
    output += BASE32_ALPHABET[(value << (5 - bits)) & 31]
  }

  return output
}

function base32ToBytes(text) {
  const clean = String(text).toUpperCase().replace(/=+$/, '')
  let value = 0
  let bits = 0
  const bytes = []

  for (const char of clean) {
    const index = BASE32_ALPHABET.indexOf(char)

    if (index === -1) {
      throw new Error('Некорректный Base32')
    }

    value = (value << 5) | index
    bits += 5

    if (bits >= 8) {
      bits -= 8
      bytes.push((value >>> bits) & 255)
    }
  }

  return new Uint8Array(bytes)
}

export function encodeBytes(bytes, format) {
  return normalizeFormat(format) === FORMAT_BASE32
    ? bytesToBase32(bytes)
    : bytesToBase64Url(bytes)
}

export function decodeBytes(text, format) {
  return normalizeFormat(format) === FORMAT_BASE32
    ? base32ToBytes(text)
    : base64UrlToBytes(text)
}

/*
 * Определяем алфавит по самой строке: Base32 состоит только из A-Z2-7,
 * поэтому старые токены читаются независимо от текущей настройки.
 */
export function detectFormat(text) {
  return /^[A-Z2-7]+$/.test(text) ? FORMAT_BASE32 : FORMAT_BASE64URL
}
