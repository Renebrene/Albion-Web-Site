/*
 * Режим отображения доступности в списке «Возможности».
 *
 * Значение приходит из админ-настроек (ключ `available_mode` в /api/settings,
 * группа «Внешний вид»):
 *   'surfaces' — как сейчас: строка на каждую поверхность (A(1), A(2)…);
 *   'sides'    — свернуть поверхности A1…A5 в одну сторону A: месяц свободен,
 *                если свободна хоть одна поверхность, иначе — продано
 *                (резерв не показываем).
 *
 * Пока настройки не загрузились — используем значение по умолчанию.
 */
import { ref } from 'vue'

export const DEFAULT_AVAILABLE_MODE = 'surfaces'

export const availableMode = ref(DEFAULT_AVAILABLE_MODE)

/* Допустимые значения — 'surfaces' | 'sides'. */
export function setAvailableMode(value) {
  availableMode.value = value === 'sides' ? 'sides' : 'surfaces'
}
