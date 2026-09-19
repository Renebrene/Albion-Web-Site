<template>
  <q-page class="about-page">
    <div v-if="loading" class="about-state">
      <q-spinner-dots size="42px" />
    </div>

    <div v-else-if="error" class="about-state">
      <div class="about-error">
        Не удалось загрузить информацию о компании
      </div>
    </div>

    <template v-else>
      <!-- HERO -->
      <section class="about-hero">
        <div class="about-hero-copy">
          <div class="about-eyebrow">
            {{ about.eyebrow }}
          </div>

          <h1>{{ about.title }}</h1>

          <p class="about-intro">
            {{ about.intro }}
          </p>
        </div>

        <div class="about-hero-image">
          <div
            v-if="about.images?.hero"
            class="about-image"
            :style="{
              backgroundImage: `url(${about.images.hero})`
            }"
          ></div>

          <div v-else class="about-image about-image-placeholder">
            <span>ALBION</span>
            <small>РЕКЛАМНЫЕ РЕШЕНИЯ</small>
          </div>
        </div>
      </section>

      <!-- STATS -->
      <section class="about-stats">
        <div
          v-for="stat in about.stats"
          :key="stat.label"
          class="about-stat"
        >
          <strong>{{ stat.value }}</strong>
          <span>{{ stat.label }}</span>
        </div>
      </section>

      <!-- CONTENT -->
      <section class="about-grid">

        <!-- NETWORK -->
        <article class="about-card about-network">
          <div class="about-card-label">01 · СЕТЬ</div>

          <h2>{{ about.network?.title }}</h2>

          <div class="about-subtitle">Города присутствия</div>

          <div class="about-tags">
            <span
              v-for="city in about.network?.cities || []"
              :key="city"
            >
              {{ city }}
            </span>
          </div>

          <div class="about-subtitle about-subtitle-spaced">
            Трассы и территории
          </div>

          <ul class="about-list">
            <li
              v-for="highway in about.network?.highways || []"
              :key="highway"
            >
              {{ highway }}
            </li>
          </ul>
        </article>

        <!-- ACTIVITIES -->
        <article class="about-card about-activities">
          <div class="about-card-label">02 · НАПРАВЛЕНИЯ</div>

          <h2>{{ about.activities?.title }}</h2>

          <div class="activities-list">
            <div
              v-for="(item, index) in about.activities?.items || []"
              :key="item"
              class="activity-item"
            >
              <span>{{ String(index + 1).padStart(2, '0') }}</span>
              <strong>{{ item }}</strong>
            </div>
          </div>
        </article>

        <!-- PRODUCTION -->
        <article class="about-card about-production">
          <div class="about-card-label">03 · ПРОИЗВОДСТВО</div>

          <h2>{{ about.production?.title }}</h2>

          <div class="production-list">
            <div
              v-for="item in about.production?.items || []"
              :key="item.title"
              class="production-item"
            >
              <div class="production-title">
                {{ item.title }}
              </div>

              <div class="production-text">
                {{ item.text }}
              </div>
            </div>
          </div>
        </article>

      </section>
    </template>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getAbout } from '../services/api'

const loading = ref(true)
const error = ref(false)

const about = ref({
  eyebrow: '',
  title: '',
  intro: '',
  stats: [],
  network: {
    title: '',
    cities: [],
    highways: []
  },
  activities: {
    title: '',
    items: []
  },
  production: {
    title: '',
    items: []
  },
  images: {
    hero: '',
    network: '',
    production: ''
  }
})

