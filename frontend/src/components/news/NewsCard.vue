<template>
  <article
    class="news-card"
    :class="[`news-card-${size}`, { 'has-slider': mediaItems.length > 1 }]"
    role="link"
    tabindex="0"
    :aria-label="`Читать: ${news.title}`"
    @click="openNews"
    @keydown.enter.prevent="openNews"
    @keydown.space.prevent="openNews"
  >
    <div
      class="news-media"
      :style="mediaAspect ? { aspectRatio: mediaAspect } : null"
    >
      <template v-if="mediaItems.length">
        <!-- Видео в карточке: без автозапуска, показываем постер/первый кадр -->
        <video
          v-if="activeMedia.kind === 'video'"
          class="media-thumb"
          :src="activeMedia.url"
          :poster="activeMedia.poster || undefined"
          muted
          preload="metadata"
          playsinline
        ></video>

        <!-- Фото и GIF (GIF остаётся обычным img — анимация проигрывается) -->
        <img
          v-else
          class="media-thumb"
          :src="activeMedia.url"
          :alt="activeMedia.alt || news.title"
          loading="lazy"
          decoding="async"
        />

        <div
          v-if="mediaItems.length > 1"
          class="news-slider"
          @click.stop
          @keydown.stop
        >
          <button
            type="button"
            class="slider-arrow"
            aria-label="Предыдущий слайд"
            @click="prevSlide"
          >
            ‹
          </button>

          <div class="slider-dots">
            <button
              v-for="(item, index) in mediaItems"
              :key="item.id"
              type="button"
              class="slider-dot"
              :class="{ active: index === currentSlide }"
              :aria-label="`Слайд ${index + 1}`"
              @click="currentSlide = index"
            />
          </div>

          <button
            type="button"
            class="slider-arrow"
            aria-label="Следующий слайд"
            @click="nextSlide"
          >
            ›
          </button>
        </div>

        <div v-if="mediaItems.length > 1" class="photo-count">
          {{ currentSlide + 1 }} / {{ mediaItems.length }}
        </div>
      </template>

      <div v-else class="news-no-photo"> ALBION </div>
    </div>

    <div class="news-card-content">
      <div class="news-meta">
        <span>{{ formattedDate }}</span>
        <span class="news-category">{{ news.category }}</span>
      </div>

      <h2>{{ news.title }}</h2>

      <p v-if="showExcerpt">
        {{ news.excerpt }}
      </p>

      <div class="news-read">
        Читать
        <span>→</span>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { normalizeMedia, coverIndex } from './NewsMediaCarousel.vue'

const props = defineProps({
  news: {
    type: Object,
    required: true
  },
  size: {
    type: String,
    default: 'normal'
  }
})

const router = useRouter()
const currentSlide = ref(0)

// Медиа приводим к единому виду и стартуем с обложки.
// Обложка карточки — вариант `card`, затем `thumb`, затем оригинал.
const mediaItems = computed(() =>
  normalizeMedia(props.news.media, ['card', 'thumb'])
)
const activeMedia = computed(() => mediaItems.value[currentSlide.value] || {})

/*
 * Пропорция кадра по обложке (реальные width/height из API). Задаём её
 * контейнеру медиа: тогда фото ложится по ширине карточки целиком, без
 * обрезки, а высота карточки остаётся стабильной до загрузки картинки.
 * Если размеров нет — работает запасная пропорция из CSS (.news-card-*).
 */
const coverMedia = computed(
  () => mediaItems.value[coverIndex(mediaItems.value)] || {}
)
const mediaAspect = computed(() => {
  const width = Number(coverMedia.value.width)
  const height = Number(coverMedia.value.height)

  return width > 0 && height > 0 ? `${width} / ${height}` : null
})

watch(
  mediaItems,
  list => {
    currentSlide.value = coverIndex(list)
  },
  { immediate: true }
)

const showExcerpt = computed(() => {
  return ['large', 'horizontal'].includes(props.size)
})

const formattedDate = computed(() => {
  if (!props.news.date) return ''

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric'
  }).format(new Date(`${props.news.date}T12:00:00`))
})

function nextSlide() {
  const count = mediaItems.value.length
  if (!count) return

  currentSlide.value = (currentSlide.value + 1) % count
}

