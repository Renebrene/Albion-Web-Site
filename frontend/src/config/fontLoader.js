/*
 * Ленивая загрузка веб-шрифтов с Google Fonts.
 *
 * Мотивация: сам Roboto больше НЕ входит в бандл (убран из `extras`
 * в quasar.config.js — это убрало ~160 КБ файлов шрифта). При этом
 * возможность выбрать шрифт в настройках сохраняется: если в /api/settings
 * выбран не системный шрифт (Inter / Roboto / PT Sans / Montserrat /
 * Manrope), сюда приходит имя семейства и мы подключаем нужный
 * stylesheet Google Fonts.
 *
 * По умолчанию шрифт = 'system' → не запрашивается ни один байт.
 *
 * Стиль намеренно повторяет src/map/yandexLoader.js: один общий промис
 * на семейство, защита от повторной вставки, аккуратная деградация
 * при любой ошибке (шрифт просто не применится — сработает фолбэк из
 * css/ app.scss: 'Font', Inter, sans-serif).
 */

const LINK_ATTR = 'data-albion-font'
const GOOGLE_FONTS_BASE = 'https://fonts.googleapis.com/css2?family='

/* Уже запрошенные семейства: имя → промис загрузки <link>. */
const loaded = new Map()

/*
 * Допустимое имя семейства. Закрытый whitelist-паттерн защищает от
 * подстановки произвольных символов в href (значение приходит из
 * редактируемых настроек).
 */
const SAFE_FAMILY = /^[A-Za-z0-9][A-Za-z0-9 \-]*$/

/*
 * Явные веса для известных семейств: Google Fonts отвечает 400
 * Bad Request, если запросить неподдерживаемый вес (например, 800
 * у PT Sans). Для неизвестных имён — запрос без указания весов
 * (как выберет сам Google Fonts).
 */
const FONT_WEIGHTS = {
  Inter: '400;500;600;700;800',
  Roboto: '400;500;700;900',
  'PT Sans': '400;700',
  Montserrat: '400;500;600;700;800',
  Manrope: '400;500;600;700;800'
}

function normalize(value) {
  return String(value ?? '').trim()
}

/* Системный/пустой шрифт грузить не нужно — это шрифт по умолчанию. */
function needsFont(name) {
  return name !== '' && name !== 'system'
}

function buildHref(family) {
  const weights = FONT_WEIGHTS[family]

  /* Пробел в имени семейства кодируем как '+', как требует Google Fonts. */
  const encoded = family.replaceAll(' ', '+')

  const spec = weights ? `${encoded}:wght@${weights}` : encoded

  return `${GOOGLE_FONTS_BASE}${spec}&display=swap`
}

/**
 * Подключить одно семейство с Google Fonts.
 *
 * Возвращает промис, который резолвится с <link> при успехе и с null,
 * если шрифт не нужен / имя некорректно / загрузка не удалась.
 * Повторные вызовы для одного семейства переиспользуют промис.
 */
export function loadSiteFont(family) {
  if (typeof document === 'undefined') {
    return Promise.resolve(null)
  }

  const name = normalize(family)

  if (!needsFont(name)) {
    return Promise.resolve(null)
  }

  if (!SAFE_FAMILY.test(name)) {
    console.warn(
      'Albion fonts: некорректное имя шрифта, пропуск:',
      name
    )
    return Promise.resolve(null)
  }

  if (loaded.has(name)) {
    return loaded.get(name)
  }

  const promise = new Promise(resolve => {
    const link = document.createElement('link')

    link.setAttribute(LINK_ATTR, name)
    link.rel = 'stylesheet'
    link.href = buildHref(name)

    link.onload = () => resolve(link)

    link.onerror = () => {
      /* Снимаем кэш, чтобы следующая попытка могла повторить загрузку. */
      loaded.delete(name)
      console.warn('Albion fonts: не удалось загрузить шрифт', name)
      resolve(null)
    }

    document.head.appendChild(link)
  })

  loaded.set(name, promise)

  return promise
}

/**
 * Загрузить оба шрифта темы — основной и для заголовков.
 * Принимает объект настроек как есть (поля font_family / font_heading).
 */
export function applySiteFonts(settings) {
  if (!settings || typeof settings !== 'object') {
    return Promise.resolve([null, null])
  }

  return Promise.all([
    loadSiteFont(settings.font_family),
    loadSiteFont(settings.font_heading)
  ])
}
