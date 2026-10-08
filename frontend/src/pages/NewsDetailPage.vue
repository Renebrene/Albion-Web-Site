<template>
  <q-page class="news-detail-page">
    <div v-if="news" class="news-detail">

      <button
        type="button"
        class="back-button"
        @click="goBack"
      >
        <span>←</span>
        Все новости
      </button>

      <div class="news-detail-layout">

        <main class="news-main">

          <div class="news-top-meta">
            <span class="news-category">{{ news.category }}</span>
            <span>{{ formattedDate }}</span>
          </div>

          <h1>{{ news.title }}</h1>

          <p class="news-excerpt">
            {{ news.excerpt }}
          </p>

          <div class="news-gallery">
            <img
              :src="currentMedia.src"
              :alt="currentMedia.alt || news.title"
            >

            <template v-if="news.media.length > 1">
              <button
                type="button"
                class="gallery-arrow gallery-prev"
                @click="prevSlide"
              >
                ‹
              </button>

              <button
                type="button"
                class="gallery-arrow gallery-next"
                @click="nextSlide"
              >
                ›
              </button>

              <div class="gallery-counter">
                {{ currentSlide + 1 }} / {{ news.media.length }}
              </div>

              <div class="gallery-dots">
                <button
                  v-for="(_, index) in news.media"
                  :key="index"
                  type="button"
                  :class="{ active: index === currentSlide }"
                  @click="currentSlide = index"
                />
              </div>
            </template>
          </div>

          <div class="news-content">
            <p
              v-for="(paragraph, index) in paragraphs"
              :key="index"
            >
              {{ paragraph }}
            </p>
          </div>

        </main>

        <aside class="news-sidebar">

          <div class="sidebar-block">
            <div class="sidebar-label">ALBION</div>
            <div class="sidebar-title">
              Рекламные возможности
            </div>

            <p>
              Выберите подходящие рекламные конструкции,
              адреса и периоды размещения на интерактивной карте.
            </p>

            <button
              type="button"
              class="sidebar-button"
              @click="openAdvertising"
            >
              Смотреть конструкции
              <span>→</span>
            </button>
          </div>

          <div class="sidebar-block sidebar-related">
            <div class="sidebar-label">ЕЩЁ НОВОСТИ</div>

            <button
              v-for="item in relatedNews"
              :key="item.id"
              type="button"
              class="related-item"
              @click="openRelated(item.slug)"
            >
              <span class="related-date">
                {{ formatShortDate(item.date) }}
              </span>

              <strong>{{ item.title }}</strong>

              <span class="related-arrow">→</span>
            </button>
          </div>

        </aside>

      </div>
    </div>

    <div v-else class="news-not-found">
      <h1>Новость не найдена</h1>
      <button
        type="button"
        @click="goBack"
      >
        Вернуться к новостям
      </button>
    </div>
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NEWS from '../data/news'

const route = useRoute()
const router = useRouter()

const currentSlide = ref(0)

const news = computed(() => {
  return NEWS.find(
    item =>
      item.slug === route.params.slug &&
      item.status === 'published'
  )
})

const currentMedia = computed(() => {
  return news.value?.media?.[currentSlide.value] || {
    src: '',
    alt: ''
  }
})

const paragraphs = computed(() => {
  if (!news.value?.content) return []

  return news.value.content
    .split(/\n+/)
    .map(text => text.trim())
    .filter(Boolean)
})

const formattedDate = computed(() => {
  if (!news.value?.date) return ''

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric'
  }).format(
    new Date(`${news.value.date}T12:00:00`)
  )
})

const relatedNews = computed(() => {
  if (!news.value) return []

  return NEWS
    .filter(item =>
      item.status === 'published' &&
      item.id !== news.value.id
    )
    .sort((a, b) =>
      new Date(b.date) - new Date(a.date)
    )
    .slice(0, 4)
})

function nextSlide() {
  const count = news.value?.media?.length || 0
  if (!count) return

  currentSlide.value =
    (currentSlide.value + 1) % count
}

function prevSlide() {
  const count = news.value?.media?.length || 0
  if (!count) return

  currentSlide.value =
    (currentSlide.value - 1 + count) % count
}

function goBack() {
  router.push('/novosti')
}

function openRelated(slug) {
  currentSlide.value = 0
  router.push(`/novosti/${slug}`)
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

function openAdvertising() {
  router.push('/vozmozhnosti')
}

function formatShortDate(date) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short'
  })
    .format(new Date(`${date}T12:00:00`))
    .replace('.', '')
}
</script>

<style scoped>
.news-detail-page {
  min-height: calc(100vh - 115px);
  background: #f3f5f6;
}

.news-detail {
  max-width: 1450px;
  margin: 0 auto;
  padding: 34px 42px 80px;
}

.back-button {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 28px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #68757d;
  cursor: pointer;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .4px;
}

.back-button:hover {
  color: var(--albion-accent);
}

.back-button span {
  font-size: 18px;
  line-height: 1;
}

.news-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 42px;
  align-items: start;
}

