/*
 * Значения полей с `clearable`.
 *
 * Quasar при очистке клавишей ✕ эмитит null
 * (quasar/src/composables/private.use-field/use-field.js, clearValue →
 * emit('update:modelValue', null)), причём и для строковых q-input,
 * и для q-select с `multiple` (там ожидается массив).
 * Обычные чтения — `.trim()`, `.length`, `.includes()` — на таком значении
 * падают. Перед чтением прогоняем значение через эти хелперы.
 */

/* Строка: null/undefined → '', число/иное → String(). */
export function asText(value) {
  if (typeof value === 'string') {
    return value
  }

  return value == null ? '' : String(value)
}

/* Список: null/undefined (очистка множественного выбора) → []. */
export function asList(value) {
  return Array.isArray(value) ? value : []
}
