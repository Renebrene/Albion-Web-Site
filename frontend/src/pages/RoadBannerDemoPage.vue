<script setup lang="ts">
import { ref } from 'vue'
import RoadBanner from '@/components/common/RoadBanner.vue'

const height = ref(280)
const trafficDensity = ref(1)
const speedFactor = ref(1)
const paused = ref(false)
const showBanner = ref(true)

function onReady() {
  console.log('[RoadBannerDemo] Component ready')
}

function onError(err: Error) {
  console.error('[RoadBannerDemo] Error:', err)
}
</script>

<template>
  <q-page class="road-banner-demo">
    <!-- БАННЕР (в самом верху) -->
    <RoadBanner
      :height="height"
      :traffic-density="trafficDensity"
      :speed-factor="speedFactor"
      :paused="paused"
      @ready="onReady"
      @error="onError"
    />

    <!-- ОБЫЧНЫЙ КОНТЕНТ СТРАНИЦЫ (под баннером) -->
    <div class="demo-content">
      <div class="demo-header">
        <h1>Демо: RoadBanner — Анимированная городская дорога</h1>
        <p class="subtitle">
          Low-poly баннер с интерактивным трафиком, светофорами и пешеходами.
          Компонент работает поверх контента, не блокирует скролл.
        </p>
      </div>

      <div class="demo-controls">
        <q-card class="control-card">
          <q-card-section>
            <div class="control-label">Высота баннера</div>
            <q-slider
              v-model="height"
              :min="150"
              :max="400"
              :step="10"
              label
              label-always
              color="primary"
            />
          </q-card-section>
        </q-card>

        <q-card class="control-card">
          <q-card-section>
            <div class="control-label">Плотность трафика</div>
            <q-slider
              v-model="trafficDensity"
              :min="0.3"
              :max="2"
              :step="0.1"
              label
              label-always
              color="primary"
            />
          </q-card-section>
        </q-card>

        <q-card class="control-card">
          <q-card-section>
            <div class="control-label">Множитель скорости</div>
            <q-slider
              v-model="speedFactor"
              :min="0.3"
              :max="2"
              :step="0.1"
              label
              label-always
              color="primary"
            />
          </q-card-section>
        </q-card>

        <q-card class="control-card">
          <q-card-section>
            <q-toggle
              v-model="paused"
              label="Пауза анимации"
              color="negative"
            />
          </q-card-section>
        </q-card>
      </div>

      <div class="demo-section">
        <h2>Описание компонента</h2>
        <q-card class="info-card">
          <q-card-section>
            <p
              ><strong>RoadBanner</strong> — переиспользуемый Vue 3 компонент
              для декоративного баннера в стиле low-poly.</p
            >

            <h3>Ключевые особенности:</h3>
            <ul>
              <li>Двусторонняя дорога с разметкой, тротуарами, бордюрами</li>
              <li
                >Два перекрёстка с зебрами и синхронизированными светофорами
                (фазы сдвинуты)</li
              >
              <li
                >Пул машин (объектный пул) — без аллокаций в кадре, 6 цветов
                кузовов</li
              >
              <li
                >Плавная кинематика: разгон, торможение перед стоп-линией,
                дистанция до впереди идущей</li
              >
              <li
                >Ортографическая камера для изометрического ракурса, адаптив под
                любую ширину</li
              >
              <li
                >Graceful fallback: SVG-баннер при отсутствии WebGL или
                prefers-reduced-motion</li
              >
              <li
                >Пауза рендера вне вьюпорта (IntersectionObserver) и в скрытой
                вкладке</li
              >
              <li>Полная очистка GPU-ресурсов на unmount</li>
            </ul>

            <h3>API (Props):</h3>
            <table class="props-table">
              <thead>
                <tr
                  ><th>Prop</th><th>Тип</th><th>Default</th
                  ><th>Описание</th></tr
                >
              </thead>
              <tbody>
                <tr
                  ><td>height</td><td>number</td><td>280</td
                  ><td>Высота баннера в px</td></tr
                >
                <tr
                  ><td>trafficDensity</td><td>number</td><td>1</td
                  ><td>Плотность трафика (0.3–2.0)</td></tr
                >
                <tr
                  ><td>speedFactor</td><td>number</td><td>1</td
                  ><td>Множитель скорости машин</td></tr
                >
                <tr
                  ><td>paused</td><td>boolean</td><td>false</td
                  ><td>Внешняя пауза анимации</td></tr
                >
              </tbody>
            </table>

            <h3>Events:</h3>
            <ul>
              <li><code>@ready</code> — Three.js сцена инициализирована</li>
              <li
                ><code>@error</code> — ошибка инициализации (WebGL недоступен и
                т.д.)</li
              >
            </ul>
          </q-card-section>
        </q-card>
      </div>

      <div class="demo-section">
        <h2>Тест скролла и слоёв</h2>
        <q-card class="scroll-test-card">
          <q-card-section>
            <p
              >Прокрутите страницу вниз — баннер должен уйти за экран, скролл
              работает нативно, Canvas не перехватывает wheel/touch события.</p
            >
            <div class="spacer" style="height: 800px">
              <div class="scroll-marker">↓ Прокрутите вниз ↓</div>
            </div>
            <p>Если вы видите этот текст — скролл работает корректно.</p>
          </q-card-section>
        </q-card>
      </div>

      <div class="demo-section">
        <h2>Тест повторного монтирования</h2>
        <q-card class="remount-card">
          <q-card-section>
            <p
              >Компонент корректно очищает ресурсы при размонтировании. Можно
              проверить повторный mount/unmount:</p
            >
            <q-btn
              label="Скрыть/Показать баннер"
              color="primary"
              @click="showBanner = !showBanner"
            />
          </q-card-section>
        </q-card>

        <div v-if="showBanner" class="remount-test">
          <RoadBanner
            :height="200"
            :traffic-density="1.5"
            :speed-factor="1.2"
            @ready="onReady"
            @error="onError"
          />
        </div>
      </div>
    </div>
  </q-page>
