/*
 * Ленивые попапы карты (ключ `map_lazy_popups` в настройках сайта).
 *
 *   false — разметка попапа собирается заранее для всех меток (как было);
 *   true  — HTML собирается при открытии конкретного попапа.
 *
 * Переключается в админке: Настройки → Карта. Движки читают флаг при
 * перерисовке, поэтому смена настройки применяется после перезагрузки
 * страницы или ближайшего обновления данных карты.
 */
import { ref } from 'vue'

export const DEFAULT_LAZY_POPUPS = false

export const lazyPopups = ref(DEFAULT_LAZY_POPUPS)

export function setLazyPopups(value) {
  lazyPopups.value = value === true || value === 'true' || value === '1'
}
