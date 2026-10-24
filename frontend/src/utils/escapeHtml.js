/*
 * Экранирование текста для строк с разметкой (попапы карты, маркеры).
 *
 * Отдельный модуль без зависимостей: раньше функция жила в map/markerIcon.js,
 * а тот импортирует Leaflet, из-за чего popupContent.js тянул ядро карты в
 * чанк страницы каталога — даже когда карта собрана на Яндекс.Картах.
 */
export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}
