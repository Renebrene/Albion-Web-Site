/*
 * Оператор карты.
 *
 * Значение приходит из админ-настроек (ключ `map_engine` в /api/settings):
 *   'osm'    — Leaflet + OpenStreetMap;
 *   'yandex' — Yandex Maps JS API 2.1.
 *
 * Архитектура сохранена: оба движка на месте, выбор — по этому флагу,
 * при недоступности Яндекс-API карта молча откатывается на Leaflet
 * (см. src/map/MapView.vue).
 */
import { ref } from 'vue'

/* Значение по умолчанию, пока настройки не загрузились / недоступны. */
export const DEFAULT_MAP_ENGINE = 'osm'

/*
 * Ключ Yandex Maps JS API 2.1.
 *
 * Только из окружения: VITE_YANDEX_MAPS_KEY (см. frontend/.env.example).
 * В исходниках ключ не хранится — так его можно ротировать и ограничить
 * по домену в кабинете разработчика Яндекс.Карт, не трогая код.
 *
 * Если ключ не задан, загрузчик API сразу откажется (см. yandexLoader.js),
 * и карта молча переключится на Leaflet/OSM — сайт продолжит работать.
 */
export const YANDEX_MAPS_KEY =
  (import.meta.env && import.meta.env.VITE_YANDEX_MAPS_KEY) || ''

/* Активный оператор карты (реактивно). */
export const mapEngine = ref(DEFAULT_MAP_ENGINE)

/* Допустимые значения — 'osm' | 'yandex'. */
export function setMapEngine(value) {
  mapEngine.value = value === 'yandex' ? 'yandex' : 'osm'
}
