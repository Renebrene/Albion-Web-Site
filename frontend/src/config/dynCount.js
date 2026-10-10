/*
 * Показ количества поверхностей у динамической стороны — «динамика (5)».
 *
 * Значение приходит из админ-настроек (ключ `show_dyn_count` в /api/settings,
 * группа «Отображение сторон»). По умолчанию — показываем (как было).
 * Гасит подпись и в списке «Возможности», и в попапах карты.
 */
import { ref } from 'vue'

export const DEFAULT_SHOW_DYN_COUNT = true

export const showDynCount = ref(DEFAULT_SHOW_DYN_COUNT)

/* Принимает 'true' | 'false' (строки из настроек) либо boolean.
   Выключено только при явном false; всё прочее (в т.ч. отсутствие
   значения) — «показывать». */
export function setShowDynCount(value) {
  showDynCount.value = !(value === false || value === 'false')
}
