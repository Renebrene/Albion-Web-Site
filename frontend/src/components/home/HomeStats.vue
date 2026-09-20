<template>
  <section class="stats-section">
    <div class="stats-grid">
      <article
        v-for="stat in stats"
        :key="stat.label"
        class="stat"
      >
        <div class="stat-value">
          {{ stat.value }}
        </div>

        <div class="stat-label">
          {{ stat.label }}
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { getConstructions, getPage } from '@/services/api'

const constructions = ref([])

const cmsContent = ref({
  founding_year: '1995',
  labels: {
    constructions: 'рекламных конструкций',
    cities: 'городов и территорий',
    types: 'форматов рекламы'
  }
})

onMounted(async () => {
  try {
    constructions.value = await getConstructions()
  } catch (error) {
    console.error('Не удалось загрузить статистику:', error)
  }

  try {
    const page = await getPage('home')
    const block = page?.blocks?.find((item) => item.key === 'stats')
    const content = block?.content

    if (content && typeof content === 'object') {
      cmsContent.value = {
        ...cmsContent.value,
        ...content,
        labels: {
          ...cmsContent.value.labels,
          ...(content.labels || {})
        }
      }
    }
  } catch (error) {
    console.warn('Не удалось загрузить настройки статистики из CMS:', error)
  }
})

const cities = computed(() => {
  return new Set(
    constructions.value
      .map(item => item.city)
      .filter(Boolean)
  ).size
})

const types = computed(() => {
  return new Set(
    constructions.value
      .map(item => item.type)
      .filter(Boolean)
  ).size
})

const stats = computed(() => [
  {
    value: constructions.value.length || '—',
    label: cmsContent.value.labels.constructions
  },
  {
    value: cities.value || '—',
    label: cmsContent.value.labels.cities
  },
  {
    value: types.value || '—',
    label: cmsContent.value.labels.types
  },
  {
    value: cmsContent.value.founding_year || '—',
    label: 'год основания'
  }
])
</script>

<style scoped>
.stats-section {
  position: relative;
  z-index: 2;

  width: min(1280px, 88%);
  margin: -45px auto 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);

  overflow: hidden;

  border-radius: 16px;

  background: #fff;

  box-shadow: 0 20px 60px rgba(23, 33, 43, 0.12);
}

.stat {
  min-height: 130px;
  padding: 25px 28px;

  display: flex;
  flex-direction: column;
  justify-content: center;

  border-right: 1px solid #edf0f2;
}

.stat:last-child {
  border-right: 0;
}

.stat-value {
  color: #17212b;

  font-size: 36px;
  line-height: 1;
  font-weight: 900;
  letter-spacing: -1px;
}

.stat-label {
  margin-top: 10px;

  color: #78858e;

  font-size: 13px;
  line-height: 1.3;
}

@media (max-width: 800px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .stat:nth-child(2) {
    border-right: 0;
  }

  .stat:nth-child(-n + 2) {
    border-bottom: 1px solid #edf0f2;
  }
}

@media (max-width: 500px) {
  .stats-section {
    width: 90%;
    margin-top: -25px;
  }

  .stat {
    min-height: 105px;
    padding: 18px;
  }

  .stat-value {
    font-size: 28px;
  }
}
</style>
