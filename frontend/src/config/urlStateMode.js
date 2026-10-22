/*
 * Формат ссылки на каталог (ключ `url_state_mode` в настройках сайта).
 *
 *   'readable' — ?mode=list&city=...&type=... (основной);
 *   'compact'  — ?s=v1-... (самодостаточный токен для QR/короткой ссылки).
 *
 * Разбор всегда принимает оба формата; режим влияет только на генерацию.
 */
import { ref } from 'vue'

export const DEFAULT_URL_STATE_MODE = 'readable'
export const DEFAULT_URL_STATE_FORMAT = 'base64url'

export const urlStateMode = ref(DEFAULT_URL_STATE_MODE)
export const urlStateTokenFormat = ref(DEFAULT_URL_STATE_FORMAT)

export function setUrlStateMode(value) {
  urlStateMode.value = value === 'compact' ? 'compact' : 'readable'
}

export function setUrlStateTokenFormat(value) {
  urlStateTokenFormat.value = value === 'base32' ? 'base32' : 'base64url'
}