</template>

<style scoped>
.road-banner-demo {
  min-height: 100vh;
  background: #f3f5f6;
}

.demo-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.demo-header {
  text-align: center;
  margin-bottom: 32px;
  padding-top: 16px;
}

.demo-header h1 {
  margin: 0 0 8px;
  color: #17212b;
  font-size: clamp(24px, 3vw, 36px);
  font-weight: 800;
  line-height: 1.2;
}

.subtitle {
  margin: 0;
  color: #5b6873;
  font-size: 16px;
  line-height: 1.5;
  max-width: 700px;
  margin-left: auto;
  margin-right: auto;
}

.demo-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.control-card {
  background: #fff;
  border-radius: 12px;
}

.control-label {
  font-size: 13px;
  font-weight: 600;
  color: #5b6873;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.demo-section {
  margin-bottom: 40px;
}

.demo-section h2 {
  margin: 0 0 16px;
  color: #17212b;
  font-size: 22px;
  font-weight: 800;
}

.info-card,
.scroll-test-card,
.remount-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e4e6ea;
}

.info-card ul {
  margin: 12px 0;
  padding-left: 20px;
}

.info-card li {
  margin: 8px 0;
  color: #3a4750;
  line-height: 1.6;
}

.props-table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 14px;
}

.props-table th,
.props-table td {
  padding: 10px 12px;
  border: 1px solid #e4e6ea;
  text-align: left;
}

.props-table th {
  background: #f4f6f7;
  font-weight: 700;
  color: #17212b;
}

.props-table code {
  background: #f0f2f4;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.spacer {
  display: flex;
  align-items: center;
  justify-content: center;
}

.scroll-marker {
  color: #8b949b;
  font-size: 14px;
  animation: bounce 1.5s infinite;
}

@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(8px);
  }
}

.remount-test {
  margin-top: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px dashed #c1c7cd;
}
</style>
