/*
 * Кнопки слайдов главной.
 *
 * Разбор общий для всех типов слайдов: кнопки приходят из админки
 * (`slide.buttons`), у старых слайдов — legacy-поля `button_label` /
 * `button2_label`. Ссылки проверяет safeCmsUrl: небезопасные адреса
 * отбрасываются.
 *
 * Вынесено из HomeSlider, чтобы компоненты слайдов были самодостаточными:
 * новый тип слайда берёт кнопки отсюда и не требует правок в родителе.
 */

import { safeCmsUrl } from '../../../utils/safeCmsUrl'

/* Список кнопок с ключом для v-for; пустые подписи отбрасываем. */
export function withKeys(list) {
  return (Array.isArray(list) ? list : [])
    .filter(btn => btn && String(btn.label || '').trim())
    .map((btn, i) => {
      const rawUrl = String(btn.url || '').trim()

      return {
        key: btn.id !== null && btn.id !== undefined ? `b${btn.id}` : `k${i}`,
        label: String(btn.label).trim(),
        url: safeCmsUrl(rawUrl),
        invalidUrl: Boolean(rawUrl) && !safeCmsUrl(rawUrl),
        variant: btn.variant === 'ghost' ? 'ghost' : 'primary'
      }
    })
    .filter(btn => !btn.invalidUrl)
}

/* Кнопки слайда: свои из базы либо запасные (legacy/зашитые). */
export function slideButtons(slide, fallback = []) {
  const own = withKeys(slide && slide.buttons)

  return own.length ? own : withKeys(fallback)
}

/* Кнопки текстового слайда: свои либо legacy-кнопка слайда. */
export function textSlideButtons(slide) {
  const fallback =
    slide && slide.button_label
      ? [
          {
            label: slide.button_label,
            url: slide.button_url || '',
            variant: 'primary'
          }
        ]
      : []

  return slideButtons(slide, fallback)
}

/* Кнопки карточки hero: свои либо legacy button/button2. */
export function itemButtons(item) {
  const own = withKeys(item && item.buttons)

  if (own.length) {
    return own
  }

  const fallback = []

  if (item && item.button_label) {
    fallback.push({
      label: item.button_label,
      url: item.button_url || '',
      variant: 'primary'
    })
  }

  if (item && item.button2_label) {
    fallback.push({
      label: item.button2_label,
      url: item.button2_url || '#',
      variant: 'ghost'
    })
  }

  return withKeys(fallback)
}

/* Кнопка-действие (переход к форме): пустая ссылка или якорь (#form). */
export function isFormButton(btn) {
  const url = String((btn && btn.url) || '').trim()

  return !url || url.startsWith('#')
}