async function loadAbout() {
  loading.value = true
  error.value = false

  try {
    about.value = await getAbout()
  } catch (err) {
    console.error('Albion about:', err)
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadAbout)
</script>

<style scoped>
.about-page {
  background: #f5f3ef;
  color: #171717;
  padding: 28px 32px 48px;
}

.about-state {
  min-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.about-error {
  color: #a33a32;
}

/* HERO */

.about-hero {
  max-width: 1440px;
  margin: 0 auto;
  min-height: 330px;

  display: grid;
  grid-template-columns: 1.08fr 0.82fr;
  gap: 24px;
}

.about-hero-copy {
  padding: 30px 20px 26px 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.about-eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8c5a3c;
  margin-bottom: 16px;
}

.about-hero h1 {
  margin: 0;
  max-width: 720px;
  font-size: clamp(34px, 4vw, 54px);
  line-height: 0.98;
  letter-spacing: -0.045em;
  font-weight: 800;
}

.about-intro {
  max-width: 640px;
  margin: 20px 0 0;
  font-size: 16px;
  line-height: 1.55;
  color: #57534e;
}

.about-hero-image {
  min-height: 330px;
}

.about-image {
  width: 100%;
  height: 100%;
  min-height: 330px;
  border-radius: 18px;
  background-size: cover;
  background-position: center;
}

.about-image-placeholder {
  background:
    linear-gradient(
      135deg,
      #242424 0%,
      #34312e 45%,
      #8c5a3c 100%
    );

  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding: 26px;
  color: white;
}

.about-image-placeholder span {
  font-size: 34px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.about-image-placeholder small {
  margin-top: 8px;
  font-size: 11px;
  letter-spacing: 0.18em;
  opacity: 0.7;
}

/* STATS */

.about-stats {
  max-width: 1440px;
  margin: 16px auto 26px;

  display: grid;
  grid-template-columns: repeat(4, 1fr);

  border-top: 1px solid #d8d3cc;
  border-bottom: 1px solid #d8d3cc;
}

.about-stat {
  min-height: 88px;
  padding: 16px 20px;

  display: flex;
  flex-direction: column;
  justify-content: center;

  border-right: 1px solid #d8d3cc;
}

.about-stat:last-child {
  border-right: 0;
}

.about-stat strong {
  font-size: 32px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.about-stat span {
  margin-top: 8px;
  color: #77716b;
  font-size: 13px;
}

/* GRID */

.about-grid {
  max-width: 1440px;
  margin: 0 auto;

  display: grid;
  grid-template-columns: 1fr 1.25fr 1fr;
  gap: 18px;
}

.about-card {
  background: white;
  border-radius: 18px;
  padding: 28px;
  min-height: 390px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.045);
}

.about-card-label {
  color: #8c5a3c;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.15em;
}

.about-card h2 {
  margin: 12px 0 25px;
  font-size: 25px;
  line-height: 1.1;
  letter-spacing: -0.025em;
}

.about-subtitle {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #858079;
  margin-bottom: 10px;
}

.about-subtitle-spaced {
  margin-top: 25px;
}

.about-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.about-tags span {
  border: 1px solid #ddd8d1;
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 12px;
}

.about-list {
  padding: 0;
  margin: 0;
  list-style: none;
}

.about-list li {
  position: relative;
  padding-left: 15px;
  margin-bottom: 9px;
  font-size: 13px;
  line-height: 1.35;
  color: #55514c;
}

.about-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #8c5a3c;
}

/* ACTIVITIES */

.activities-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.activity-item {
  min-height: 72px;
  padding: 13px;
  background: #f6f4f1;
  border-radius: 10px;

  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.activity-item span {
  font-size: 10px;
  color: #9a938b;
}

.activity-item strong {
  font-size: 12px;
  line-height: 1.3;
}

/* PRODUCTION */

.production-list {
  display: flex;
  flex-direction: column;
}

.production-item {
  padding: 17px 0;
  border-top: 1px solid #e5e1dc;
}

.production-item:first-child {
  border-top: 0;
  padding-top: 0;
}

.production-title {
  font-weight: 800;
  font-size: 14px;
  margin-bottom: 6px;
}

.production-text {
  color: #67615b;
  font-size: 13px;
  line-height: 1.45;
}

/* RESPONSIVE */

@media (max-width: 1100px) {
  .about-hero {
    grid-template-columns: 1fr;
  }

  .about-hero-image {
    min-height: 280px;
  }

  .about-image {
    min-height: 280px;
  }

  .about-grid {
    grid-template-columns: 1fr 1fr;
  }

  .about-production {
    grid-column: span 2;
  }
}

@media (max-width: 760px) {
  .about-page {
    padding: 18px 16px 32px;
  }

  .about-hero h1 {
    font-size: 42px;
  }

  .about-stats {
    grid-template-columns: 1fr 1fr;
  }

  .about-stat:nth-child(2) {
    border-right: 0;
  }

  .about-stat:nth-child(-n + 2) {
    border-bottom: 1px solid #d8d3cc;
  }

  .about-grid {
    grid-template-columns: 1fr;
  }

  .about-production {
    grid-column: auto;
  }

  .activities-list {
    grid-template-columns: 1fr;
  }
}
</style>
