/*
 * Выбор движка карты.
 *
 * 'yandex'  — Yandex Maps JS API 2.1 (основной вариант);
 * 'leaflet' — Leaflet + markercluster (фолбэк).
 *
 * Если загрузка Yandex API не удалась, MapView автоматически
 * откатывается на Leaflet (см. src/map/MapView.vue).
 */
export const MAP_ENGINE = 'yandex'

/*
 * Ключ Yandex Maps JS API 2.1.
 *
 * Берём из .env (VITE_YANDEX_MAPS_KEY), при отсутствии —
 * демонстрационный ключ по умолчанию.
 */
export const YANDEX_MAPS_KEY =
  (import.meta.env && import.meta.env.VITE_YANDEX_MAPS_KEY) ||
  '892d3b65-eb5c-4c57-92d8-666266f880fa'
