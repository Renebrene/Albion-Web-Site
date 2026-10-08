/*
 * Ленивая загрузка Yandex Maps JS API 2.1.
 *
 * Скрипт подключается один раз (синглтон-промис). Если загрузка
 * падает по сети или таймауту — промис отклоняется, чтобы MapView
 * мог откатиться на Leaflet.
 */

import { YANDEX_MAPS_KEY } from '../config/mapConfig'

const SCRIPT_ATTR = 'data-albion-yandex-maps'
const LOAD_TIMEOUT_MS = 15000

let loadingPromise = null

/* Ждём инициализацию API: ymaps.ready(...) */
function whenYmapsReady() {
  return new Promise((resolve, reject) => {
    if (
      typeof window === 'undefined' ||
      !window.ymaps ||
      typeof window.ymaps.ready !== 'function'
    ) {
      reject(new Error('Yandex Maps: объект ymaps недоступен'))
      return
    }

    window.ymaps.ready(() => resolve(window.ymaps))
  })
}

export function loadYandexMaps() {
  if (typeof window === 'undefined') {
    return Promise.reject(
      new Error('Yandex Maps: window недоступен')
    )
  }

  /* API уже подключён (например, был загружен ранее). */
  if (window.ymaps && typeof window.ymaps.ready === 'function') {
    return whenYmapsReady()
  }

  if (loadingPromise) {
    return loadingPromise
  }

  loadingPromise = new Promise((resolve, reject) => {
    let settled = false
    let timeoutId = null

    const finish = (settle, value) => {
      if (settled) {
        return
      }

      settled = true

      if (timeoutId) {
        clearTimeout(timeoutId)
        timeoutId = null
      }

      settle(value)
    }

    const fail = error => {
      loadingPromise = null

      finish(
        reject,
        error instanceof Error
          ? error
          : new Error(String(error))
      )
    }

    const succeed = () => {
      whenYmapsReady().then(
        api => finish(resolve, api),
        err => fail(err)
      )
    }

    timeoutId = setTimeout(
      () =>
        fail(
          new Error(
            'Yandex Maps: превышено время ожидания загрузки API'
          )
        ),
      LOAD_TIMEOUT_MS
    )

    /* Убираем возможный «зависший» скрипт прошлой попытки. */
    const stale = document.querySelector(
      `script[${SCRIPT_ATTR}]`
    )

    if (stale && stale.parentNode) {
      stale.parentNode.removeChild(stale)
    }

    const script = document.createElement('script')

    script.setAttribute(SCRIPT_ATTR, 'true')
    script.async = true

    script.src =
      'https://api-maps.yandex.ru/2.1/' +
      `?apikey=${encodeURIComponent(YANDEX_MAPS_KEY)}` +
      '&lang=ru_RU'

    script.onload = succeed

    script.onerror = () =>
      fail(
        new Error(
          'Yandex Maps: не удалось загрузить скрипт api-maps.yandex.ru'
        )
      )

    document.head.appendChild(script)
  })

  return loadingPromise
}
