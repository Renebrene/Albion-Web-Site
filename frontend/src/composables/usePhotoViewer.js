import { ref } from 'vue'

/*
 * Общее окно просмотра фото конструкции (singleton).
 *
 * Состояние — модульные ref, поэтому одно и то же окно открывают
 * и карточки списка, и попапы карты, и панель портфеля.
 *
 * Почему делегирование кликов, а не Vue-обработчики:
 * разметку попапов карты строит popupContent.js статичной строкой,
 * реактивность Vue туда не достаёт. Поэтому один раз вешаем на
 * `document` делегированный обработчик: клик по `[data-photo]`
 * открывает окно с данными из data-атрибутов (data-photo-url /
 * data-photo-title / data-photo-filename).
 */

// ---------------------------------------------------------------- состояние

const isOpen = ref(false)
const url = ref('')
const title = ref('')
const filename = ref('')

// ---------------------------------------------------------------- утилиты

// Запрещённые в файловых системах символы и управляющие коды.
const INVALID_FS_CHARS = /[\\/:*?"<>|\u0000-\u001f]/g

/*
 * Расширение из URL картинки (без query/hash). По умолчанию — jpg.
 */
export function extensionFromUrl(photoUrl) {
  try {
    const path = String(photoUrl || '').split(/[?#]/)[0]
    const match = path.match(/\.([a-z0-9]{1,8})$/i)

    return match ? match[1].toLowerCase() : 'jpg'
  } catch {
    return 'jpg'
  }
}

/*
 * Собирает человекочитаемое название фото: «Город, адрес · Сторона A».
 * Пустые части аккуратно пропускаются.
 */
/*
 * Проверяет, входит ли название города в адрес как отдельное слово.
 * Нужно, чтобы не дублировать город: в базе адрес часто уже начинается
 * с него («г. Новошахтинск, …»). Проверка по границам слова не даёт
 * «Ростов» ложно совпасть с «Ростовская».
 */
function containsWord(text, word) {
  const haystack = text.toLowerCase()
  const needle = word.toLowerCase()

  let index = haystack.indexOf(needle)

  const isBoundary = char => char === '' || !/[а-яёa-z0-9]/i.test(char)

  while (index !== -1) {
    const before = index === 0 ? '' : haystack[index - 1]
    const after = haystack[index + needle.length] || ''

    if (isBoundary(before) && isBoundary(after)) {
      return true
    }

    index = haystack.indexOf(needle, index + 1)
  }

  return false
}

export function photoLabel({ city, address, side } = {}) {
  const parts = []

  const cityText = String(city ?? '').trim()
  const addressText = String(address ?? '').trim()

  /* Город добавляем, только если его ещё нет внутри адреса. */
  const place =
    cityText && addressText && containsWord(addressText, cityText)
      ? addressText
      : [cityText, addressText].filter(Boolean).join(', ')

  if (place) {
    parts.push(place)
  }

  const sideText = String(side ?? '').trim()

  if (sideText) {
    parts.push(`Сторона ${sideText}`)
  }

  return parts.join(' · ')
}

/*
 * Приводит имя файла к безопасному виду:
 *   - расширение берётся из имени, если оно уже есть, иначе — из URL;
 *   - запрещённые символы заменяются пробелом, пробелы схлопываются;
 *   - длина ограничивается ~120 символами, хвостовые точки убираются.
 */
export function sanitizeFileName(base, photoUrl, maxLength = 120) {
  const raw = String(base ?? '').trim()

  const existing = raw.match(/\.([a-z0-9]{1,8})$/i)
  const ext = existing ? existing[1].toLowerCase() : extensionFromUrl(photoUrl)

  let stem = existing ? raw.slice(0, -existing[0].length) : raw

  stem = stem
    .replace(INVALID_FS_CHARS, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  // Оставляем место под «.расширение».
  const maxStem = Math.max(1, maxLength - ext.length - 1)

  if (stem.length > maxStem) {
    stem = stem.slice(0, maxStem)
  }

  // Хвостовые точки и пробелы в имени файла недопустимы.
  stem = stem.replace(/[.\s]+$/, '')

  if (!stem) {
    stem = 'photo'
  }

  return `${stem}.${ext}`
}

// ---------------------------------------------------------------- управление

/* Открыть окно. Предыдущее содержимое заменяется. */
function openPhoto({ url: photoUrl, title: photoTitle, filename: photoFile } = {}) {
  const src = String(photoUrl || '').trim()

  if (!src) {
    return
  }

  if (isOpen.value) {
    closePhoto()
  }

  url.value = src
  title.value = String(photoTitle || '').trim()
  filename.value = String(photoFile || '').trim()
  isOpen.value = true
}

function closePhoto() {
  isOpen.value = false
}

/* Открыть окно по элементу с data-photo-* атрибутами. */
function openFromElement(element) {
  if (!element || typeof element.getAttribute !== 'function') {
    return
  }

  const photoUrl = element.getAttribute('data-photo-url')

  if (!photoUrl) {
    return
  }

  openPhoto({
    url: photoUrl,
    title: element.getAttribute('data-photo-title') || '',
    filename: element.getAttribute('data-photo-filename') || ''
  })
}

// ---------------------------------------------------------------- делегирование

let handlerAttached = false

function onDocumentClick(event) {
  const target = event.target

  if (!target || typeof target.closest !== 'function') {
    return
  }

  const el = target.closest('[data-photo]')

  if (!el || !el.getAttribute('data-photo-url')) {
    return
  }

  event.preventDefault()
  openFromElement(el)
}

/* Навешиваем обработчик один раз (лениво, на клиенте). */
function attachHandler() {
  if (handlerAttached || typeof document === 'undefined') {
    return
  }

  document.addEventListener('click', onDocumentClick)
  handlerAttached = true
}

// ---------------------------------------------------------------- публичный API

export function usePhotoViewer() {
  attachHandler()

  return {
    // состояние
    isOpen,
    url,
    title,
    filename,

    // управление
    openPhoto,
    closePhoto,
    openFromElement
  }
}
