/*
 * Конвертация раскладки клавиатуры: QWERTY → ЙЦУКЕН.
 *
 * Пользователь печатает «rjcvjyfdnjd», не заметив, что раскладка
 * английская; на русской раскладке эти же клавиши дают «космонавтов».
 * Это не транслитерация (та отвечает за «Kurchatova» → «Курчатова»,
 * см. transliterate.js), а перевод по позиции клавиш.
 *
 * Конвертируем, только если в строке есть латиница и нет кириллицы:
 * в смешанном наборе позиционный перевод ненадёжен.
 */

const QWERTY_TO_RUSSIAN = {
  q: 'й',
  w: 'ц',
  e: 'у',
  r: 'к',
  t: 'е',
  y: 'н',
  u: 'г',
  i: 'ш',
  o: 'щ',
  p: 'з',
  '[': 'х',
  ']': 'ъ',
  a: 'ф',
  s: 'ы',
  d: 'в',
  f: 'а',
  g: 'п',
  h: 'р',
  j: 'о',
  k: 'л',
  l: 'д',
  ';': 'ж',
  "'": 'э',
  z: 'я',
  x: 'ч',
  c: 'с',
  v: 'м',
  b: 'и',
  n: 'т',
  m: 'ь',
  ',': 'б',
  '.': 'ю',
  '/': '.'
}

const LATIN_LETTER = /[a-z]/i
const CYRILLIC_LETTER = /[а-яё]/i

/*
 * «rjcvjyfdnjd» → «космонавтов».
 *
 * Регистр сохраняем; неизвестные символы (цифры, пробелы, дефисы)
 * не трогаем.
 */
export function convertQwertyToRussian(value) {
  const text = String(value || '')

  if (!/[a-z]/i.test(text)) {
    return text
  }

  let result = ''

  for (const char of text) {
    const mapped = QWERTY_TO_RUSSIAN[char.toLowerCase()]

    if (mapped === undefined) {
      result += char
      continue
    }

    result += char === char.toLowerCase() ? mapped : mapped.toUpperCase()
  }

  return result
}

/*
 * Имеет смысл конвертировать только тогда, когда набрана латиница
 * (клавиша-позиция «русского» текста) и кириллицы в строке нет.
 */
export function isLatinLayoutText(value) {
  const text = String(value || '')

  return LATIN_LETTER.test(text) && !CYRILLIC_LETTER.test(text)
}

/*
 * Готовый запрос для поиска: латинскую раскладку переводим в русскую,
 * остальное возвращаем как есть.
 */
export function searchQueryForCatalog(value) {
  const text = String(value || '').trim()

  return isLatinLayoutText(text) ? convertQwertyToRussian(text) : text
}
