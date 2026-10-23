/*
 * Отладочные сообщения карты.
 *
 * Раньше движки писали в консоль на каждый рендер («597 physical
 * constructions / 597 markers») — при смене фильтров это засоряло консоль
 * пользователя. Теперь логи выключены по умолчанию и включаются флагом:
 *
 *   window.__ALBION_MAP_DEBUG__ = true
 */
export function mapDebug(...args) {
  if (typeof window !== 'undefined' && window.__ALBION_MAP_DEBUG__) {
    console.log(...args)
  }
}
