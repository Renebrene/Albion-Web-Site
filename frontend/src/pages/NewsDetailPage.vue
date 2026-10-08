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

          <!-- Медиа новости: фото, GIF и видео в карусели.
               Если медиа нет — блок не показываем. -->
          <NewsMediaCarousel
            v-if="media.length"
            class="news-media-block"
            :media="media"
            :alt="news.title"
          />

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

    <div v-else-if="loading" class="news-loading">
      <q-spinner-dots size="42px" color="primary" />
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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NEWS from '../data/news'
import { getNewsItem } from '@/services/api'
import NewsMediaCarousel, {
  normalizeMedia
} from '../components/news/NewsMediaCarousel.vue'

const route = useRoute()
const router = useRouter()

const apiNews = ref(null)
const loading = ref(true)

/*
 * Приводим новость к единому виду: API отдаёт category-объект и
 * published_at, локальные данные — строку категории и поле date.
 */
function normalizeNews(item) {
  if (!item) return null

  const category = item.category && typeof item.category === 'object'
    ? item.category.name
    : item.category

  const date = String(item.date || item.published_at || '').slice(0, 10)

  return {
    id: item.id ?? item.slug,
    slug: item.slug,
    title: item.title || '',
    excerpt: item.excerpt || '',
    content: item.content || '',
    category: category || '',
    date,
    media: normalizeMedia(item.media || [])
  }
}

async function loadNews(slug) {
  loading.value = true
  apiNews.value = null

  try {
    const data = await getNewsItem(slug)
    apiNews.value = normalizeNews(data)
  } catch (error) {
    // 404 — это нормальная ситуация «новость не найдена», в консоль не пишем.
    // Об остальных ошибках (например, API недоступен) сообщаем.
    if (!String(error).includes('404')) {
      console.error('Не удалось загрузить новость:', error)
    }
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.slug,
  slug => loadNews(slug),
  { immediate: true }
)

const news = computed(() => {
  if (apiNews.value) return apiNews.value

  // Пока идёт загрузка, локальные данные не подставляем — чтобы не мигало.
  if (loading.value) return null

  const local = NEWS.find(
    item =>
      item.slug === route.params.slug &&
      item.status === 'published'
  )

  return normalizeNews(local)
})

const media = computed(() => news.value?.media || [])

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

function goBack() {
  router.push('/novosti')
}

function openRelated(slug) {
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

.news-media-block {
  display: block;
  margin-bottom: 34px;
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

.news-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
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

  .news-sidebar {
    grid-template-columns: 1fr;
  }
}
</style>
