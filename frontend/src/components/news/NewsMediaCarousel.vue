<template>
  <div
    v-if="items.length"
    class="news-media-carousel"
    @touchstart.passive="onTouchStart"
    @touchend.passive="onTouchEnd"
  >
    <!-- Активный слайд: фото / анимированный GIF / видео -->
    <div class="media-stage">
      <Transition name="media-fade" mode="out-in">
        <!-- Видео: без автозапуска, постер если он есть -->
        <video
          v-if="active.kind === 'video'"
          :key="active.id"
          class="media-item"
          :src="active.url"
          :poster="active.poster || undefined"
          controls
          preload="metadata"
          playsinline
        ></video>

        <!-- Анимированный GIF: обычный img, чтобы анимация проигрывалась -->
        <img
          v-else-if="active.kind === 'gif'"
          :key="active.id"
          class="media-item"
          :src="active.url"
          :alt="active.alt || alt || 'Медиа новости'"
          decoding="async"
        >

        <!-- Фото: ленивая загрузка и сохранение пропорций -->
        <img
          v-else
          :key="active.id"
          class="media-item"
          :src="active.url"
          :alt="active.alt || alt || 'Медиа новости'"
          loading="lazy"
          decoding="async"
        >
      </Transition>
    </div>

    <!-- Навигация показываем только если слайдов больше одного -->
    <template v-if="items.length > 1">
      <button
        type="button"
        class="carousel-arrow carousel-prev"
        aria-label="Предыдущий слайд"
        @click="prev"
      >
        ‹
      </button>

      <button
        type="button"
        class="carousel-arrow carousel-next"
        aria-label="Следующий слайд"
        @click="next"
      >
        ›
      </button>

      <div class="carousel-counter">
        {{ current + 1 }} / {{ items.length }}
      </div>

      <div class="carousel-dots">
        <button
          v-for="(item, index) in items"
          :key="item.id"
          type="button"
          class="carousel-dot"
          :class="{ active: index === current }"
          :aria-label="`Слайд ${index + 1}`"
          @click="current = index"
        />
      </div>
    </template>
  </div>
</template>

<script>
/*
 * Хелперы для медиа новостей. Живут здесь, чтобы карусель, карточка
 * новости и страницы использовали одну и ту же логику.
 *
 * Поддерживаются два формата элемента:
 *  - новый (API): { storage_path, mime_type, is_cover, sort_order, alt, title }
 *  - старый (локальные данные): { type: 'image'|'video'|'gif', src, alt }
 */

// storage-путь нужного варианта (large/card/thumb) или '' если его нет.
// `variants` может отсутствовать (старые данные / ответ без него) — не падаем.
export function variantPath(item, variant) {
  const variants = Array.isArray(item?.variants) ? item.variants : []
  const found = variants.find((entry) => entry && entry.variant === variant)
  return found?.storage_path || ''
}

// URL файла для отображения. Второй аргумент — предпочитаемые варианты
// (строка или массив по приоритету). Если вариантов нет — молча
// падаем на оригинал `storage_path`, а для старых данных — на готовый src.
export function mediaUrl(item, preferred) {
  if (!item) return ''

  const order = Array.isArray(preferred) ? preferred : (preferred ? [preferred] : [])
  for (const variant of order) {
    const path = variantPath(item, variant)
    if (path) return `/storage/${path}`
  }

  if (item.storage_path) return `/storage/${item.storage_path}`
  return item.src || item.url || ''
}

// Тип медиа определяем по mime_type, иначе по старому полю type/расширению.
export function mediaKind(item) {
  if (!item) return 'image'

  const mime = String(item.mime_type || '').toLowerCase()
  if (mime.startsWith('video/')) return 'video'
  if (mime === 'image/gif') return 'gif'
  if (mime.startsWith('image/')) return 'image'

  const legacy = String(item.type || '').toLowerCase()
  if (legacy === 'video' || legacy === 'gif' || legacy === 'image') {
    return legacy
  }

  const url = mediaUrl(item).toLowerCase().split('?')[0]
  if (/\.(mp4|webm|mov|m4v|ogv|ogm)$/.test(url)) return 'video'
  if (/\.gif$/.test(url)) return 'gif'
  return 'image'
}

