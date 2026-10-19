<template>
  <section class="inventory-section">
    <div class="inventory-shell">
      <div class="inventory-heading">
        <div>
          <div class="eyebrow">{{ content.eyebrow }}</div>
          <h2>{{ content.title }}</h2>
        </div>

        <p>{{ content.text }}</p>
      </div>

      <div class="inventory-content">
        <div class="inventory-intro">
          <div class="inventory-total">
            <strong>{{ constructions.length }}</strong>
            <span>конструкций<br />в каталоге</span>
          </div>

          <div class="inventory-types-title">
            {{ content.types_title }}
          </div>
        </div>

        <div class="inventory-types">
          <button
            v-for="item in typeList"
            :key="item.name"
            type="button"
            class="inventory-type"
            @click="openType(item.name)"
          >
            <span class="type-index">
              {{ String(item.index).padStart(2, '0') }}
            </span>

            <span class="type-name">{{ item.name }}</span>
            <span class="type-count">{{ item.count }}</span>
            <span class="type-arrow">→</span>
          </button>
        </div>
      </div>

      <div class="inventory-footer">
        <span>Реальные данные каталога ALBION</span>

        <q-btn
          unelevated
          :label="content.button.label"
          class="inventory-button"
          :to="content.button.to"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getConstructions, getPage } from '@/services/api'

const router = useRouter()
const constructions = ref([])

const content = ref({
  eyebrow: 'РЕКЛАМНЫЕ ВОЗМОЖНОСТИ',
  title: 'Выберите формат рекламы',
  text: 'Собственная сеть ALBION — рекламные конструкции в Ростове-на-Дону и городах Ростовской области.',
  types_title: 'Форматы рекламы',
  button: {
    label: 'Смотреть всю сеть',
    to: '/vozmozhnosti'
  }
})

onMounted(async () => {
  try {
    constructions.value = await getConstructions()
  } catch (error) {
    console.error('Не удалось загрузить каталог:', error)
  }

  try {
    const page = await getPage('home')
    const block = page?.blocks?.find(item => item.key === 'inventory')
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
    console.warn('Не удалось загрузить настройки каталога из CMS:', error)
  }
})

const typeList = computed(() => {
  const counts = new Map()

  constructions.value.forEach(item => {
    const type = String(item.type || '').trim()

    if (!type) return

    counts.set(type, (counts.get(type) || 0) + 1)
  })

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([name, count], index) => ({
      name,
      count,
      index: index + 1
    }))
})

function openType(type) {
  router.push({
    path: '/vozmozhnosti',
    query: { type }
  })
}
</script>

<style scoped>
.inventory-section {
  padding: 120px 0;
  background: #17212b;
  color: #fff;
}

.inventory-shell {
  width: min(1280px, 88%);
  margin: 0 auto;
}

.inventory-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 440px);
  gap: 80px;
  align-items: end;
  margin-bottom: 64px;
}

.eyebrow {
  margin-bottom: 14px;
  color: var(--albion-accent);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 1.5px;
}

.inventory-heading h2 {
  margin: 0;
  max-width: 760px;
  font-size: clamp(42px, 5vw, 72px);
  line-height: 0.95;
  letter-spacing: -2.5px;
  font-weight: 900;
}

.inventory-heading p {
  margin: 0;
  color: #aeb9c1;
  font-size: 15px;
  line-height: 1.65;
}

.inventory-content {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 70px;
  padding: 38px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
}

.inventory-intro {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.inventory-total {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.inventory-total strong {
  font-size: 64px;
  line-height: 0.9;
  font-weight: 900;
  letter-spacing: -3px;
}

.inventory-total span {
  padding-bottom: 4px;
  color: #8e9aa3;
  font-size: 10px;
  line-height: 1.3;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.inventory-types-title {
  color: #5b6873;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.2px;
  text-transform: uppercase;
}

.inventory-types {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.inventory-type {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto 28px;
  align-items: center;
  gap: 12px;
  min-height: 78px;
  padding: 0 12px;
  border: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  color: #fff;
  text-align: left;
  cursor: pointer;
  transition:
    background 0.18s ease,
    padding 0.18s ease;
}

.inventory-type:nth-child(-n + 2) {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.inventory-type:hover {
  padding-left: 18px;
  background: rgba(255, 255, 255, 0.055);
}

.type-index {
  color: #66747e;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.type-name {
  min-width: 0;
  overflow: hidden;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-count {
  color: #aeb9c1;
  font-size: 13px;
  font-weight: 800;
}

.type-arrow {
  color: var(--albion-accent);
  font-size: 18px;
  font-weight: 700;
  transition: transform 0.18s ease;
}

.inventory-type:hover .type-arrow {
  transform: translateX(4px);
}

.inventory-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 30px;
  padding-top: 28px;
}

.inventory-footer > span {
  color: #5b6873;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.inventory-button {
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
  .inventory-heading {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .inventory-content {
    grid-template-columns: 1fr;
    gap: 36px;
  }

  .inventory-intro {
    gap: 24px;
  }
}

@media (max-width: 640px) {
  .inventory-section {
    padding: 80px 0;
  }

  .inventory-shell {
    width: min(1280px, 90%);
  }

  .inventory-heading h2 {
    font-size: 42px;
    letter-spacing: -1.5px;
  }

  .inventory-types {
    grid-template-columns: 1fr;
  }

  .inventory-type:nth-child(2) {
    border-top: 0;
  }

  .inventory-total strong {
    font-size: 52px;
  }

  .inventory-footer {
    align-items: flex-start;
    flex-direction: column;
  }

  .inventory-button {
    width: 100%;
  }
}
</style>
