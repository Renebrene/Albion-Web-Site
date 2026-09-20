<template>
  <section class="hero">
    <q-carousel
      v-model="slide"
      animated
      infinite
      :autoplay="autoplay"
      transition-prev="slide-right"
      transition-next="slide-left"
      class="hero-carousel"
    >
      <q-carousel-slide
        v-for="item in slides"
        :key="item.key"
        :name="item.key"
        class="hero-slide"
        :class="{ 'hero-slide-dark': item.type === 'production' }"
      >
        <div class="hero-inner">
          <div class="hero-content">
            <div class="hero-kicker">
              {{ item.kicker }}
            </div>

            <component
              :is="item.type === 'network' ? 'h1' : 'h2'"
            >
              {{ item.title }}
              <span>{{ item.title_accent }}</span>
            </component>

            <p>
              {{ item.text }}
            </p>

            <div class="hero-actions">
              <q-btn
                v-if="item.primary_button"
                unelevated
                :label="item.primary_button.label"
                class="hero-primary"
                :to="item.primary_button.to"
              />

              <q-btn
                v-if="item.secondary_button"
                flat
                :label="item.secondary_button.label"
                class="hero-secondary"
                :to="item.secondary_button.to"
              />
            </div>
          </div>

          <div
            class="hero-visual"
            :class="{
              'hero-visual-production': item.type === 'production',
              'hero-visual-digital': item.type === 'digital'
            }"
          >
            <template v-if="item.type === 'network'">
              <div class="visual-card visual-card-main">
                <div class="visual-label">
                  {{ item.visual?.label }}
                </div>

                <div class="visual-number">
                  {{ item.visual?.number }}
                </div>

                <div class="visual-text">
                  {{ item.visual?.text }}
                </div>
              </div>

              <div class="visual-card visual-card-small">
                <strong>
                  {{ item.visual?.small_value }}
                </strong>

                <span>
                  {{ item.visual?.small_text }}
                </span>
              </div>
            </template>

            <div
              v-else-if="item.type === 'production'"
              class="production-word"
            >
              {{ item.visual?.text }}
            </div>

            <div
              v-else-if="item.type === 'digital'"
              class="digital-screen"
            >
              {{ item.visual?.text }}
            </div>
          </div>
        </div>
      </q-carousel-slide>

      <template #control>
        <q-carousel-control
          position="bottom-right"
          :offset="[32, 28]"
        >
          <div class="hero-dots">
            <button
              v-for="item in slides"
              :key="item.key"
              class="hero-dot"
              :class="{ active: slide === item.key }"
              @click="slide = item.key"
            />
          </div>
        </q-carousel-control>
      </template>
    </q-carousel>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getPage } from '@/services/api'

const slide = ref('network')
const autoplay = ref(true)

const fallbackSlides = [
  {
    key: 'network',
    type: 'network',
    kicker: 'НАРУЖНАЯ РЕКЛАМА · ALBION',
    title: 'Ваша реклама',
    title_accent: 'работает на результат',
    text: 'Рекламные конструкции в Ростове-на-Дону и городах Ростовской области.',
    primary_button: {
      label: 'Подобрать конструкцию',
      to: '/vozmozhnosti'
    },
    secondary_button: {
      label: 'О компании',
      to: '/o-kompanii'
    },
    visual: {
      label: 'РЕКЛАМНАЯ СЕТЬ',
      number: '1569',
      text: 'конструкций в базе',
      small_value: '30+',
      small_text: 'лет на рынке'
    }
  },
  {
    key: 'production',
    type: 'production',
    kicker: 'ALBION · КОМПЛЕКСНЫЕ РЕШЕНИЯ',
    title: 'От идеи',
    title_accent: 'до размещения',
    text: 'Производство рекламы, брендинг, полиграфия, транспортная реклама и монтаж.',
    primary_button: {
      label: 'Наши направления',
      to: '/napravleniya'
    },
    visual: {
      text: 'ALBION'
    }
  },
  {
    key: 'digital',
    type: 'digital',
    kicker: 'DIGITAL · НОВЫЙ ФОРМАТ',
    title: 'Цифровая реклама',
    title_accent: 'в местах с высоким трафиком',
    text: 'Видеоформаты и современные рекламные поверхности для заметных кампаний.',
    primary_button: {
      label: 'Смотреть возможности',
      to: '/vozmozhnosti'
    },
    visual: {
      text: 'DIGITAL'
    }
  }
]

const slides = ref(fallbackSlides)

onMounted(async () => {
  try {
    const page = await getPage('home')
    const hero = page?.blocks?.find((block) => block.key === 'hero')
    const cmsSlides = hero?.content?.slides

    if (Array.isArray(cmsSlides) && cmsSlides.length > 0) {
      slides.value = cmsSlides
      slide.value = cmsSlides[0].key
      autoplay.value = hero.content.autoplay !== false
    }
  } catch (error) {
    console.warn('Не удалось загрузить Hero из CMS:', error)
  }
})
</script>

