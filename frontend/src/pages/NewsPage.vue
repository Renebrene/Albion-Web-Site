<template>
  <q-page class="news-page">
    <div class="news-container">
      <!-- Заголовок и фильтры зафиксированы, лента новостей
           прокручивается под ними. -->
      <div class="news-sticky">
        <header class="news-header">
          <div>
            <div class="news-kicker">ALBION</div>
            <h1>Новости</h1>
          </div>

          <p> События, проекты и новые возможности компании </p>
        </header>

        <nav class="news-categories">
          <button
            v-for="category in categories"
            :key="category"
            type="button"
            :class="{ active: selectedCategory === category }"
            @click="selectedCategory = category"
          >
            {{ category }}
          </button>
        </nav>
      </div>

      <div class="news-body">
        <div v-if="loading" class="news-loading">
          <q-spinner-dots size="42px" color="primary" />
        </div>

        <template v-else>
          <section ref="grid" class="news-grid">
            <NewsCard
              v-for="(item, index) in filteredNews"
              :key="item.id"
              :news="item"
              :size="cardSize(index)"
            />
          </section>

          <div v-if="!filteredNews.length" class="news-empty">
            <strong>Новостей пока нет</strong>
            <span>Попробуйте выбрать другую категорию.</span>
          </div>
        </template>
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import NewsCard from '../components/news/NewsCard.vue'
import NEWS from '../data/news'
import { getNews } from '@/services/api'
import { normalizeMedia } from '../components/news/NewsMediaCarousel.vue'

const selectedCategory = ref('Все')
const newsList = ref([])
const loading = ref(true)

/*
 * Приводим новость к единому виду: API отдаёт category-объект и
 * published_at, локальные данные — строку категории и поле date.
 */
function normalizeNews(item) {
  const category =
    item.category && typeof item.category === 'object'
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

function localNews() {
  return NEWS.filter(item => item.status === 'published').map(normalizeNews)
}

onMounted(async () => {
  try {
    const data = await getNews()
    const list = Array.isArray(data) ? data : data?.data || data?.items || []

    const published = list.filter(item => item.is_published !== false)

    newsList.value = published.length
      ? published.map(normalizeNews)
      : localNews()
  } catch (error) {
    // Если API недоступен — показываем локальные данные, как раньше.
    console.error('Не удалось загрузить новости:', error)
    newsList.value = localNews()
  } finally {
    loading.value = false
  }
})

const categories = computed(() => {
  const values = [
    ...new Set(newsList.value.map(item => item.category).filter(Boolean))
  ]

  return ['Все', ...values]
})

const filteredNews = computed(() => {
  return newsList.value
    .filter(item => {
      if (selectedCategory.value === 'Все') {
        return true
      }

      return item.category === selectedCategory.value
    })
    .sort((a, b) => {
      return new Date(b.date) - new Date(a.date)
    })
})

/*
 * Высота карточки. Ширина у всех одинаковая — одна колонка сетки, а
 * высоту задаёт пропорция медиа: «large» — высокие, «horizontal» —
 * приземистые, «normal» — средние. Ритм повторяется по массиву, чтобы
 * лента выглядела несимметричной, но не «рваной».
 */
const CARD_SIZE_PATTERN = [
  'large',
  'normal',
  'horizontal',
  'normal',
  'large',
  'horizontal',
  'normal'
]

function cardSize(index) {
  return CARD_SIZE_PATTERN[index % CARD_SIZE_PATTERN.length]
}

/*
 * Плиточная укладка.
 *
 * Карточки не выравниваются по рядам: сетка растёт строкой-единицей
 * (8 px), а каждой карточке считаем, сколько таких строк она занимает
 * по своей высоте. Тогда короткая карточка не оставляет под собой
 * пустоту до следующего ряда, а подтягивается к соседям сверху.
 *
 * Высоты карточек стабильны: область медиа задана через aspect-ratio,
 * поэтому подгрузка картинок раскладку не сдвигает.
 */
const grid = ref(null)

/* Шаг строки 1 px — остаток от округления почти незаметен. */
const MASONRY_ROW = 1
const MASONRY_GAP = 4

function layoutMasonry() {
  const el = grid.value

  if (!el) {
    return
  }

  const cards = [...el.children]

  /* Сначала измеряем без наших спанов, затем расставляем. */
  cards.forEach(card => {
    card.style.gridRowEnd = 'auto'
  })

  const unit = MASONRY_ROW + MASONRY_GAP
  const heights = cards.map(card => card.getBoundingClientRect().height)

  cards.forEach((card, index) => {
    const span = Math.max(1, Math.ceil((heights[index] + MASONRY_GAP) / unit))

    card.style.gridRowEnd = `span ${span}`
  })
}

let masonryTimer = null

/* Пересчёт откладываем: раскладка идёт после отрисовки и при ресайзе. */
function scheduleMasonry() {
  if (masonryTimer) {
    clearTimeout(masonryTimer)
  }

  masonryTimer = setTimeout(() => {
    masonryTimer = null
    layoutMasonry()
  }, 60)
}

onMounted(() => {
  window.addEventListener('resize', scheduleMasonry)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', scheduleMasonry)

  if (masonryTimer) {
    clearTimeout(masonryTimer)
  }
})

watch([filteredNews, loading], async () => {
  await nextTick()
  scheduleMasonry()
})
</script>

<style scoped>
.news-page {
  min-height: calc(100dvh - var(--albion-header-h, 78px));
  /* Фон заметно темнее светлых карточек — сетка читается как сетка */
  background: #d3dbe0;
}

.news-container {
  max-width: 1500px;
  margin: 0 auto;
  /* Боковые и нижний отступы плавно растут вместе с окном (clamp) — без
     резких скачков на границах брейкпоинтов. Верхний отступ переехал в
     .news-sticky, чтобы фон зафиксированного блока накрывал ленту. */
  padding: 0 clamp(15px, 2.8vw, 42px) clamp(45px, 5vw, 70px);
}

/*
 * Название и фильтры «прилипают» под шапкой сайта: лента новостей
 * прокручивается под ними. Непрозрачный фон обязателен — иначе карточки
 * будут видны сквозь зафиксированный блок.
 */
.news-sticky {
  position: sticky;
  top: var(--albion-header-h, 78px);
  z-index: 20;
  padding-top: clamp(25px, 2.8vw, 42px);
  background: #d3dbe0;
}

/* Отступ от фильтров до первой карточки. */
.news-body {
  padding-top: clamp(16px, 1.5vw, 22px);
}

.news-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 40px;
  margin-bottom: 25px;
}