// Постер для видео: готовый URL, абсолютный путь или storage-путь.
// Для нового формата приоритет — `preview_path` (постер видео из БД).
function mediaPoster(item) {
  const poster = item?.poster || item?.preview_path || item?.poster_path
  if (!poster) return ''
  if (/^(https?:)?\/\//.test(poster) || poster.startsWith('/')) return poster
  return `/storage/${poster}`
}

// Приводим медиа к единому виду и сортируем по sort_order.
// `preferred` — вариант(ы) для выбора URL (см. mediaUrl).
// Функция идемпотентна: уже нормализованные элементы не меняются.
export function normalizeMedia(list, preferred) {
  if (!Array.isArray(list)) return []

  return list
    .filter(Boolean)
    .map((item, index) => {
      // Уже нормализованный элемент: не трогаем его без запроса варианта,
      // но при `preferred` пересчитываем URL из сохранённых сырых полей —
      // страницы (NewsPage/NewsDetailPage) нормализуют медиа без варианта,
      // а карточка/карусель донастраивают URL под свой размер.
      if (item.kind && item.url) {
        if (!preferred) return item
        return { ...item, url: mediaUrl(item, preferred) }
      }

      const rawCover = item.is_cover
      return {
        id: item.id ?? `media-${index}`,
        url: mediaUrl(item, preferred),
        kind: mediaKind(item),
        alt: item.alt || item.title || item.original_name || '',
        title: item.title || item.original_name || '',
        poster: mediaPoster(item),
        isCover: rawCover === true || rawCover === 1 || rawCover === '1',
        sortOrder:
          typeof item.sort_order === 'number' ? item.sort_order : index,
        // Сырые поля храним, чтобы повторная нормализация могла выбрать
        // другой вариант (card/thumb/large) и постер видео.
        storage_path: item.storage_path || '',
        variants: Array.isArray(item.variants) ? item.variants : [],
        preview_path: item.preview_path || null
      }
    })
    .filter(item => item.url)
    .sort((a, b) => a.sortOrder - b.sortOrder)
}

// Индекс обложки: элемент с is_cover, иначе первый.
export function coverIndex(items) {
  const index = items.findIndex(item => item.isCover)
  return index >= 0 ? index : 0
}
</script>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  // Массив медиа в любом из поддерживаемых форматов.
  media: {
    type: Array,
    default: () => []
  },
  // Запасной alt, если у файла не задан собственный.
  alt: {
    type: String,
    default: ''
  }
})

const current = ref(0)

// Слайд грузит вариант `large` (если есть), иначе оригинал `storage_path`.
const items = computed(() => normalizeMedia(props.media, 'large'))

const active = computed(() => items.value[current.value] || {})

// При смене набора медиа начинаем с обложки.
watch(items, list => {
  current.value = coverIndex(list)
}, { immediate: true })

function next() {
  const count = items.value.length
  if (!count) return
  current.value = (current.value + 1) % count
}

function prev() {
  const count = items.value.length
  if (!count) return
  current.value = (current.value - 1 + count) % count
}

/* Свайп на тач-устройствах: реагируем только на явное горизонтальное движение. */
let touchStartX = 0
let touchStartY = 0

function onTouchStart(event) {
  const touch = event.changedTouches[0]
  touchStartX = touch.clientX
  touchStartY = touch.clientY
}

function onTouchEnd(event) {
  const touch = event.changedTouches[0]
  const dx = touch.clientX - touchStartX
  const dy = touch.clientY - touchStartY

  if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) {
    if (dx < 0) next()
    else prev()
  }
}
</script>

<style scoped>
.news-media-carousel {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: 18px;
  background: #e4e9eb;
}

.media-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #dfe5e8;
}

/* object-fit: contain — пропорции не искажаются, кадр вписывается целиком */
.media-item {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

video.media-item {
  background: #0e141a;
}

/* Плавная смена слайда */
.media-fade-enter-active,
.media-fade-leave-active {
  transition: opacity .22s ease;
}

.media-fade-enter-from,
.media-fade-leave-to {
  opacity: 0;
}

.carousel-arrow {
  position: absolute;
  top: 50%;
  z-index: 2;
  width: 42px;
  height: 42px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .92);
  color: #17212b;
  cursor: pointer;
  font-size: 32px;
  line-height: 1;
  box-shadow: 0 4px 15px rgba(0, 0, 0, .12);
}

.carousel-arrow:hover {
  background: #fff;
}

.carousel-prev {
  left: 18px;
}

.carousel-next {
  right: 18px;
}

.carousel-counter {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 7px 10px;
  border-radius: 7px;
  background: rgba(20, 30, 40, .68);
  color: #fff;
  font-size: 9px;
  font-weight: 800;
}

.carousel-dots {
  position: absolute;
  left: 50%;
  bottom: 17px;
  display: flex;
  gap: 7px;
  transform: translateX(-50%);
}

.carousel-dot {
  width: 7px;
  height: 7px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .55);
  cursor: pointer;
}

.carousel-dot.active {
  background: var(--albion-accent);
  transform: scale(1.4);
}

@media (max-width: 600px) {
  .news-media-carousel {
    border-radius: 12px;
  }

  .carousel-arrow {
    width: 34px;
    height: 34px;
    font-size: 25px;
  }

  .carousel-prev {
    left: 10px;
  }

  .carousel-next {
    right: 10px;
  }
}
</style>
