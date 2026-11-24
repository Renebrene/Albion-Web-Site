import { ref } from 'vue'
import { adminRequest } from '../services/adminApi'

/*
 * Режим баннера: 'default' — синхронизация с реальными данными,
 * 'custom' — ручные настройки и сценарии.
 * Значение хранится в блоке #banner-settings кода слайда.
 */
export const roadrunnerMode = ref('default')

export function modeFromCode(code) {
  const match = String(code || '').match(
    /<script type="application\/json" id="banner-settings">([\s\S]*?)<\/script>/i
  )

  if (!match) return 'default'

  try {
    const parsed = JSON.parse(match[1])
    return parsed.mode?.value === 'custom' ? 'custom' : 'default'
  } catch {
    return 'default'
  }
}

export async function loadRoadrunnerMode() {
  try {
    const data = await adminRequest('/api/admin/home/slides')
    const slide = (data.slides || []).find(s => s.kind === 'road-banner')
    roadrunnerMode.value = modeFromCode(slide?.code || '')
  } catch {
    /* оставляем 'default', если код прочитать не удалось */
  }

  return roadrunnerMode.value
}
