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

export function matchesSearchGroups(haystack, groups) {
  return groups.some(tokens => tokens.every(token => haystack.includes(token)))
}
