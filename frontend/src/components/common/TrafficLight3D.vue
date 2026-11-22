<script setup>
/*
 * Светофор на canvas 2D: сцена, стойка и три сигнала с переключением фаз
 * (красный → красный+жёлтый → зелёный → жёлтый).
 *
 * Размеры считаем в ЛОГИЧЕСКИХ (CSS) пикселях, а канвас держим в
 * `devicePixelRatio` раз крупнее для резкости. Раньше рисование брало
 * `canvas.width` (это device-пиксели) при уже масштабированном контексте:
 * на экранах с dpr > 1 светофор рисовался вдвое крупнее и уезжал за правый
 * край — выглядело как «не работает».
 */
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  /** Высота контейнера в пикселях */
  height: { type: Number, default: 380 },
  /** Автоматически переключать фазы */
  autoCycle: { type: Boolean, default: true },
  /** Скорость цикла (множитель): 1 — обычная, 2 — вдвое быстрее */
  cycleSpeed: { type: Number, default: 1 }
})

const canvasRef = ref(null)

let animationId = 0
let ctx = null
let disposed = false
let phaseStartTime = 0
let lastTime = 0

/* Логический размер полотна (CSS-пиксели) — в нём и рисуем. */
let viewWidth = 0
let viewHeight = 0

/* Цвета светофора */
const COLORS = {
  red: { on: '#ff3b30', off: '#3d0d0d', glow: '#ff6b5a' },
  yellow: { on: '#ffc53d', off: '#3d300d', glow: '#ffdd6b' },
  green: { on: '#2fe36a', off: '#0d3d1a', glow: '#5aff7a' }
}

/* Фазы: [красный, жёлтый, зелёный] — true = включён */
const PHASES = [
  [true, false, false], // красный
  [true, true, false], // красный + жёлтый
  [false, false, true], // зелёный
  [false, true, false] // жёлтый
]
const PHASE_DURATIONS = [4000, 1400, 4000, 1400] // мс

let currentPhase = 0
let lightsState = PHASES[0]

