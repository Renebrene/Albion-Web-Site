<template>
  <q-dialog
    v-model="isOpen"
    maximized
    transition-show="fade"
    transition-hide="fade"
  >
    <div class="photo-viewer">
      <!-- Заголовок: название фото (адрес + сторона) -->
      <div class="photo-viewer__head">
        <div class="photo-viewer__title">
          {{ title || 'Фото конструкции' }}
        </div>

        <button
          type="button"
          class="photo-viewer__close"
          title="Закрыть"
          aria-label="Закрыть"
          @click="closePhoto"
        >
          ✕
        </button>
      </div>

      <!-- Крупное изображение, вписанное в экран -->
      <div class="photo-viewer__body">
        <img
          v-if="url"
          :key="url"
          :src="url"
          :alt="title || 'Фото конструкции'"
          class="photo-viewer__image"
        />

        <!-- Переключатель: стрелки и точки — как в карусели новостей -->
        <template v-if="images.length > 1">
          <button
            type="button"
            class="photo-viewer__arrow photo-viewer__arrow--prev"
            aria-label="Предыдущее изображение"
            @click="prevImage"
          >
            ‹
          </button>

          <button
            type="button"
            class="photo-viewer__arrow photo-viewer__arrow--next"
            aria-label="Следующее изображение"
            @click="nextImage"
          >
            ›
          </button>

          <div class="photo-viewer__counter">
            {{ current + 1 }} / {{ images.length }}
          </div>

          <div class="photo-viewer__dots">
            <button
              v-for="(image, index) in images"
              :key="index"
              type="button"
              class="photo-viewer__dot"
              :class="{ active: index === current }"
              :aria-label="image.label || `Изображение ${index + 1}`"
              @click="setCurrent(index)"
            />
          </div>
        </template>
      </div>

      <!-- Действия -->
      <div class="photo-viewer__actions">
        <button
          type="button"
          class="photo-viewer__btn photo-viewer__btn--accent"
          :disabled="downloading"
          @click="handleDownload"
        >
          {{ downloading ? 'Скачиваем…' : 'Скачать' }}
        </button>

        <button type="button" class="photo-viewer__btn" @click="closePhoto">
          Закрыть
        </button>
      </div>
    </div>
  </q-dialog>
</template>

<script setup>
import { ref } from 'vue'

import {
  sanitizeFileName,
  usePhotoViewer
} from '../../composables/usePhotoViewer'

/*
 * Общее окно просмотра фото. Монтируется один раз в MainLayout,
 * состояние берёт из singleton-композабла usePhotoViewer.
 */
const {
  isOpen,
  images,
  current,
  currentImage,
  url,
  title,
  filename,
  closePhoto,
  nextImage,
  prevImage,
  setCurrent
} = usePhotoViewer()

const downloading = ref(false)

/* Временная ссылка -> клик -> освобождение blob-URL. */
function triggerDownload(href, name) {
  const link = document.createElement('a')

  link.href = href
  link.download = name
  link.rel = 'noopener'

  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/*
 * Скачивание: fetch -> blob -> object URL. Если fetch не удался
 * (например CORS), откатываемся на прямую ссылку <a download>.
 * Ошибки не должны ронять интерфейс.
 */
async function handleDownload() {
  if (!url.value) {
    return
  }

  // Базовое имя: filename активного изображения (у карты — «… · карта»),
  // иначе явное filename окна, иначе название (адрес + сторона).
  const active = currentImage.value || {}
  const base =
    active.filename || filename.value || active.label || title.value || 'photo'
  const name = sanitizeFileName(base, url.value)

  downloading.value = true

  try {
    const response = await fetch(url.value, { credentials: 'same-origin' })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)

    triggerDownload(objectUrl, name)
    URL.revokeObjectURL(objectUrl)
  } catch (error) {
    console.warn(
      '[PhotoViewer] не удалось скачать через fetch, использую прямую ссылку:',
      error
    )

    try {
      triggerDownload(url.value, name)
    } catch (fallbackError) {
      console.error('[PhotoViewer] скачивание не удалось:', fallbackError)
    }
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped>
.photo-viewer {
  display: flex;
  flex-direction: column;
  align-items: stretch;

  width: 100%;
  height: 100%;

  padding: 16px 18px 18px;

  background: rgba(10, 14, 18, 0.94);
  color: #fff;
}

/* --------------------------------------------------------- Заголовок */

.photo-viewer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;

  gap: 12px;

  flex: 0 0 auto;

  padding-bottom: 12px;
}

.photo-viewer__title {
  font-size: 16px;
  font-weight: 900;
  line-height: 1.35;
}

.photo-viewer__close {
  flex: 0 0 auto;

  display: grid;
  place-items: center;

  width: 34px;
  height: 34px;

  padding: 0;

  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 50%;

  background: transparent;
  color: #fff;

  font-size: 15px;

  cursor: pointer;
}

.photo-viewer__close:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}

/* --------------------------------------------------------- Изображение */

.photo-viewer__body {
  position: relative;

  flex: 1 1 auto;

  display: grid;
  place-items: center;

  min-height: 0;

  overflow: hidden;
}

.photo-viewer__image {
  max-width: 100%;
  max-height: 90vh;

  object-fit: contain;

  border-radius: 8px;
}

/* --------------------------------------------------------- Переключатель */

.photo-viewer__arrow {
  position: absolute;
  top: 50%;
  z-index: 2;

  display: grid;
  place-items: center;

  width: 44px;
  height: 44px;

  padding: 0;

  transform: translateY(-50%);

  border: 0;
  border-radius: 50%;

  background: rgba(255, 255, 255, 0.92);
  color: #17212b;

  font-size: 32px;
  line-height: 1;

  cursor: pointer;

  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.28);
}

.photo-viewer__arrow:hover {
  background: #fff;
}

.photo-viewer__arrow--prev {
  left: 18px;
}

.photo-viewer__arrow--next {
  right: 18px;
}

.photo-viewer__counter {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;

  padding: 6px 10px;

  border-radius: 7px;

  background: rgba(20, 30, 40, 0.68);
  color: #fff;

  font-size: 11px;
  font-weight: 800;
}

.photo-viewer__dots {
  position: absolute;
  left: 50%;
  bottom: 14px;
  z-index: 2;

  display: flex;

  gap: 7px;

  transform: translateX(-50%);
}

.photo-viewer__dot {
  width: 8px;
  height: 8px;

  padding: 0;

  border: 0;
  border-radius: 50%;

  background: rgba(255, 255, 255, 0.55);

  cursor: pointer;
}

.photo-viewer__dot.active {
  background: var(--albion-accent);

  transform: scale(1.4);
}

/* --------------------------------------------------------- Действия */

.photo-viewer__actions {
  flex: 0 0 auto;

  display: flex;
  flex-wrap: wrap;
  justify-content: center;

  gap: 10px;

  padding-top: 14px;
}

.photo-viewer__btn {
  min-width: 130px;

  padding: 9px 18px;

  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 9px;

  background: transparent;
  color: #fff;

  font-size: 13px;
  font-weight: 800;

  cursor: pointer;
}

.photo-viewer__btn:hover {
  border-color: var(--albion-accent);
}

.photo-viewer__btn--accent {
  border-color: var(--albion-accent);
  background: var(--albion-accent);
  color: #fff;
}

.photo-viewer__btn--accent:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>