.news-kicker {
  margin-bottom: 5px;
  color: var(--albion-accent);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.8px;
}

.news-header h1 {
  margin: 0;
  color: #17212b;
  font-size: clamp(30px, 3vw, 42px);
  line-height: 1;
  font-weight: 900;
  letter-spacing: -1.5px;
}

.news-header p {
  max-width: 300px;
  margin: 0;
  color: #78848b;
  font-size: clamp(11px, 0.8vw, 12px);
  line-height: 1.45;
  text-align: right;
}

.news-categories {
  display: flex;
  align-items: center;
  gap: 5px;
  /* Без нижнего отступа: граница фильтров — низ зафиксированного блока,
     под ним лента уходит при прокрутке. Отступ до карточек даёт
     .news-body. */
  padding-bottom: 13px;
  border-bottom: 1px solid #dfe4e7;
}

.news-categories button {
  height: 31px;
  padding: 0 14px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #5b6873;
  cursor: pointer;
  font-size: 10px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: 0.35px;
}

.news-categories button:hover {
  background: #e8ecee;
  color: #17212b;
}

.news-categories button.active {
  background: #17212b;
  color: #fff;
}

.news-grid {
  display: grid;
  /* Пять карточек в ряд на широких экранах; на меньших ширинах число
     колонок уменьшается (см. медиазапросы ниже). */
  grid-template-columns: repeat(5, minmax(0, 1fr));

  /*
   * Строка-единица для плиточной укладки. Значения должны совпадать
   * с MASONRY_ROW / MASONRY_GAP в скрипте (layoutMasonry).
   */
  grid-auto-rows: 1px;

  /* Плотная сетка: карточки почти вплотную, разделяет их фон */
  gap: 4px;

  align-items: start;
}

.news-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.news-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  color: #65727b;
}

.news-empty strong {
  color: #17212b;
  font-size: 20px;
}

.news-empty span {
  margin-top: 6px;
  font-size: 12px;
}

/*
 * Число карточек в ряду уменьшается вместе с окном, чтобы карточки не
 * становились слишком узкими. Размер самих карточек при этом не
 * масштабируется — меняется только количество колонок.
 */
@media (max-width: 1400px) {
  .news-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .news-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .news-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 650px) {
  .news-header {
    display: block;
  }

  .news-header p {
    margin-top: 10px;
    text-align: left;
  }

  .news-categories {
    overflow-x: auto;
  }

  .news-categories button {
    flex: 0 0 auto;
  }
}

@media (max-width: 540px) {
  .news-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
/*
 * Пока открыта страница новостей, системный скроллбар окна прячем: лента
 * прокручивается под зафиксированными заголовком и фильтрами, а «поле
 * прокрутки» остаётся невидимым. Правила глобальные (вне scoped), потому
 * что прокручивается сам документ, а не внутренний контейнер.
 */
html:has(.news-page),
body:has(.news-page) {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* старый Edge / IE */
}

html:has(.news-page)::-webkit-scrollbar,
body:has(.news-page)::-webkit-scrollbar {
  display: none; /* Chrome / Safari */
}
</style>
