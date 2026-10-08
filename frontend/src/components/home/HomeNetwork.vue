<template>
  <section class="network-section">
    <div class="network-shell">

      <div class="network-heading">
        <div>
          <div class="eyebrow">СОБСТВЕННАЯ СЕТЬ</div>

          <h2>
            Albion
            <span>рядом с вашим клиентом</span>
          </h2>
        </div>

        <p>
          Собственная сеть рекламных конструкций
          в Ростове-на-Дону и городах Ростовской области.
        </p>
      </div>

      <div class="network-layout">

        <!-- Визуальная карта -->
        <div class="network-map">

          <div class="map-label">
            <span class="map-dot"></span>
            РОСТОВСКАЯ ОБЛАСТЬ
          </div>

          <div
            v-for="point in mapPoints"
            :key="point.city"
            class="map-point"
            :class="{ main: point.main }"
            :style="{
              left: `${point.x}%`,
              top: `${point.y}%`
            }"
          >
            <span class="point-pulse"></span>

            <div class="point-label">
              {{ point.city }}
              <strong>{{ point.count }}</strong>
            </div>
          </div>

          <div class="route route-one"></div>
          <div class="route route-two"></div>
          <div class="route route-three"></div>

          <div class="map-caption">
            <strong>{{ constructionCount }}</strong>
            <span>конструкций в собственной сети</span>
          </div>
        </div>

        <!-- Информация о сети -->
        <div class="network-info">

          <div class="network-block">
            <div class="block-number">01</div>

            <div>
              <h3>Города присутствия</h3>

              <div class="cities">
                <button
                  v-for="city in cityList"
                  :key="city.name"
                  type="button"
                  class="city"
                  @click="goToCity(city.name)"
                >
                  <span>{{ city.name }}</span>
                  <strong>{{ city.count }}</strong>
                </button>
              </div>
            </div>
          </div>

          <div class="network-block">
            <div class="block-number">02</div>

            <div>
              <h3>Ключевые трассы и территории</h3>

              <div class="highways">
                <div
                  v-for="highway in highways"
                  :key="highway"
                  class="highway"
                >
                  <span class="highway-icon">→</span>
                  <span>{{ highway }}</span>
                </div>
              </div>
            </div>
          </div>

          <q-btn
            unelevated
            label="Смотреть всю сеть"
            class="network-button"
            to="/vozmozhnosti"
          />

        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getConstructions } from '@/services/api'

const router = useRouter()

const constructions = ref([])

onMounted(async () => {
  try {
    constructions.value = await getConstructions()
  } catch (error) {
    console.error('Не удалось загрузить сеть:', error)
  }
})

const constructionCount = computed(() => {
  return constructions.value.length
})

const cityList = computed(() => {
  const counts = new Map()

  constructions.value.forEach(item => {
    if (!item.city) return

    counts.set(
      item.city,
      (counts.get(item.city) || 0) + 1
    )
  })

  return [...counts.entries()]
    .map(([name, count]) => ({
      name,
      count
    }))
    .sort((a, b) => b.count - a.count)
})

/*
 * Положение городов на визуальной схеме рассчитывается
 * автоматически из реальных координат конструкций API.
 *
 * Это не географическая карта, а визуальная схема сети.
 * Поэтому lat/lng нормализуются в диапазон 10–90%.
 */
const cityCoordinates = computed(() => {
  const cities = new Map()

  constructions.value.forEach(item => {
    if (!item.city) return

    const lat = Number(item.lat)
    const lng = Number(item.lng)

    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return

    if (!cities.has(item.city)) {
      cities.set(item.city, {
        latSum: 0,
        lngSum: 0,
        count: 0
      })
    }

    const city = cities.get(item.city)

    city.latSum += lat
    city.lngSum += lng
    city.count += 1
  })

  return [...cities.entries()].map(([name, data]) => ({
    name,
    lat: data.latSum / data.count,
    lng: data.lngSum / data.count
  }))
})

const mapPoints = computed(() => {
  const points = cityCoordinates.value

  if (!points.length) return []

  const minLat = Math.min(...points.map(point => point.lat))
  const maxLat = Math.max(...points.map(point => point.lat))
  const minLng = Math.min(...points.map(point => point.lng))
  const maxLng = Math.max(...points.map(point => point.lng))

  const latRange = maxLat - minLat || 1
  const lngRange = maxLng - minLng || 1

  return cityList.value
    .map(city => {
      const coordinates = points.find(
        point => point.name === city.name
      )

      if (!coordinates) return null

      return {
        city: city.name,
        count: city.count,

        // Долгота → горизонтальная позиция.
        x: 10 + ((coordinates.lng - minLng) / lngRange) * 80,

        // Широта → вертикальная позиция.
        // На экране север должен быть выше.
        y: 90 - ((coordinates.lat - minLat) / latRange) * 80,

        main: city.name === 'Ростов-на-Дону'
      }
    })
    .filter(Boolean)
})

const highways = [
  'М4 Москва — Ростов-на-Дону',
  'М23 Ростов-на-Дону — Таганрог',
  'Родионово-Несветайская трасса',
  'Верхнетемерницкий'
]

function goToCity(city) {
  router.push({
    path: '/vozmozhnosti',
    query: {
      city
    }
  })
}
</script>

<style scoped>
.network-section {
  padding: 120px 0;

  background: #f4f6f7;
}

.network-shell {
  width: min(1280px, 88%);
  margin: 0 auto;
}

.network-heading {
  display: grid;
  grid-template-columns: 1fr 0.55fr;
  gap: 80px;
  align-items: end;
}

