<template>
  <section class="directions-section">
    <div class="directions-shell">
      <div class="directions-heading">
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

      <div v-if="activities.length" class="directions-list">
        <button
          v-for="(item, index) in activities"
          :key="item"
          type="button"
          class="direction-item"
          @click="openDirections"
        >
          <span class="direction-number">
            {{ String(index + 1).padStart(2, '0') }}
          </span>

          <span class="direction-title">
            {{ item }}
          </span>

          <span class="direction-arrow"> → </span>
        </button>
      </div>

      <div class="directions-footer">
        <span> {{ activities.length }} направлений деятельности </span>

        <q-btn
          unelevated
          :label="content.button.label"
          class="directions-button"
          :to="content.button.to"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAbout, getPage } from '@/services/api'

const router = useRouter()

const activities = ref([])

const content = ref({
  eyebrow: 'НАПРАВЛЕНИЯ',
  title: 'Комплексная реклама',
  text: 'От размещения на собственной сети до производства, брендинга и специальных рекламных решений.',
  button: {
    label: 'Все направления',
    to: '/napravleniya'
  }
})

onMounted(async () => {
  try {
    const about = await getAbout()
    activities.value = Array.isArray(about?.activities?.items)
      ? about.activities.items
      : []
  } catch (error) {
    console.warn('Не удалось загрузить направления деятельности:', error)
  }

  try {
    const page = await getPage('home')

    const block = page?.blocks?.find(item => item.key === 'directions')
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
    console.warn('Не удалось загрузить настройки направлений из CMS:', error)
  }
})

function openDirections() {
  router.push('/napravleniya')
}
</script>

<style scoped>
.directions-section {
  padding: 120px 0;
  background: #fff;
  color: #17212b;
}

.directions-shell {
  width: min(1280px, 88%);
  margin: 0 auto;
}

.directions-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 440px);
  gap: 80px;
  align-items: end;
  margin-bottom: 58px;
}

.eyebrow {
  margin-bottom: 14px;
  color: var(--albion-accent);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.5px;
}

.directions-heading h2 {
  margin: 0;
  color: #17212b;
  font-size: clamp(42px, 5vw, 72px);
  line-height: 0.95;
  letter-spacing: -2.5px;
  font-weight: 900;
}

.directions-heading p {
  margin: 0;
  color: #68757e;
  font-size: 15px;
  line-height: 1.65;
}

.directions-list {
  border-top: 1px solid #dfe4e7;
}

.direction-item {
  display: grid;
  grid-template-columns: 70px minmax(0, 1fr) 40px;
  align-items: center;
  gap: 20px;
  width: 100%;
  min-height: 82px;
  padding: 0 18px;
  border: 0;
  border-bottom: 1px solid #dfe4e7;
  background: transparent;
  color: #17212b;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.18s ease,
    padding 0.18s ease;
}

.direction-item:hover {
  padding-left: 26px;
  background: #f4f6f7;
}

.direction-number {
  color: #a2adb4;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.direction-title {
  font-size: 16px;
  line-height: 1.35;
  font-weight: 750;
}

.direction-arrow {
  color: var(--albion-accent);
  font-size: 20px;
  text-align: right;
  transition: transform 0.18s ease;
}

.direction-item:hover .direction-arrow {
  transform: translateX(5px);
}

.directions-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  padding-top: 28px;
}

.directions-footer > span {
  color: #89949b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.directions-button {
  min-height: 44px;
  padding: 0 22px;
  border-radius: 10px;
  background: var(--albion-accent);
  color: #fff;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

@media (max-width: 900px) {
  .directions-heading {
    grid-template-columns: 1fr;
    gap: 24px;
  }
}

@media (max-width: 640px) {
  .directions-section {
    padding: 80px 0;
  }

  .directions-shell {
    width: 90%;
  }

  .directions-heading h2 {
    font-size: 42px;
    letter-spacing: -1.5px;
  }

  .direction-item {
    grid-template-columns: 42px minmax(0, 1fr) 24px;
    gap: 12px;
    min-height: 92px;
    padding: 0 8px;
  }

  .direction-title {
    font-size: 14px;
  }

  .directions-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .directions-button {
    width: 100%;
  }
}
</style>
