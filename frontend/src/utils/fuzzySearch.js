import { normalizeSearchText } from './searchText'

/* Левенштейн с ранним выходом, если расстояние уже больше max. */
function levenshtein(a, b, max) {
  if (a === b) {
    return 0
  }

  if (Math.abs(a.length - b.length) > max) {
    return max + 1
  }

  let previous = Array.from({ length: b.length + 1 }, (_, i) => i)
  let current = Array.from({ length: b.length + 1 })

  for (let i = 1; i <= a.length; i += 1) {
    current[0] = i
    let rowMin = current[0]

    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1

      current[j] = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + cost
      )

      if (current[j] < rowMin) {
        rowMin = current[j]
      }
    }

    if (rowMin > max) {
      return max + 1
    }

    ;[previous, current] = [current, previous]
  }

  return previous[b.length]
}

/*
 * Словарь известных слов из базы: города, районы, адреса, названия,
 * форматы. Нужен, чтобы не «исправлять» запрос в случайное слово.
 */
export function buildVocabulary(items) {
  const counts = new Map()

  const add = value => {
    for (const token of normalizeSearchText(value).split(' ')) {
      if (!token || /^\d+$/.test(token)) {
        continue
      }

      counts.set(token, (counts.get(token) || 0) + 1)
    }
  }

  for (const item of items || []) {
    add(item?.city)
    add(item?.district)
    add(item?.address)
    add(item?.name)
    add(item?.type)
  }

  return counts
}

/* Ближайшее известное слово; короткие слова и числа не трогаем. */
export function correctToken(token, vocabulary) {
  if (
    !token ||
    token.length < 4 ||
    /^\d+$/.test(token) ||
    vocabulary.has(token)
  ) {
    return token
  }

  const maxDistance = token.length >= 7 ? 2 : 1
  let best = null
  let bestDistance = maxDistance + 1
  let bestCount = -1

  for (const [candidate, count] of vocabulary) {
    if (Math.abs(candidate.length - token.length) > maxDistance) {
      continue
    }

    const distance = levenshtein(token, candidate, maxDistance)

    if (
      distance < bestDistance ||
      (distance === bestDistance && count > bestCount)
    ) {
      best = candidate
      bestDistance = distance
      bestCount = count
    }
  }

  return best || token
}

export function correctTokenGroups(groups, vocabulary) {
  return groups.map(tokens =>
    tokens.map(token => correctToken(token, vocabulary))
  )
}

export function groupsChanged(original, corrected) {
  return corrected.some((tokens, index) =>
    tokens.some((token, tokenIndex) => token !== original[index]?.[tokenIndex])
  )
}