.news-main {
  min-width: 0;
  max-width: 980px;
}

.news-top-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 13px;
  color: #89949b;
  font-size: 10px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: .45px;
}

.news-category {
  color: var(--albion-accent);
}

.news-main h1 {
  max-width: 900px;
  margin: 0;
  color: #17212b;
  font-size: clamp(34px, 4vw, 58px);
  line-height: .98;
  font-weight: 900;
  letter-spacing: -2px;
}

.news-excerpt {
  max-width: 820px;
  margin: 20px 0 28px;
  color: #65727b;
  font-size: 16px;
  line-height: 1.5;
}

.news-gallery {
  position: relative;
  overflow: hidden;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 18px;
  background: #e4e9eb;
}

.news-gallery img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.gallery-arrow {
  position: absolute;
  top: 50%;
  width: 42px;
  height: 42px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 50%;
  background: rgba(255,255,255,.92);
  color: #17212b;
  cursor: pointer;
  font-size: 32px;
  line-height: 1;
  box-shadow: 0 4px 15px rgba(0,0,0,.12);
}

.gallery-arrow:hover {
  background: #fff;
}

.gallery-prev {
  left: 18px;
}

.gallery-next {
  right: 18px;
}

.gallery-counter {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 7px 10px;
  border-radius: 7px;
  background: rgba(20,30,40,.68);
  color: #fff;
  font-size: 9px;
  font-weight: 800;
}

.gallery-dots {
  position: absolute;
  left: 50%;
  bottom: 17px;
  display: flex;
  gap: 7px;
  transform: translateX(-50%);
}

.gallery-dots button {
  width: 7px;
  height: 7px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255,255,255,.55);
  cursor: pointer;
}

.gallery-dots button.active {
  background: #fff;
  transform: scale(1.4);
}

.news-content {
  max-width: 780px;
  padding: 32px 0 10px;
}

.news-content p {
  margin: 0 0 20px;
  color: #34424b;
  font-size: 15px;
  line-height: 1.72;
}

.news-sidebar {
  position: sticky;
  top: 25px;
}

.sidebar-block {
  padding: 22px;
  border-radius: 14px;
  background: #fff;
}

.sidebar-block + .sidebar-block {
  margin-top: 14px;
}

.sidebar-label {
  margin-bottom: 8px;
  color: var(--albion-accent);
  font-size: 9px;
  font-weight: 850;
  letter-spacing: 1.5px;
}

.sidebar-title {
  color: #17212b;
  font-size: 19px;
  line-height: 1.1;
  font-weight: 900;
}

.sidebar-block p {
  margin: 11px 0 17px;
  color: #71808a;
  font-size: 11px;
  line-height: 1.5;
}

.sidebar-button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: 38px;
  padding: 0 12px;
  border: 0;
  border-radius: 7px;
  background: #17212b;
  color: #fff;
  cursor: pointer;
  font-size: 9px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .35px;
}

.sidebar-button:hover {
  background: var(--albion-accent);
}

.sidebar-button span {
  font-size: 15px;
}

.sidebar-related {
  padding: 19px 14px;
}

.sidebar-related .sidebar-label {
  padding: 0 8px 8px;
}

.related-item {
  position: relative;
  display: block;
  width: 100%;
  padding: 11px 25px 11px 8px;
  border: 0;
  border-top: 1px solid #edf0f2;
  background: transparent;
  color: #17212b;
  cursor: pointer;
  text-align: left;
}

.related-item:hover strong {
  color: var(--albion-accent);
}

.related-date {
  display: block;
  margin-bottom: 4px;
  color: #99a2a8;
  font-size: 8px;
  font-weight: 750;
  text-transform: uppercase;
}

.related-item strong {
  display: block;
  font-size: 11px;
  line-height: 1.25;
}

.related-arrow {
  position: absolute;
  top: 50%;
  right: 7px;
  color: var(--albion-accent);
  transform: translateY(-50%);
}

.news-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 500px;
}

.news-not-found h1 {
  color: #17212b;
}

.news-not-found button {
  padding: 11px 18px;
  border: 0;
  border-radius: 7px;
  background: #17212b;
  color: #fff;
  cursor: pointer;
}

@media (max-width: 900px) {
  .news-detail {
    padding: 28px 25px 60px;
  }

  .news-detail-layout {
    grid-template-columns: 1fr;
  }

  .news-sidebar {
    position: static;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }

  .sidebar-block + .sidebar-block {
    margin-top: 0;
  }
}

@media (max-width: 600px) {
  .news-detail {
    padding: 22px 15px 50px;
  }

  .news-main h1 {
    font-size: 34px;
    letter-spacing: -1px;
  }

  .news-excerpt {
    font-size: 14px;
  }

  .news-gallery {
    border-radius: 12px;
  }

  .gallery-arrow {
    width: 34px;
    height: 34px;
    font-size: 25px;
  }

  .gallery-prev {
    left: 10px;
  }

  .gallery-next {
    right: 10px;
  }

  .news-sidebar {
    grid-template-columns: 1fr;
  }
}
</style>
