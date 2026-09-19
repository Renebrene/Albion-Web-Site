<template>
  <article
    class="news-card"
    :class="[
      `news-card-${size}`,
      { 'has-slider': news.media?.length > 1 }
    ]"
    @click="openNews"
  >
    <div class="news-media">
      <template v-if="news.media?.length">
        <img
          :src="news.media[currentSlide]?.src"
          :alt="news.media[currentSlide]?.alt || news.title"
        >

        <div
          v-if="news.media.length > 1"
          class="news-slider"
          @click.stop
        >
          <button
            type="button"
            class="slider-arrow"
            @click="prevSlide"
          >
            ‹
          </button>

          <div class="slider-dots">
            <button
              v-for="(_, index) in news.media"
              :key="index"
              type="button"
              class="slider-dot"
              :class="{ active: index === currentSlide }"
              @click="currentSlide = index"
            />
          </div>

          <button
            type="button"
            class="slider-arrow"
            @click="nextSlide"
          >
            ›
          </button>
        </div>

        <div
          v-if="news.media.length > 1"
          class="photo-count"
        >
          {{ currentSlide + 1 }} / {{ news.media.length }}
        </div>
      </template>

      <div v-else class="news-no-photo">
        ALBION
      </div>
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
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

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
  const count = props.news.media?.length || 0
  if (!count) return

  currentSlide.value =
    (currentSlide.value + 1) % count
}

function prevSlide() {
  const count = props.news.media?.length || 0
  if (!count) return

  currentSlide.value =
    (currentSlide.value - 1 + count) % count
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
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  transition:
    transform .22s ease,
    box-shadow .22s ease;
}

.news-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(20, 30, 40, .10);
}

.news-card-large {
  grid-column: span 2;
  grid-row: span 2;
}

.news-card-horizontal {
  grid-column: span 2;
}

.news-media {
  position: relative;
  overflow: hidden;
  background: #e9edef;
}

.news-card-normal .news-media {
  aspect-ratio: 1.35;
}

.news-card-large .news-media {
  aspect-ratio: 1.55;
}

.news-card-horizontal .news-media {
  aspect-ratio: 2.1;
}

.news-media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform .4s ease;
}

.news-card:hover .news-media img {
  transform: scale(1.025);
}

.news-no-photo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 220px;
  color: #a1aaaf;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 4px;
}

.news-card-content {
  padding: 15px 17px 18px;
}

.news-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #89949b;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .35px;
}

.news-category {
  color: #e12a1f;
}

.news-card h2 {
  margin: 0;
  color: #17212b;
  font-size: 17px;
  line-height: 1.12;
  font-weight: 850;
}

.news-card-large h2 {
  font-size: 25px;
  line-height: 1.08;
}

.news-card-horizontal h2 {
  font-size: 21px;
}

.news-card p {
  margin: 9px 0 0;
  color: #65727b;
  font-size: 12px;
  line-height: 1.45;
}

.news-read {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 13px;
  color: #17212b;
  font-size: 10px;
  font-weight: 850;
  text-transform: uppercase;
  letter-spacing: .3px;
}

.news-read span {
  color: #e12a1f;
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
  background: rgba(255,255,255,.92);
  color: #17212b;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,.12);
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
  background: rgba(255,255,255,.65);
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
  background: rgba(20,30,40,.65);
  color: #fff;
  font-size: 8px;
  font-weight: 800;
}

@media (max-width: 800px) {
  .news-card-large,
  .news-card-horizontal {
    grid-column: span 1;
    grid-row: span 1;
  }

  .news-card-large .news-media,
  .news-card-horizontal .news-media {
    aspect-ratio: 1.35;
  }

  .news-card-large h2,
  .news-card-horizontal h2 {
    font-size: 19px;
  }
}
</style>