.eyebrow {
  margin-bottom: 14px;

  color: var(--albion-accent);

  font-size: 10px;
  font-weight: 900;
  letter-spacing: 2px;
}

h2 {
  margin: 0;

  color: #17212b;

  font-size: clamp(38px, 4.5vw, 60px);
  line-height: 1;
  letter-spacing: -2px;
  font-weight: 900;
}

h2 span {
  display: block;
  color: #8b969e;
}

.network-heading > p {
  margin: 0;

  color: #71808c;

  font-size: 16px;
  line-height: 1.6;
}

.network-layout {
  display: grid;
  grid-template-columns: 1.05fr 0.95fr;
  gap: 14px;

  margin-top: 55px;
}

.network-map {
  position: relative;
  min-height: 570px;
  overflow: hidden;

  border-radius: 18px;

  background:
    radial-gradient(
      circle at 60% 50%,
      rgba(225, 42, 31, 0.16),
      transparent 26%
    ),
    linear-gradient(
      145deg,
      #dfe5e7,
      #cbd4d8
    );
}

.network-map::before,
.network-map::after {
  content: '';

  position: absolute;

  border: 1px solid rgba(255, 255, 255, 0.65);
  border-radius: 50%;

  pointer-events: none;
}

.network-map::before {
  width: 580px;
  height: 580px;

  left: 25%;
  top: 5%;
}

.network-map::after {
  width: 420px;
  height: 420px;

  left: 38%;
  top: 18%;
}

.map-label {
  position: absolute;
  top: 25px;
  left: 25px;

  display: flex;
  align-items: center;
  gap: 8px;

  color: #56636c;

  font-size: 9px;
  font-weight: 900;
  letter-spacing: 1.5px;
}

.map-dot {
  width: 7px;
  height: 7px;

  border-radius: 50%;

  background: var(--albion-accent);
}

.map-point {
  position: absolute;

  width: 12px;
  height: 12px;

  border-radius: 50%;

  background: #17212b;
  border: 3px solid #fff;

  transform: translate(-50%, -50%);

  z-index: 5;
}

.map-point.main {
  width: 18px;
  height: 18px;

  background: var(--albion-accent);
}

.point-pulse {
  position: absolute;
  inset: -8px;

  border: 1px solid rgba(225, 42, 31, 0.35);
  border-radius: 50%;
}

.point-label {
  position: absolute;
  left: 18px;
  top: -8px;

  display: flex;
  align-items: center;
  gap: 7px;

  white-space: nowrap;

  color: #17212b;

  font-size: 10px;
  font-weight: 800;
}

.point-label strong {
  padding: 3px 6px;

  border-radius: 4px;

  background: #fff;

  color: var(--albion-accent);

  font-size: 9px;
}

.route {
  position: absolute;

  height: 2px;

  transform-origin: left center;

  background: rgba(225, 42, 31, 0.45);

  z-index: 2;
}

.route-one {
  width: 340px;

  left: 34%;
  top: 50%;

  transform: rotate(-8deg);
}

.route-two {
  width: 300px;

  left: 47%;
  top: 54%;

  transform: rotate(25deg);
}

.route-three {
  width: 360px;

  left: 46%;
  top: 48%;

  transform: rotate(-32deg);
}

.map-caption {
  position: absolute;
  left: 25px;
  bottom: 25px;

  display: flex;
  flex-direction: column;
}

.map-caption strong {
  color: #17212b;

  font-size: 40px;
  line-height: 1;
  font-weight: 900;
}

.map-caption span {
  margin-top: 6px;

  color: #64717a;

  font-size: 11px;
}

.network-info {
  padding: 35px;

  border-radius: 18px;

  background: #fff;
}

.network-block {
  display: grid;
  grid-template-columns: 35px 1fr;
  gap: 15px;

  padding-bottom: 32px;
  margin-bottom: 30px;

  border-bottom: 1px solid #e9edef;
}

.block-number {
  color: var(--albion-accent);

  font-size: 10px;
  font-weight: 900;
}

h3 {
  margin: 0 0 18px;

  color: #17212b;

  font-size: 18px;
  font-weight: 900;
}

.cities {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px 20px;
}

.city {
  width: 100%;
  padding: 10px 0;

  display: flex;
  justify-content: space-between;
  align-items: center;

  border: 0;
  border-bottom: 1px solid #edf0f2;

  background: transparent;

  color: #4f5c65;

  text-align: left;

  cursor: pointer;
}

.city:hover {
  color: var(--albion-accent);
}

.city strong {
  color: #9ba5ab;

  font-size: 11px;
}

.highways {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.highway {
  display: flex;
  align-items: center;
  gap: 10px;

  color: #64717a;

  font-size: 12px;
  line-height: 1.4;
}

.highway-icon {
  color: var(--albion-accent);
  font-weight: 900;
}

.network-button {
  min-height: 48px;
  padding: 0 22px;

  border-radius: 7px;

  background: #17212b;
  color: #fff;

  font-weight: 800;
}

@media (max-width: 950px) {
  .network-heading {
    grid-template-columns: 1fr;
    gap: 25px;
  }

  .network-layout {
    grid-template-columns: 1fr;
  }

  .network-map {
    min-height: 500px;
  }
}

@media (max-width: 600px) {
  .network-section {
    padding: 75px 0;
  }

  .network-shell {
    width: 90%;
  }

  .network-info {
    padding: 25px 20px;
  }

  .cities {
    grid-template-columns: 1fr;
  }

  .network-map {
    min-height: 430px;
  }

  .point-label {
    font-size: 9px;
  }
}
</style>
