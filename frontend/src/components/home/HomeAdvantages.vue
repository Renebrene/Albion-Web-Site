<template>
  <section class="advantages-section">
    <div class="advantages-shell">
      <div class="advantages-heading">
        <div>
          <div class="eyebrow">
            {{ content.eyebrow }}
          </div>

          <h2>
            {{ content.title }}
          </h2>
        </div>

        <p>
          {{ content.text }}
        </p>
      </div>

      <div v-if="items.length" class="advantages-grid">
        <article
          v-for="(item, index) in items"
          :key="item.title || index"
          class="advantage-card"
        >
          <div class="advantage-number">
            {{ String(index + 1).padStart(2, '0') }}
          </div>

          <div class="advantage-content">
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </div>
        </article>
      </div>

      <div class="advantages-footer">
        <span>Производственные возможности ALBION</span>

        <q-btn
          unelevated
          :label="content.button.label"
          class="advantages-button"
          :to="content.button.to"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAbout, getPage } from '@/services/api'

const items = ref([])

const content = ref({
  eyebrow: 'ALBION · ВОЗМОЖНОСТИ',
  title: 'Всё необходимое для рекламной кампании',
  text: 'Производство, полиграфия и монтаж — ключевые возможности ALBION для реализации рекламных задач.',
  button: {
    label: 'О компании',
    to: '/o-kompanii'
  }
})

onMounted(async () => {
  try {
    const about = await getAbout()

    items.value = Array.isArray(about?.production?.items)
      ? about.production.items
      : []
  } catch (error) {
    console.warn('Не удалось загрузить производственные возможности:', error)
  }

  try {
    const page = await getPage('home')
    const block = page?.blocks?.find(item => item.key === 'advantages')
    const cms = block?.content

    if (cms && typeof cms === 'object') {
      content.value = {
        ...content.value,
        ...cms,
        button: {
          ...content.value.button,
          ...cms.button
        }
      }
    }
  } catch (error) {
    console.warn('Не удалось загрузить настройки преимуществ из CMS:', error)
  }
})
</script>

<style scoped>
.advantages-section {
  padding: 110px 0;
  background: #ffffff;
  color: #17212b;
}

.advantages-shell {
  width: min(1280px, 88%);
  margin: 0 auto;
}

.advantages-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.8fr);
  gap: 70px;
  align-items: end;
  margin-bottom: 54px;
}

.eyebrow {
  margin-bottom: 12px;
  color: var(--albion-accent);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.6px;
  text-transform: uppercase;
}

.advantages-heading h2 {
  max-width: 700px;
  margin: 0;
  font-size: clamp(34px, 4vw, 58px);
  line-height: 0.98;
  letter-spacing: -2px;
}

.advantages-heading > p {
  max-width: 500px;
  margin: 0;
  color: #69747c;
  font-size: 16px;
  line-height: 1.65;
}

.advantages-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid #dfe4e7;
  border-bottom: 1px solid #dfe4e7;
}

.advantage-card {
  min-width: 0;
  padding: 34px 30px 38px;
}

.advantage-card + .advantage-card {
  border-left: 1px solid #dfe4e7;
}

.advantage-number {
  margin-bottom: 54px;
  color: var(--albion-accent);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 1px;
}

.advantage-content h3 {
  margin: 0 0 14px;
  font-size: 24px;
  line-height: 1.1;
}

.advantage-content p {
  margin: 0;
  color: #69747c;
  font-size: 14px;
  line-height: 1.65;
}

.advantages-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding-top: 30px;
}

.advantages-footer > span {
  color: #89939a;
  font-size: 12px;
  letter-spacing: 0.8px;
  text-transform: uppercase;
}

.advantages-button {
  min-height: 46px;
  padding: 0 22px;
  border-radius: 0;
  background: #17212b;
  color: #ffffff;
  font-weight: 700;
}

@media (max-width: 800px) {
  .advantages-section {
    padding: 76px 0;
  }

  .advantages-heading {
    grid-template-columns: 1fr;
    gap: 24px;
    margin-bottom: 38px;
  }

  .advantages-heading h2 {
    letter-spacing: -1px;
  }

  .advantages-grid {
    grid-template-columns: 1fr;
  }

  .advantage-card + .advantage-card {
    border-top: 1px solid #dfe4e7;
    border-left: 0;
  }

  .advantage-number {
    margin-bottom: 28px;
  }

  .advantages-footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
