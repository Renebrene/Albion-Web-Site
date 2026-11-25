<template>
  <div class="road-slide">
    <div class="road-slide-content">
      <h1 class="road-slide-title">{{ slide.title }}</h1>
      <p v-if="slide.text" class="road-slide-text">{{ slide.text }}</p>
    </div>

    <!--
      Код баннера — отдельный HTML-документ из админки.
      sandbox="allow-scripts allow-same-origin": iframe имеет тот же origin,
      что и родитель, поэтому может делать fetch к /api/* (CSP разрешает
      http://127.0.0.1:*). Скрипт не получает доступ к cookie родителя
      (sandbox изолирует cookie-хранилище).
      pointer-events: none — колесо/свайп листают слайды поверх баннера.
    -->
    <div v-if="active && slide.has_code" class="road-slide-stage">
      <iframe
        ref="frame"
        :src="codeUrl"
        class="road-slide-frame"
        referrerpolicy="no-referrer"
        loading="lazy"
        title="Светофорные объекты — анимированная городская дорога"
        @load="onFrameLoad"
      ></iframe>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

/*
 * Слайд «Светофорные объекты»: заголовок/текст из админки + 3D-баннер,
 * который идёт по низу визуальной части. Сам код баннера хранится в
 * home_slides.code и обновляется через админку (главная страница).
 * iframe монтируется только на активном слайде — вне экрана WebGL-сцена
 * не крутится и не тратит CPU.
 */
const props = defineProps({
  slide: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  }
})

/* Код баннера сам содержит блок настроек (#banner-settings). */
const codeUrl = computed(() => `/api/home/slides/${props.slide.id}/code`)

/* Сценарий из чата приходит событием окна. Передаём его прямо в iframe,
   чтобы сцена перерисовалась сразу, не дожидаясь опроса. */
const frame = ref(null)
const frameLoaded = ref(false)
// Сценарий, пришедший до готовности iframe: отправим его сразу после load.
let pendingPayload = null

function postScenario(payload) {
  const target = frame.value?.contentWindow
  if (!target) return false
  target.postMessage({ type: 'albion-roadrunner', payload }, '*')
  return true
}

function forwardScenario(event) {
  const payload = event?.detail
  if (!payload) return
  if (!frameLoaded.value || !postScenario(payload)) {
    pendingPayload = payload
  }
}

function onFrameLoad() {
  frameLoaded.value = true
  if (!pendingPayload) return
  const payload = pendingPayload
  pendingPayload = null
  postScenario(payload)
}

onMounted(() => window.addEventListener('albion:roadrunner-scenario', forwardScenario))
onBeforeUnmount(() => window.removeEventListener('albion:roadrunner-scenario', forwardScenario))

// iframe существует только на активном слайде; при уходе со слайда
// считаем его неготовым, чтобы следующий сценарий не потерялся.
watch(
  () => props.active,
  (isActive) => {
    if (isActive) return
    frameLoaded.value = false
  }
)
</script>

<style scoped>
.road-slide {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.road-slide-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: clamp(10px, 1.8vh, 20px);
  padding: clamp(24px, 6vh, 72px) clamp(16px, 4vw, 64px) clamp(12px, 2vh, 24px);
  text-align: center;
}

.road-slide-title {
  margin: 0;
  font-size: clamp(26px, 4vw, 56px);
  font-weight: 900;
  letter-spacing: 0.04em;
}

.road-slide-text {
  margin: 0;
  max-width: min(900px, 92%);
  white-space: pre-line;
  font-size: clamp(14px, 1.5vw, 20px);
  line-height: 1.55;
  opacity: 0.92;
}

.road-slide-stage {
  position: relative;
  flex: none;
  width: 100%;
  /* Половина видимой части страницы; минимум — чтобы сцена не схлопнулась
     на очень низких окнах. */
  height: 50vh;
  min-height: 200px;
  overflow: hidden;
  background: #9fd4ec;
}

/* Плавный переход от тёмного слайда к светлому небу баннера. */
.road-slide-stage::after {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  z-index: 1;
  height: clamp(20px, 3.5vh, 38px);
  background: linear-gradient(
    180deg,
    rgba(20, 24, 29, 0.58),
    rgba(20, 24, 29, 0)
  );
  pointer-events: none;
}

.road-slide-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  pointer-events: none;
  /* Обрезка сцены делается внутри баннера, чтобы HUD оставался в углу. */
}

@media (max-width: 760px) {
  .road-slide-stage {
    height: 180px;
  }
}
</style>
