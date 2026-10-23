/*
 * Контакты в заявках: российский телефон и e-mail.
 *
 * Телефон принимаем в любом виде — «8 900 123-45-67»,
 * «+7 (900) 123 45 67», «9001234567». Возвращаем канонический
 * «+7 (900) 123-45-67» либо пустую строку, если номер не российский
 * или неполный.
 *
 * Та же нормализация продублирована на сервере
 * (backend/api/public_requests.py) — клиентская проверка только для UX.
 */

export function normalizeRuPhone(value) {
  const digits = String(value || '').replace(/\D/g, '')

  let normalized = digits

  if (
    normalized.length === 11 &&
    (normalized[0] === '7' || normalized[0] === '8')
  ) {
    normalized = '7' + normalized.slice(1)
  } else if (normalized.length === 10) {
    normalized = '7' + normalized
  }

  if (normalized.length !== 11 || normalized[0] !== '7') {
    return ''
  }

  return (
    `+7 (${normalized.slice(1, 4)}) ` +
    `${normalized.slice(4, 7)}-${normalized.slice(7, 9)}-${normalized.slice(9, 11)}`
  )
}

export function isValidEmail(value) {
  const email = String(value || '').trim()

  return email.length <= 254 && /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email)
}
