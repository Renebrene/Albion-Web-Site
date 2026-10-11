/* Validate links editable through CMS before placing them in href attributes. */
function hasControlOrBackslash(value) {
  return [...value].some(char => {
    const code = char.charCodeAt(0)
    return code <= 0x1f || code === 0x7f || char === '\\'
  })
}
const TEL_NUMBER = /^\+?[0-9(). -]{3,40}$/
const SCHEME_PREFIX = /^[a-z][a-z0-9+.-]*:/i

export function safeCmsUrl(value) {
  let url = String(value ?? '').trim()

  if (!url || hasControlOrBackslash(url)) return ''
  if (url.startsWith('#')) return url

  // Allow root-relative paths but reject protocol-relative URLs (//host).
  if (url.startsWith('/')) return url.startsWith('//') ? '' : url

  // Bare paths such as "novosti" are kept as local routes. Any explicit
  // scheme must match the small allowlist below.
  if (!SCHEME_PREFIX.test(url)) {
    return url.replaceAll(' ', '%20')
  }

  if (/^https?:/i.test(url) && !/^https?:\/\//i.test(url)) return ''

  url = url.replaceAll(' ', '%20')

  let parsed
  try {
    parsed = new URL(url)
  } catch {
    return ''
  }

  if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
    if (!parsed.hostname || parsed.username || parsed.password) return ''
    return url
  }

  if (parsed.protocol === 'mailto:') {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(parsed.pathname) ? url : ''
  }

  if (parsed.protocol === 'tel:') {
    let number
    try {
      number = decodeURIComponent(parsed.pathname)
    } catch {
      return ''
    }
    return TEL_NUMBER.test(number) ? url : ''
  }

  return ''
}
