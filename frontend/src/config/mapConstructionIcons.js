/*
 * SVG-значки конструкций на крупном масштабе карты
 * (ключ `map_construction_icons` в настройках сайта).
 *
 *   true  — на последних трёх уровнях увеличения вместо точек показываются
 *           модели конструкций;
 *   false — всегда точки (как было до появления значков).
 *
 * Переключается в админке: Настройки → Карта. Флаг читается при
 * создании/смене иконки, поэтому смена настройки применяется после
 * перезагрузки страницы.
 */
import { ref } from 'vue'

export const DEFAULT_CONSTRUCTION_ICONS = true

export const showConstructionIcons = ref(DEFAULT_CONSTRUCTION_ICONS)

export function setShowConstructionIcons(value) {
  showConstructionIcons.value =
    value === true || value === 'true' || value === '1'
}