function drawTrafficLight(timestamp) {
  if (!ctx || !viewWidth || !viewHeight) {
    return
  }

  const width = viewWidth
  const height = viewHeight
  const cx = width / 2
  const topMargin = 20
  const bottomMargin = 20

  // Очистка
  ctx.clearRect(0, 0, width, height)

  // Размеры светофора: ограничены и шириной, и высотой полотна
  const boxWidth = Math.min(140, width * 0.6, height * 0.34)
  const lightRadius = boxWidth / 5
  const spacing = lightRadius * 0.5
  const boxHeight = lightRadius * 6 + spacing * 2 + 30
  const boxX = cx - boxWidth / 2
  const boxY = topMargin

  // Столб
  const poleWidth = Math.max(8, boxWidth * 0.12)
  const poleHeight = Math.max(0, height - boxY - boxHeight - bottomMargin)
  const poleX = cx - poleWidth / 2

  const poleGradient = ctx.createLinearGradient(poleX, 0, poleX + poleWidth, 0)
  poleGradient.addColorStop(0, '#4a4f56')
  poleGradient.addColorStop(0.5, '#2d3136')
  poleGradient.addColorStop(1, '#1a1d20')
  ctx.fillStyle = poleGradient
  ctx.fillRect(poleX, boxY + boxHeight, poleWidth, poleHeight)

  // Основание столба
  const baseWidth = boxWidth * 0.7
  const baseHeight = 12
  const baseX = cx - baseWidth / 2
  const baseY = height - bottomMargin - baseHeight
  const baseGradient = ctx.createLinearGradient(0, baseY, 0, baseY + baseHeight)
  baseGradient.addColorStop(0, '#3a3f47')
  baseGradient.addColorStop(1, '#1a1d20')
  ctx.fillStyle = baseGradient
  ctx.fillRect(baseX, baseY, baseWidth, baseHeight)

  // Корпус светофора
  const radius = 12
  ctx.fillStyle = '#1a1d20'
  ctx.beginPath()
  ctx.roundRect(boxX, boxY, boxWidth, boxHeight, radius)
  ctx.fill()

  // Обводка корпуса
  ctx.strokeStyle = '#3a3f47'
  ctx.lineWidth = 2
  ctx.stroke()

  // Три сигнала
  const lightColors = ['red', 'yellow', 'green']

  lightColors.forEach((color, i) => {
    const isOn = lightsState[i]
    const cy = boxY + 20 + lightRadius + i * (lightRadius * 2 + spacing)
    const lx = cx

    // Козырёк
    ctx.fillStyle = '#11151a'
    ctx.beginPath()
    ctx.moveTo(lx - lightRadius - 4, cy - lightRadius + 2)
    ctx.lineTo(lx + lightRadius + 4, cy - lightRadius + 2)
    ctx.quadraticCurveTo(
      lx + lightRadius + 4,
      cy - lightRadius - 8,
      lx,
      cy - lightRadius - 8
    )
    ctx.quadraticCurveTo(
      lx - lightRadius - 4,
      cy - lightRadius - 8,
      lx - lightRadius - 4,
      cy - lightRadius + 2
    )
    ctx.fill()

    // Сама линза
    const lightConfig = COLORS[color]

    const lensGradient = ctx.createRadialGradient(
      lx - lightRadius * 0.3,
      cy - lightRadius * 0.3,
      0,
      lx,
      cy,
      lightRadius
    )

    if (isOn) {
      lensGradient.addColorStop(0, '#ffffff')
      lensGradient.addColorStop(0.3, lightConfig.on)
      lensGradient.addColorStop(1, lightConfig.off)
    } else {
      lensGradient.addColorStop(0, '#2a2d30')
      lensGradient.addColorStop(1, '#0d0f11')
    }

    ctx.fillStyle = lensGradient
    ctx.beginPath()
    ctx.arc(lx, cy, lightRadius, 0, Math.PI * 2)
    ctx.fill()

    // Обводка линзы
    ctx.strokeStyle = isOn ? lightConfig.glow : '#2a2d30'
    ctx.lineWidth = isOn ? 3 : 1
    ctx.globalAlpha = isOn ? 0.8 : 1
    ctx.stroke()
    ctx.globalAlpha = 1

    // Свечение если включено
    if (isOn) {
      const glowGradient = ctx.createRadialGradient(
        lx,
        cy,
        0,
        lx,
        cy,
        lightRadius * 2.5
      )
      glowGradient.addColorStop(0, lightConfig.glow + '80')
      glowGradient.addColorStop(0.5, lightConfig.glow + '30')
      glowGradient.addColorStop(1, lightConfig.glow + '00')
      ctx.fillStyle = glowGradient
      ctx.beginPath()
      ctx.arc(lx, cy, lightRadius * 2.5, 0, Math.PI * 2)
      ctx.fill()
    }
  })

  // Пульсация для активного света
  if (lightsState.some(state => state)) {
    const activeIndex = lightsState.findIndex(state => state)

    if (activeIndex >= 0) {
      const pulse = (Math.sin(timestamp * 0.004) + 1) * 0.5 // 0..1
      const color = lightColors[activeIndex]
      const cy =
        boxY + 20 + lightRadius + activeIndex * (lightRadius * 2 + spacing)
      const glowGradient = ctx.createRadialGradient(
        cx,
        cy,
        0,
        cx,
        cy,
        lightRadius * 3
      )
      glowGradient.addColorStop(
        0,
        COLORS[color].glow +
          Math.floor(30 + pulse * 40)
            .toString(16)
            .padStart(2, '0')
      )
      glowGradient.addColorStop(1, COLORS[color].glow + '00')
      ctx.fillStyle = glowGradient
      ctx.beginPath()
      ctx.arc(cx, cy, lightRadius * 3, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

function animate(timestamp) {
  if (disposed) {
    return
  }

  if (!lastTime) {
    lastTime = timestamp
    phaseStartTime = timestamp
  }

  // Переключение фаз
  if (props.autoCycle) {
    const speed = props.cycleSpeed > 0 ? props.cycleSpeed : 1
    const elapsed = timestamp - phaseStartTime
    const duration = PHASE_DURATIONS[currentPhase] / speed

    if (elapsed >= duration) {
      phaseStartTime = timestamp
      currentPhase = (currentPhase + 1) % PHASES.length
      lightsState = PHASES[currentPhase]
    }
  }

  drawTrafficLight(timestamp)
  animationId = requestAnimationFrame(animate)
}

function resize() {
  const canvas = canvasRef.value

  if (!canvas) {
    return
  }

  const container = canvas.parentElement
  const width = container ? container.clientWidth : 0
  const height = props.height || 380

  // Контейнер может быть скрыт (0 px) — тогда подождём следующего замера.
  if (!width || !height) {
    return
  }

  viewWidth = width
  viewHeight = height

  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(width * dpr)
  canvas.height = Math.round(height * dpr)
  canvas.style.width = width + 'px'
  canvas.style.height = height + 'px'

  ctx = canvas.getContext('2d')
  // Масштабируем контекст один раз на замер: после смены canvas.width
  // трансформация сбрасывается, поэтому ctx.scale здесь не накапливается.
  ctx.scale(dpr, dpr)
}

onMounted(() => {
  resize()
  animate(performance.now())

  const observer = new ResizeObserver(resize)

  if (canvasRef.value?.parentElement) {
    observer.observe(canvasRef.value.parentElement)
  }

  canvasRef.value.__resizeObserver = observer

  // Пауза в фоновой вкладке: не жжём CPU впустую.
  const handleVisibility = () => {
    if (document.hidden) {
      cancelAnimationFrame(animationId)
    } else {
      lastTime = 0
      animate(performance.now())
    }
  }

  document.addEventListener('visibilitychange', handleVisibility)
  canvasRef.value.__visibilityHandler = handleVisibility
})

onUnmounted(() => {
  disposed = true
  cancelAnimationFrame(animationId)

  const canvas = canvasRef.value

  if (canvas) {
    if (canvas.__resizeObserver) {
      canvas.__resizeObserver.disconnect()
    }

    if (canvas.__visibilityHandler) {
      document.removeEventListener(
        'visibilitychange',
        canvas.__visibilityHandler
      )
    }
  }
})
</script>

<template>
  <div
    class="traffic-light-canvas"
    :style="{ height: (height || 380) + 'px', width: '100%' }"
  >
    <canvas
      ref="canvasRef"
      class="tl-canvas"
      aria-label="Интерактивный светофор"
      role="img"
    />
  </div>
</template>

<style scoped>
.traffic-light-canvas {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: #0b0e13;
  border: 1px solid rgba(255, 77, 61, 0.15);
  display: flex;
  justify-content: center;
  align-items: center;
}

.tl-canvas {
  display: block;
  max-width: 100%;
  max-height: 100%;
}
</style>
