<template>
  <q-page class="news-page">
    <div class="news-container">

      <header class="news-header">
        <div>
          <div class="news-kicker">ALBION</div>
          <h1>Новости</h1>
        </div>

        <p>
          События, проекты и новые возможности
          компании
        </p>
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

      <section class="news-grid">
        <NewsCard
          v-for="(item, index) in filteredNews"
          :key="item.id"
          :news="item"
          :size="cardSize(index)"
        />
      </section>

      <div
        v-if="!filteredNews.length"
        class="news-empty"
      >
        <strong>Новостей пока нет</strong>
        <span>Попробуйте выбрать другую категорию.</span>
      </div>

    </div>
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import NewsCard from '../components/news/NewsCard.vue'
import NEWS from '../data/news'

const selectedCategory = ref('Все')

const categories = computed(() => {
  const values = [
    ...new Set(
      NEWS
        .filter(item => item.status === 'published')
        .map(item => item.category)
        .filter(Boolean)
    )
  ]

  return ['Все', ...values]
})

const filteredNews = computed(() => {
  return NEWS
    .filter(item => item.status === 'published')
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

function cardSize(index) {
  if (index === 0) return 'large'
  if (index === 3) return 'horizontal'
  if (index === 6) return 'horizontal'

  return 'normal'
}
</script>

<style scoped>
.news-page {
  min-height: calc(100vh - 115px);
  background: #f3f5f6;
}

.news-container {
  max-width: 1500px;
  margin: 0 auto;
  padding: 42px 42px 70px;
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
  color: #e12a1f;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.8px;
}

.news-header h1 {
  margin: 0;
  color: #17212b;
  font-size: 42px;
  line-height: 1;
  font-weight: 900;
  letter-spacing: -1.5px;
}

.news-header p {
  max-width: 300px;
  margin: 0;
  color: #78848b;
  font-size: 12px;
  line-height: 1.45;
  text-align: right;
}

.news-categories {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 22px;
  padding-bottom: 13px;
  border-bottom: 1px solid #dfe4e7;
}

.news-categories button {
  height: 31px;
  padding: 0 14px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #71808c;
  cursor: pointer;
  font-size: 10px;
  font-weight: 750;
  text-transform: uppercase;
  letter-spacing: .35px;
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  grid-auto-rows: auto;
  gap: 14px;
  align-items: start;
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

@media (max-width: 1100px) {
  .news-container {
    padding: 32px 25px 55px;
  }

  .news-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 650px) {
  .news-container {
    padding: 25px 15px 45px;
  }

  .news-header {
    display: block;
  }

  .news-header h1 {
    font-size: 34px;
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

  .news-grid {
    grid-template-columns: 1fr;
  }
}
</style>