function prevSlide() {
  const count = mediaItems.value.length
  if (!count) return

  currentSlide.value = (currentSlide.value - 1 + count) % count
}

function openNews() {
  router.push(`/novosti/${props.news.slug}`)
}
</script>

<style scoped>
.news-card {
  position: relative;
  min-width: 0;
  overflow: hidden;

  border: 1px solid #d9e1e6;
  border-radius: 12px;

  background: #fff;

  /* Лёгкая тень по умолчанию — карточка отделяется от фона */
  box-shadow: 0 1px 3px rgba(20, 30, 40, 0.06);

  cursor: pointer;
  transition:
    transform 0.22s ease,
    box-shadow 0.22s ease;
}

.news-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(20, 30, 40, 0.1);
}

/*
 * Ширину задаёт сетка (NewsPage) — все карточки одной ширины.
 * «large» / «horizontal» влияют только на высоту (пропорцию медиа) и
 * размер заголовка, но не на ширину.
 */

.news-media {
  position: relative;
  overflow: hidden;

  /*
   * Почти белый фон (а не серый, как страница): область без фото не
   * сливается с подложкой, карточка читается светлым блоком.
   */
  background: #f5f8fa;

  border-bottom: 1px solid #eef2f5;
}

.news-card-normal .news-media {
  aspect-ratio: 1.35;
}

/* Высокая карточка: медиа выше — карточка заметно длиннее соседей. */
.news-card-large .news-media {
  aspect-ratio: 1.05;
}

/* Приземистая карточка: широкое медиа — карточка короткая. */
.news-card-horizontal .news-media {
  aspect-ratio: 2;
}

.news-media img,
.news-media video {
  display: block;
  width: 100%;
  height: 100%;
  /* Вписываем кадр целиком: для обложки пропорция контейнера совпадает
     с пропорцией фото, поэтому оно занимает всю площадь без обрезки;
     прочие кадры карусели показываются полностью, без кропа. */
  object-fit: contain;
  transition: transform 0.4s ease;
}

.news-card:hover .news-media img,
.news-card:hover .news-media video {
  transform: scale(1.025);
}

.news-no-photo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 220px;
  color: #b9c5cc;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 4px;
}

.news-card-content {
  padding: clamp(12px, 1.15vw, 15px) clamp(13px, 1.3vw, 17px)
    clamp(14px, 1.5vw, 18px);
}

.news-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #89949b;
  font-size: clamp(8px, 0.62vw, 9px);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.35px;
}

.news-category {
  color: var(--albion-accent);
}

.news-card h2 {
  margin: 0;
  color: #17212b;
  font-size: clamp(15px, 1.15vw, 17px);
  line-height: 1.12;
  font-weight: 850;
}

.news-card-large h2 {
  font-size: clamp(19px, 1.7vw, 25px);
  line-height: 1.08;
}

.news-card-horizontal h2 {
  font-size: clamp(17px, 1.4vw, 21px);
}

.news-card p {
  margin: 9px 0 0;
  color: #65727b;
  font-size: clamp(11px, 0.85vw, 12px);
  line-height: 1.45;
}

.news-read {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 13px;
  color: #17212b;
  font-size: clamp(9px, 0.7vw, 10px);
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.news-read span {
  color: var(--albion-accent);
  font-size: 15px;
}

.news-slider {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.slider-arrow {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.92);
  color: #17212b;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.slider-dots {
  display: flex;
  align-items: center;
  gap: 5px;
}

.slider-dot {
  width: 6px;
  height: 6px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.65);
  cursor: pointer;
}

.slider-dot.active {
  background: #fff;
  transform: scale(1.35);
}

.photo-count {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 5px 8px;
  border-radius: 6px;
  background: rgba(20, 30, 40, 0.65);
  color: #fff;
  font-size: 8px;
  font-weight: 800;
}

@media (max-width: 800px) {
  /* На узких экранах выравниваем пропорции медиа, чтобы высокие
     карточки не растягивали плитку. Кегль заголовка уже упирается в
     нижнюю границу clamp и отдельной правки не требует. */
  .news-card-large .news-media,
  .news-card-horizontal .news-media {
    aspect-ratio: 1.35;
  }
}
</style>
