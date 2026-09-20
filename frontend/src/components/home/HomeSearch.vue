<template>
  <section class="search-section">
    <div class="search-shell">

      <div class="search-heading">
        <div class="eyebrow">
          {{ content.eyebrow }}
        </div>

        <h2>
          {{ content.title }}
        </h2>

        <p>
          {{ content.text }}
        </p>
      </div>

      <form class="search-box" @submit.prevent="openSearch">
        <div class="search-icon">⌕</div>

        <input
          v-model="searchQuery"
          type="search"
          :placeholder="content.placeholder"
          autocomplete="off"
        >

        <button
          type="submit"
          :disabled="!searchQuery.trim()"
        >
          {{ content.button.label }}
          <span>→</span>
        </button>
      </form>

      <div class="search-hint">
        <span>Например:</span>
        <button
          v-for="example in content.examples"
          :key="example"
          type="button"
          @click="searchExample(example)"
        >
          {{ example }}
        </button>
      </div>

    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getPage } from '@/services/api'

const router = useRouter()

const searchQuery = ref('')

const content = ref({
  eyebrow: 'ПОИСК ПО СЕТИ',
  title: 'Найдите рекламную конструкцию',
  text: 'Введите адрес, город или номер конструкции — система покажет доступные рекламные возможности.',
  placeholder: 'Адрес, город или номер конструкции',
  examples: [
    'Ростов-на-Дону',
    'Таганрог',
    '339 Стрелковой Дивизии'
  ],
  button: {
    label: 'Найти'
  }
})

onMounted(async () => {
  try {
    const page = await getPage('home')
    const block = page?.blocks?.find(item => item.key === 'search')
    const cms = block?.content

    if (cms && typeof cms === 'object') {
      content.value = {
        ...content.value,
        ...cms,
        button: {
          ...content.value.button,
          ...(cms.button || {})
        }
      }
    }
  } catch (error) {
    console.warn('Не удалось загрузить настройки поиска из CMS:', error)
  }
})

function openSearch() {
  const value = searchQuery.value.trim()

  if (!value) {
    router.push('/vozmozhnosti')
    return
  }

  router.push({
    path: '/vozmozhnosti',
    query: {
      address: value
    }
  })
}

function searchExample(example) {
  searchQuery.value = example
  openSearch()
}
</script>

<style scoped>
.search-section {
  padding: 110px 0;
  background: #f4f6f7;
}

.search-shell {
  width: min(1100px, 88%);
  margin: 0 auto;
}

.search-heading {
  max-width: 760px;
  margin-bottom: 42px;
}

.eyebrow {
  margin-bottom: 14px;
  color: #e12a1f;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.5px;
}

.search-heading h2 {
  margin: 0 0 18px;
  color: #17212b;
  font-size: clamp(40px, 5vw, 68px);
  line-height: .98;
  letter-spacing: -2.5px;
  font-weight: 900;
}

.search-heading p {
  max-width: 620px;
  margin: 0;
  color: #68757e;
  font-size: 15px;
  line-height: 1.65;
}

.search-box {
  display: flex;
  align-items: center;
  min-height: 76px;
  padding: 8px 8px 8px 24px;
  background: #fff;
  border: 1px solid #dfe4e7;
  border-radius: 16px;
  box-shadow: 0 15px 45px rgba(25, 35, 45, .08);
}

.search-icon {
  flex: 0 0 auto;
  margin-right: 16px;
  color: #9aa5ac;
  font-size: 30px;
  line-height: 1;
}

.search-box input {
  flex: 1 1 auto;
  min-width: 0;
  height: 58px;
  border: 0;
  outline: 0;
  background: transparent;
  color: #17212b;
  font: inherit;
  font-size: 16px;
}

.search-box input::placeholder {
  color: #9aa5ac;
}

.search-box button {
  flex: 0 0 auto;
  min-width: 130px;
  height: 58px;
  padding: 0 20px;
  border: 0;
  border-radius: 11px;
  background: #e12a1f;
  color: #fff;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: .08em;
  text-transform: uppercase;
  cursor: pointer;
  transition: opacity .18s ease, transform .18s ease;
}

.search-box button span {
  margin-left: 10px;
  font-size: 17px;
}

.search-box button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.search-box button:disabled {
  opacity: .45;
  cursor: default;
}

.search-hint {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 18px;
  color: #89949b;
  font-size: 11px;
}

.search-hint button {
  padding: 5px 10px;
  border: 1px solid #dfe4e7;
  border-radius: 6px;
  background: transparent;
  color: #53616a;
  font: inherit;
  cursor: pointer;
  transition: background .18s ease, border-color .18s ease;
}

.search-hint button:hover {
  background: #fff;
  border-color: #cbd3d8;
}

@media (max-width: 640px) {
  .search-section {
    padding: 80px 0;
  }

  .search-shell {
    width: 90%;
  }

  .search-heading h2 {
    font-size: 42px;
    letter-spacing: -1.5px;
  }

  .search-box {
    align-items: stretch;
    flex-direction: column;
    padding: 12px;
  }

  .search-icon {
    display: none;
  }

  .search-box input {
    width: 100%;
    height: 54px;
    padding: 0 12px;
  }

  .search-box button {
    width: 100%;
  }

  .search-hint {
    align-items: flex-start;
  }
}
</style>
