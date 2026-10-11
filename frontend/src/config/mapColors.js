/*
 * Цвета точек на карте.
 *
 * Значения приходят из админ-настроек (ключи map_color_* в /api/settings,
 * группа «Карта»):
 *   free  — все выбранные месяцы свободны;
 *   busy  — все выбранные месяцы заняты;
 *   mixed — смесь состояний (часть свободна, часть занята/в резерве).
 *
 * Оба движка карты (Leaflet и Яндекс) и подписи статусов берут цвета
 * отсюда — один источник правды. Пока настройки не загрузились или
 * недоступны, используются значения по умолчанию.
 */
import { ref } from 'vue'

/* Значения по умолчанию (совпадают с дефолтами схемы настроек). */
export const DEFAULT_MAP_DOT_COLORS = Object.freeze({
  free: '#2ea66d',
  busy: '#e24b42',
  mixed: '#e6a51c'
})

/* Текущая палитра точек. */
export const mapDotColors = ref({ ...DEFAULT_MAP_DOT_COLORS })

/*
 * Логика цвета точки:
 *   'three' — три цвета (free/busy/mixed), как раньше;
 *   'two'   — два цвета: зелёный, если есть хоть одна свободная
 *             поверхность, иначе красный (занято/резерв/утверждение).
 */
export const DEFAULT_MAP_COLOR_MODE = 'three'

export const mapColorMode = ref(DEFAULT_MAP_COLOR_MODE)

/* Допустимые значения — 'three' | 'two'. */
export function setMapColorMode(value) {
  mapColorMode.value = value === 'two' ? 'two' : 'three'
}

/*
 * Цвет безопасен только если это hex (#RGB / #RRGGBB / #RRGGBBAA).
 * Значение приходит из настроек и попадает в SVG (fill) и CSS-переменные,
 * поэтому произвольную строку пропускать нельзя. Иначе — дефолт.
 */
const HEX_COLOR = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/

function safeColor(value, fallback) {
  const text = String(value ?? '').trim()

  return HEX_COLOR.test(text) ? text : fallback
}

/*
 * Применяет цвета из загруженных настроек.
 * Принимает весь объект /api/settings (или только нужные ключи).
 */
export function setMapDotColors(settings) {
  const source = settings || {}

  mapDotColors.value = {
    free: safeColor(source.map_color_free, DEFAULT_MAP_DOT_COLORS.free),
    busy: safeColor(source.map_color_busy, DEFAULT_MAP_DOT_COLORS.busy),
    mixed: safeColor(source.map_color_mixed, DEFAULT_MAP_DOT_COLORS.mixed)
  }
}
