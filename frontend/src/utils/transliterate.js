/*
 * Практическая транслитерация латиницы в кириллицу для поиска.
 *
 * Нужна, когда пользователь печатает «Kurchatova» или «Bolshaya
 * Sadovaya», а данные в каталоге — на русском. Точная обратная
 * транслитерация невозможна (y = и/й/ы), поэтому для поиска
 * возвращаем несколько вариантов.
 */

const DIGRAPHS = [
  ['shch', 'щ'],
  ['sch', 'щ'],
  ['zh', 'ж'],
  ['kh', 'х'],
  ['ch', 'ч'],
  ['sh', 'ш'],
  ['ts', 'ц'],
  ['ya', 'я'],
  ['yu', 'ю'],
  ['yo', 'ё'],
  ['ye', 'е'],
  ['ay', 'ай'],
  ['oy', 'ой'],
  ['ey', 'ей'],
  ['uy', 'уй'],
  ['iy', 'ий'],
  ['yy', 'ый']
]

const LETTERS = {
  a: 'а',
  b: 'б',
  v: 'в',
  g: 'г',
  d: 'д',
  e: 'е',
  z: 'з',
  i: 'и',
  y: 'ы',
  k: 'к',
  l: 'л',
  m: 'м',
  n: 'н',
  o: 'о',
  p: 'п',
  r: 'р',
  s: 'с',
  t: 'т',
  u: 'у',
  f: 'ф',
  h: 'х',
  c: 'ц',
  j: 'й',
  x: 'кс',
  w: 'в',
  q: 'к',
  "'": '',
  '’': ''
}

export function transliterateToCyrillic(value) {
  const text = String(value ?? '').toLowerCase()
  let out = ''
  let index = 0

  while (index < text.length) {
    const rest = text.slice(index)
    const digraph = DIGRAPHS.find(([latin]) => rest.startsWith(latin))

    if (digraph) {
      out += digraph[1]
      index += digraph[0].length
      continue
    }

    const char = text[index]
    out += LETTERS[char] ?? char
    index += 1
  }

  return out
}

/*
 * Варианты для поиска: базовый, а также окончания «-ский/-цкий» и
 * «-ый», которые одной таблицей не угадать.
 */
export function transliterateVariants(value) {
  const primary = transliterateToCyrillic(value)

  return [
    ...new Set([
      primary,
      primary.replace(/([бвгджзклмнпрстфхцчшщ])ы\b/g, '$1ий'),
      primary.replace(/([бвгджзклмнпрстфхцчшщ])ы\b/g, '$1ый')
    ])
  ].filter(Boolean)
}