<style scoped>
.hero {
  position: relative;
  width: 100%;
}

.hero-carousel {
  min-height: 560px;
  background: #18232d;
}

.hero-slide {
  min-height: 560px;
  padding: 0;
  background:
    radial-gradient(circle at 75% 35%, rgba(225, 42, 31, 0.18), transparent 32%),
    linear-gradient(120deg, #17212b 0%, #26343e 55%, #34444e 100%);
}

.hero-slide-dark {
  background:
    radial-gradient(circle at 78% 30%, rgba(255, 255, 255, 0.08), transparent 30%),
    linear-gradient(120deg, #101820, #1d2933);
}

.hero-inner {
  width: min(1280px, 88%);
  min-height: 560px;
  margin: 0 auto;

  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  align-items: center;
  gap: 50px;
}

.hero-content {
  max-width: 700px;
}

.hero-kicker {
  margin-bottom: 20px;

  color: #e12a1f;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 2.5px;
}

h1,
h2 {
  margin: 0;

  color: #fff;

  font-size: clamp(42px, 5.2vw, 72px);
  line-height: 0.98;
  letter-spacing: -2px;
  font-weight: 900;
}

h1 span,
h2 span {
  display: block;
  color: #fff;
}

.hero-content p {
  max-width: 600px;
  margin: 28px 0 0;

  color: rgba(255, 255, 255, 0.72);
  font-size: 18px;
  line-height: 1.55;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 34px;
}

.hero-primary {
  min-height: 50px;
  padding: 0 24px;

  background: #e12a1f;
  color: #fff;

  border-radius: 7px;

  font-weight: 800;
}

.hero-secondary {
  color: #fff;
  font-weight: 700;
}

.hero-visual {
  position: relative;
  min-height: 390px;

  display: flex;
  align-items: center;
  justify-content: center;
}

.visual-card {
  position: absolute;

  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 18px;

  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(15px);

  box-shadow: 0 30px 80px rgba(0, 0, 0, 0.2);
}

.visual-card-main {
  width: 340px;
  min-height: 260px;
  padding: 34px;
}

.visual-label {
  color: rgba(255, 255, 255, 0.55);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 2px;
}

.visual-number {
  margin-top: 45px;

  color: #fff;
  font-size: 72px;
  line-height: 1;
  font-weight: 900;
}

.visual-text {
  margin-top: 10px;
  color: rgba(255, 255, 255, 0.6);
}

.visual-card-small {
  right: 5%;
  bottom: 35px;

  width: 180px;
  padding: 20px;

  display: flex;
  flex-direction: column;
}

.visual-card-small strong {
  color: #fff;
  font-size: 36px;
  font-weight: 900;
}

.visual-card-small span {
  margin-top: 4px;
  color: rgba(255, 255, 255, 0.55);
  font-size: 13px;
}

.production-word {
  color: rgba(255, 255, 255, 0.08);
  font-size: clamp(70px, 12vw, 170px);
  line-height: 1;
  font-weight: 900;
  letter-spacing: -8px;
}

.digital-screen {
  width: 390px;
  aspect-ratio: 16 / 9;

  display: grid;
  place-items: center;

  border: 12px solid #111a20;
  border-radius: 14px;

  background:
    linear-gradient(
      135deg,
      rgba(225, 42, 31, 0.8),
      rgba(225, 42, 31, 0.15)
    );

  color: #fff;
  font-size: 40px;
  font-weight: 900;
  letter-spacing: 3px;

  box-shadow: 0 35px 90px rgba(0, 0, 0, 0.35);
}

.hero-dots {
  display: flex;
  gap: 7px;
}

.hero-dot {
  width: 30px;
  height: 3px;
  padding: 0;
  border: 0;

  background: rgba(255, 255, 255, 0.3);

  cursor: pointer;
  transition: 0.2s;
}

.hero-dot.active {
  width: 50px;
  background: #e12a1f;
}

@media (max-width: 900px) {
  .hero-carousel,
  .hero-slide,
  .hero-inner {
    min-height: 650px;
  }

  .hero-inner {
    grid-template-columns: 1fr;
    gap: 20px;
    padding: 60px 0;
  }

  .hero-visual {
    min-height: 260px;
  }

  .visual-card-main {
    width: 290px;
    min-height: 210px;
  }

  .visual-number {
    margin-top: 25px;
    font-size: 56px;
  }

  .digital-screen {
    width: min(390px, 90%);
  }
}

@media (max-width: 600px) {
  .hero-inner {
    width: 90%;
  }

  h1,
  h2 {
    font-size: 40px;
    letter-spacing: -1px;
  }

  .hero-content p {
    font-size: 16px;
  }

  .hero-actions {
    flex-wrap: wrap;
  }

  .visual-card-small {
    right: 0;
  }
}
</style>
