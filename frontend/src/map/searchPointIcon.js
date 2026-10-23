/*
 * Метка точки поиска — пин-домик.
 *
 * Пути общие для двух мест: перетаскиваемой метки `.point-map-crosshair`
 * в AdvertisingPage.vue и иконки зафиксированной точки, которую рисует
 * движок карты. Иначе после «Зафиксировать» домик подменялся дефолтным
 * пином Leaflet/Яндекса.
 *
 * Движки получают SVG как data-URI, а data-URI не читает CSS-переменные,
 * поэтому акцент снимаем с :root в момент создания иконки.
 */

export const SEARCH_POINT_ICON = {
  width: 42,
  height: 50,
  /* Капля: остриё снизу — это и есть точка. */
  body: 'M21 48C21 48 5 29.5 5 19A16 16 0 1 1 37 19C37 29.5 21 48 21 48Z',
  house: 'M21 9.5 11.5 17.5H14V27.5H28V17.5H30.5L21 9.5Z',
  door: 'M18.6 27.5V21.6H23.4V27.5'
}

const DEFAULT_ACCENT = '#e12a1f'

/* Акцент сайта из настроек — boot/settings.js пишет его в --albion-accent. */
function accentColor() {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return DEFAULT_ACCENT
  }

  const value = getComputedStyle(document.documentElement)
    .getPropertyValue('--albion-accent')
    .trim()

  return value || DEFAULT_ACCENT
}

export function searchPointIconHref(color = accentColor()) {
  const { width, height, body, house, door } = SEARCH_POINT_ICON

  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}">` +
    `<path d="${body}" fill="${color}" stroke="#ffffff" stroke-width="3"/>` +
    `<path d="${house}" fill="#ffffff"/>` +
    `<path d="${door}" fill="none" stroke="${color}" stroke-width="2.2" ` +
    'stroke-linejoin="round"/>' +
    '</svg>'

  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
}
