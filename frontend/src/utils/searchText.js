import { transliterateVariants } from './transliterate'

/* Регистр, «ё», пунктуация и лишние пробелы. */
export function normalizeSearchText(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

/*
 * Группы токенов для запроса: исходный вариант и его кириллическая
 * транслитерация. Совпадения достаточно по любой группе.
 */
export function buildSearchTokenGroups(query) {
  const variants = [
    ...new Set(
      [query, ...transliterateVariants(query)]
        .map(normalizeSearchText)
        .filter(Boolean)
    )
  ]

  return variants
    .map(value => value.split(' ').filter(Boolean))
    .filter(tokens => tokens.length)
}

/*
 * Числовой токен («42») не должен находиться внутри более длинного числа
 * («142», «422347567563»). Поэтому для цифр требуем, чтобы перед и после
 * них не было других цифр. Буквенный суффикс дома «42А» при этом
 * по-прежнему находится, как и «42» целиком.
 */
const NUMERIC_TOKEN = /^\d+$/

function tokenMatches(haystack, token) {
  if (!NUMERIC_TOKEN.test(token)) {
    return haystack.includes(token)
  }

  const boundary = new RegExp(`(?<!\\d)${token}(?!\\d)`)

  return boundary.test(haystack)
}

export function matchesSearchGroups(haystack, groups) {
  return groups.some(tokens =>
    tokens.every(token => tokenMatches(haystack, token))
  )
}
