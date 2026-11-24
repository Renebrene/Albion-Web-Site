<template>
  <!-- Обёртка не перехватывает pointer-events: скролл страницы работает поверх баннера -->
  <div
    ref="containerRef"
    class="city-road-banner"
    :style="containerStyle"
    role="img"
    aria-label="Анимированная городская дорога с трафиком и светофорами"
  >
    <div
      v-if="fallbackSvg"
      class="city-road-banner__fallback"
      v-html="fallbackSvg"
    ></div>
  </div>
</template>

<script setup>
/*
  CityRoadBanner — декоративный low-poly баннер «Городская дорога».
  Трёхмерная сцена (Three.js, точечные импорты для tree-shaking):
  двухсторонняя дорога, два перекрёстка с зебрами и синхронными светофорами,
  пешеходы, пул машин с объектным пулом, кинематика разгона/торможения.
  Все геометрии генерируются кодом; при отсутствии WebGL — статичный SVG-фолбэк.
*/

import { onMounted, onBeforeUnmount, watch, ref, computed } from 'vue'
import {
  Scene,
  OrthographicCamera,
  WebGLRenderer,
  HemisphereLight,
  DirectionalLight,
  Fog,
  Mesh,
  Group,
  MeshStandardMaterial,
  MeshBasicMaterial,
  BoxGeometry,
  CylinderGeometry,
  CircleGeometry,
  PlaneGeometry,
  IcosahedronGeometry,
  Sprite,
  SpriteMaterial,
  AdditiveBlending,
  CanvasTexture,
  ACESFilmicToneMapping,
  Vector3
} from 'three'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

/* ============================================================
   PROPS / EMITS
   ============================================================ */

const props = defineProps({
  /** Высота баннера в px. null = адаптивная (280 десктоп / 180 мобайл) */
  height: { type: Number, default: null },
  /** Плотность трафика: 0.3 — редкая, 2.0 — плотная (модифицирует интервалы спавна) */
  trafficDensity: { type: Number, default: 1 },
  /** Множитель скорости машин и разгона/торможения */
  speedFactor: { type: Number, default: 1 },
  /** Внешняя пауза анимации (рендер останавливается) */
  paused: { type: Boolean, default: false },
  /** Длительность зелёной фазы светофора, с */
  greenDuration: { type: Number, default: 7 },
  /** Длительность жёлтой фазы, с */
  yellowDuration: { type: Number, default: 2.4 },
  /** Минимальная длительность красной фазы, с (реальная больше — см. FSM) */
  redDuration: { type: Number, default: 12 }
})

const emit = defineEmits(['ready', 'error'])

/* ============================================================
   КОНСТАНТЫ МИРА (все размеры — метры)
   ============================================================ */

// Дорога идёт по оси X. Перекрёстки — в x = ±IX.
const ROAD_HALF = 3.5 // полуширина проезжей части (две полосы по 3.5 м)
const ROAD_LEN = 140 // половина длины дороги (машины spawn/despawn за краем)
const SIDE_HALF = 3.0 // полуширина боковой улицы
const SIDE_LEN = 75 // глубина боковой улицы (уходит в туман)
const IX = 16 // |x| перекрёстков
const LANE_Z = 1.75 // центр полосы движения
const WALK_IN = 3.5 // внутренняя граница тротуара (= край дороги)
const WALK_OUT = 5.9 // внешняя граница тротуара
const CURB_H = 0.14
const STOP_OFF = 4.6 // стоп-линия: отступ от центра перекрёстка
const ZEBRA_HALF = 1.8 // зебра занимает x ∈ [ix−1.8, ix+1.8]
const CAR_LEN = 3.7
const CAR_HALF = 1.9
const MAX_CARS = 14 // жёсткий предел одновременных машин (объектный пул)
const CAM_AZ = 0.32 // азимут камеры (боковая изометрия), рад
const CAM_EL = 0.96 // высота камеры (~55°)

// Палитра: приглушённый город + насыщенные кузова
const COLORS = {
  grass: 0x8aa872,
  asphalt: 0x3b4046,
  sidewalk: 0xc3c8cd,
  curb: 0xa9aeb4,
  markWhite: 0xf2f4f6,
  markYellow: 0xf5c542,
  trunk: 0x6b4f35,
  crownA: 0x4e7a3a,
  crownB: 0x5d8a45,
  bush: 0x3f6b34,
  lamp: 0x555b61,
  pole: 0x3a3f45,
  glass: 0x18242f,
  wheel: 0x1d2126,
  carBody: [0xd63031, 0x0984e3, 0xf4b400, 0x00a389, 0x6c5ce7, 0xe17055],
  pedA: 0xc0392b,
  pedB: 0x2471a3,
  skin: 0xe8bf9a
}

// Состояния ламп светофора: активная / неактивная
const LAMP_RGB = { r: 0xff2d2d, y: 0xffd23f, g: 0x2ee66b }
const LAMP_OFF = { r: 0x4a1518, y: 0x4a3a10, g: 0x0f3d22 }

/* ============================================================
   Состояние компонента (ничего реактивного в кадровом цикле)
   ============================================================ */

const containerRef = ref(null)
const fallbackSvg = ref('')

let renderer = null
let scene = null
let camera = null
let canvasEl = null

let rafId = 0
let running = false // RAF разрешён (вьюпорт + вкладка + !paused)
let inited = false
let reducedMotion = false
let simT = 0 // время симуляции, с (нарастает только в кадре)
let lastFrame = 0
let spawnTimerA = 0.4 // таймеры спавна по направлениям
let spawnTimerB = 2.2
let mouseNX = 0 // нормализованная позиция мыши для параллакса
let mouseNY = 0
let parX = 0 // сглаженные оффсеты камеры
let parY = 0
let viewHalfW = 40 // текущие границы видимости (обновляются в resize)
let viewHalfH = 13
let spawnX = 60 // точки появления/исчезновения машин
let despawnX = 62

// Объектный пул машин: предварительно созданные группы, переиспользуются
const carPool = []
// Голова светофора (4 штуки: 2 перекрёстка × 2 направления)
const signalHeads = []
// Пешеходы (по 2 на перекрёсток)
const pedestrians = []

// Слушатели/наблюдатели — всё собирается в одном месте для чистого unmount
const cleanupFns = []
function onCleanup(fn) {
  cleanupFns.push(fn)
}

// Материалы/геометрии для полного dispose при размонтировании
const disposableGeos = []
const disposableMats = []
const disposableTex = []

// Детерминированный RNG — сцена стабильна от запуска к запуску
function mulberry32(seed) {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
const rng = mulberry32(20260814)
function rand(a, b) {
  return a + (b - a) * rng()
}

// Прямоугольник/цилиндр в список геометрий для последующего merge
// (merge на старте — одна меш-геометрия на группу объектов = мало draw calls)
function bx(list, w, h, d, x, y, z, ry) {
  const g = new BoxGeometry(w, h, d)
  if (ry) g.rotateY(ry)
  g.translate(x, y, z)
  list.push(g)
  return g
}
function cy(list, rt, rb, h, x, y, z, seg) {
  const g = new CylinderGeometry(rt, rb, h, seg || 8)
  g.translate(x, y, z)
  list.push(g)
  return g
}

// Плоский «блик»-эллипс (fake shadow) — дешёвая замена shadow map
function blob(list, rx, rz, x, z, opacity) {
  const g = new CircleGeometry(1, 20)
  g.rotateX(-Math.PI / 2)
  g.scale(rx, 1, rz)
  g.translate(x, 0.015, z)
  list.push(g)
}

const containerStyle = computed(() => ({
  height: props.height != null ? props.height + 'px' : ''
}))

/* ============================================================
   ГЕНЕРАЦИЯ СЦЕНЫ (всё создаётся один раз на старте)
   ============================================================ */

// Мягкий радиальный градент для ореолов ламп светофора (CanvasTexture — кодом)
function makeGlowTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const ctx = c.getContext('2d')
  const g = ctx.createRadialGradient(64, 64, 2, 64, 64, 62)
  g.addColorStop(0, 'rgba(255,255,255,0.9)')
  g.addColorStop(0.35, 'rgba(255,255,255,0.35)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 128, 128)
  const tex = new CanvasTexture(c)
  tex.colorSpace = 1 // SRGBColorSpace
  disposableTex.push(tex)
  return tex
}

function std(color, opts) {
  const m = new MeshStandardMaterial(
    Object.assign({ color: color }, opts || {})
  )
  disposableMats.push(m)
  return m
}
function basic(color) {
  const m = new MeshBasicMaterial({ color: color })
  disposableMats.push(m)
  return m
}
function mergedMesh(geos, material) {
  const g = mergeGeometries(geos, false)
  disposableGeos.push(g)
  geos.forEach(function (gg) {
    gg.dispose()
  })
  return new Mesh(g, material)
}

// --- Статика: земля, дорога, тротуары, бордюры, разметка, деревья, фонари ---
function buildStatic() {
  // Земля (трава) — большой прямоугольник под всем
  const groundGeo = new PlaneGeometry(380, 260)
  disposableGeos.push(groundGeo)
  const ground = new Mesh(groundGeo, std(COLORS.grass, { roughness: 1 }))
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.03
  scene.add(ground)

  // --- Асфальт (одна меш-геометрия: главная дорога + рукава боковых улиц) ---
  const asph = []
  bx(asph, ROAD_LEN * 2, 0.1, ROAD_HALF * 2, 0, -0.05, 0)
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    const segLen = SIDE_LEN - ROAD_HALF // боковая улица НАЧИНАЕТСЯ за проезжей частью
    bx(asph, SIDE_HALF * 2, 0.1, segLen, ix, -0.05, ROAD_HALF + segLen / 2)
    bx(asph, SIDE_HALF * 2, 0.1, segLen, ix, -0.05, -(ROAD_HALF + segLen / 2))
  }
  scene.add(mergedMesh(asph, std(COLORS.asphalt, { roughness: 0.95 })))

  // --- Тротуары (без наложений: сегменты главной дороги + угловые квадраты + рукава) ---
  const walk = []
  const mainSegs = [
    [-ROAD_LEN, -IX - 3],
    [-IX + 3, IX - 3],
    [IX + 3, ROAD_LEN]
  ]
  for (let s = 0; s < mainSegs.length; s++) {
    const a = mainSegs[s]
    const w = a[1] - a[0]
    bx(
      walk,
      w,
      0.12,
      WALK_OUT - WALK_IN,
      a[0] + w / 2,
      0,
      (WALK_IN + WALK_OUT) / 2
    )
    bx(
      walk,
      w,
      0.12,
      WALK_OUT - WALK_IN,
      a[0] + w / 2,
      0,
      -(WALK_IN + WALK_OUT) / 2
    )
  }
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    for (let sx = -1; sx <= 1; sx += 2) {
      for (let sz = -1; sz <= 1; sz += 2) {
        // угловые квадраты между главным тротуаром и тротуаром боковой улицы
        bx(
          walk,
          WALK_OUT - WALK_IN,
          0.12,
          WALK_OUT - WALK_IN,
          ix + sx * 4.2,
          0,
          sz * 4.7
        )
        // рукава тротуаров вдоль боковой улицы
        const segLen = SIDE_LEN - WALK_OUT
        bx(
          walk,
          WALK_OUT - WALK_IN,
          0.12,
          segLen,
          ix + sx * 4.2,
          0,
          sz * (WALK_OUT + segLen / 2)
        )
      }
    }
  }
  scene.add(mergedMesh(walk, std(COLORS.sidewalk, { roughness: 1 })))

  // --- Бордюры (тонкие светлые полосы по краям проезжей части и тротуаров) ---
  const curb = []
  for (let s = 0; s < mainSegs.length; s++) {
    const a = mainSegs[s]
    const w = a[1] - a[0]
    for (let sz = -1; sz <= 1; sz += 2) {
      bx(
        curb,
        w,
        CURB_H,
        0.16,
        a[0] + w / 2,
        CURB_H / 2,
        sz * (ROAD_HALF + 0.08)
      )
      bx(
        curb,
        w,
        CURB_H,
        0.16,
        a[0] + w / 2,
        CURB_H / 2,
        sz * (WALK_OUT - 0.08)
      )
    }
  }
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    for (let sx = -1; sx <= 1; sx += 2) {
      const segLen = SIDE_LEN - ROAD_HALF
      bx(
        curb,
        0.16,
        CURB_H,
        segLen,
        ix + sx * (SIDE_HALF + 0.08),
        CURB_H / 2,
        0
      )
      bx(curb, 0.16, CURB_H, segLen, ix + sx * (WALK_OUT - 0.08), CURB_H / 2, 0)
    }
  }
  scene.add(mergedMesh(curb, std(COLORS.curb, { roughness: 0.9 })))

  // --- Разметка (белая и жёлтая — по одной меш на цвет) ---
  const white = []
  const yellow = []
  // Жёлтый прерывистый центр (с пропусками на перекрёстках)
  for (let x = -ROAD_LEN + 3; x < ROAD_LEN - 3; x += 4.8) {
    if (Math.abs(x - IX) < 4.8 || Math.abs(x + IX) < 4.8) continue
    bx(yellow, 2.4, 0.02, 0.16, x, 0.011, 0)
  }
  // Белые сплошные края проезжей части
  for (let s = 0; s < mainSegs.length; s++) {
    const a = mainSegs[s]
    const w = a[1] - a[0]
    for (let sz = -1; sz <= 1; sz += 2) {
      bx(white, w, 0.02, 0.14, a[0] + w / 2, 0.011, sz * (ROAD_HALF - 0.35))
    }
  }
  // Стоп-линии перед каждой зеброй (только в полосе приближающегося направления)
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    bx(white, 0.5, 0.02, 3.0, ix - STOP_OFF, 0.011, LANE_Z) // для движения +X
    bx(white, 0.5, 0.02, 3.0, ix + STOP_OFF, 0.011, -LANE_Z) // для движения −X
  }
  // Зебры: продольные полосы (по ГОСТ — вдоль движения пешеходов, т.е. вдоль Z)
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    for (let k = 0; k < 6; k++) {
      bx(white, 0.5, 0.02, 6.6, ix - 1.55 + k * 0.62, 0.011, 0)
    }
  }
  // Боковые улицы: белый прерывистый центр + края (вдоль Z)
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    for (let z = -SIDE_LEN + 3; z < SIDE_LEN - 3; z += 4.8) {
      if (Math.abs(z) < 5.2) continue
      bx(white, 0.16, 0.02, 2.4, ix, 0.011, z)
    }
    const segLen = SIDE_LEN - ROAD_HALF - 1
    for (let sx = -1; sx <= 1; sx += 2) {
      for (let sz = -1; sz <= 1; sz += 2) {
        bx(
          white,
          0.14,
          0.02,
          segLen,
          ix + sx * (SIDE_HALF - 0.35),
          0.011,
          sz * (ROAD_HALF + 0.6 + segLen / 2)
        )
      }
    }
  }
  scene.add(mergedMesh(white, basic(COLORS.markWhite)))
  scene.add(mergedMesh(yellow, basic(COLORS.markYellow)))

  // --- Зелень: деревья (ствол + крона), кусты — всё merge-ом по материалам ---
  const trunks = []
  const crownsA = []
  const crownsB = []
  const bushes = []
  const staticShadows = []
  let treeCount = 0
  for (let x = -ROAD_LEN + 6; x < ROAD_LEN - 6; x += 11.5) {
    const jx = x + rand(-2.5, 2.5)
    if (Math.abs(jx - IX) < 8 || Math.abs(jx + IX) < 8) continue
    for (let sz = -1; sz <= 1; sz += 2) {
      if ((treeCount + (sz > 0 ? 0 : 1)) % 3 === 2) continue // редкая сетка, не забор
      const z = sz * (WALK_OUT + 1.6 + rand(0, 2.2))
      const r = rand(0.8, 1.2)
      cy(trunks, 0.09, 0.13, 1.2, jx, 0.6, z)
      const crown = new IcosahedronGeometry(r, 0)
      crown.scale(1, 1.25, 1)
      crown.translate(jx, 1.9 + r * 0.4, z)
      ;(rng() > 0.5 ? crownsA : crownsB).push(crown)
      blob(staticShadows, r * 1.15, r * 1.05, jx, z)
      treeCount++
    }
  }
  // Кусты по внешнему краю тротуара
  for (let x = -ROAD_LEN + 4; x < ROAD_LEN - 4; x += 9) {
    const jx = x + rand(-3, 3)
    if (Math.abs(jx - IX) < 6.5 || Math.abs(jx + IX) < 6.5) continue
    const sz = rng() > 0.5 ? 1 : -1
    const z = sz * (WALK_OUT - 0.6)
    const r = rand(0.35, 0.55)
    const bg = new IcosahedronGeometry(r, 0)
    bg.scale(1, 0.7, 1)
    bg.translate(jx, r * 0.55, z)
    bushes.push(bg)
    blob(staticShadows, r * 1.1, r * 0.9, jx, z)
  }
  scene.add(
    mergedMesh(trunks, std(COLORS.trunk, { roughness: 1, flatShading: true }))
  )
  scene.add(
    mergedMesh(
      crownsA,
      std(COLORS.crownA, { roughness: 0.9, flatShading: true })
    )
  )
  scene.add(
    mergedMesh(
      crownsB,
      std(COLORS.crownB, { roughness: 0.9, flatShading: true })
    )
  )
  scene.add(
    mergedMesh(bushes, std(COLORS.bush, { roughness: 1, flatShading: true }))
  )

  // --- Уличные фонари (столб + рука + голова; днём не горят) ---
  const lampGeos = []
  const lampXs = [-108, -84, -60, -36, -4, 28, 52, 76, 100]
  for (let i = 0; i < lampXs.length; i++) {
    const x = lampXs[i]
    if (Math.abs(x - IX) < 6.5 || Math.abs(x + IX) < 6.5) continue
    const sz = i % 2 === 0 ? 1 : -1
    const z = sz * (WALK_IN + 1.5)
    cy(lampGeos, 0.06, 0.09, 4.2, x, 2.1, z)
    bx(lampGeos, 0.07, 0.07, 1.2, x, 4.15, z - sz * 0.55)
    bx(lampGeos, 0.55, 0.12, 0.26, x, 4.1, z - sz * 1.1)
    blob(staticShadows, 0.5, 0.4, x, z)
  }
  scene.add(
    mergedMesh(lampGeos, std(COLORS.lamp, { roughness: 0.6, metalness: 0.4 }))
  )

  // --- Статические мягкие тени под деревьями/кустами/фонарями (fake shadows) ---
  const shadowMesh = mergedMesh(
    staticShadows,
    new MeshBasicMaterial({
      color: 0x1a2418,
      transparent: true,
      opacity: 0.16,
      depthWrite: false
    })
  )
  disposableMats.push(shadowMesh.material)
  scene.add(shadowMesh)
}

// --- Светофоры: 2 перекрёстка × 2 направления = 4 головы ---
function buildSignals(glowTex) {
  const poles = []
  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    for (let d = 0; d < 2; d++) {
      const dir = d === 0 ? 1 : -1 // направление, для которого сигнал
      // Столб справа от полосы приближения (правостороннее движение)
      const px = ix + (dir > 0 ? -5.2 : 5.2)
      const pz = dir > 0 ? 4.35 : -4.35
      const face = dir > 0 ? -1 : 1 // корпус смотрит к приближающимся машинам
      cy(poles, 0.06, 0.08, 2.9, px, 1.45, pz)
      bx(poles, 0.26, 1.02, 0.3, px, 3.28, pz, Math.PI / 2)

      const head = { x: px, z: pz, face: face, lamps: {}, halos: {}, last: '' }
      const lampY = { r: 3.58, y: 3.28, g: 2.98 }
      const keys = ['r', 'y', 'g']
      for (let k = 0; k < 3; k++) {
        const key = keys[k]
        const mat = basic(COLORS.pole)
        const circle = new Mesh(new CircleGeometry(0.085, 12), mat)
        circle.position.set(px + face * 0.16, lampY[key], pz)
        circle.rotation.y = face > 0 ? Math.PI / 2 : -Math.PI / 2
        scene.add(circle)
        head.lamps[key] = circle
        const haloMat = new SpriteMaterial({
          map: glowTex,
          color: LAMP_RGB[key],
          transparent: true,
          blending: AdditiveBlending,
          depthWrite: false,
          opacity: 0.85
        })
        const halo = new Sprite(haloMat)
        halo.scale.set(0.85, 0.85, 1)
        halo.position.set(px + face * 0.24, lampY[key], pz)
        halo.visible = false
        scene.add(halo)
        head.halos[key] = halo
        disposableMats.push(mat, haloMat)
        disposableGeos.push(circle.geometry)
      }
      signalHeads.push(head)
    }
  }
  scene.add(mergedMesh(poles, std(COLORS.pole, { roughness: 0.7 })))
}

// --- Пул машин: 14 готовых групп, геометрии разделяются между всеми ---
function buildCarPool() {
  const bodyGeos = []
  bx(bodyGeos, 3.6, 0.5, 1.7, 0, 0.55, 0) // кузов
  bx(bodyGeos, 0.4, 0.28, 1.72, 1.78, 0.4, 0) // передний бампер
  bx(bodyGeos, 0.4, 0.28, 1.72, -1.78, 0.4, 0) // задний бампер
  const bodyGeo = mergeGeometries(bodyGeos, false)
  disposableGeos.push(bodyGeo)
  bodyGeos.forEach(function (g) {
    g.dispose()
  })

  const cabinGeo = new BoxGeometry(1.7, 0.5, 1.5)
  cabinGeo.translate(-0.25, 1.02, 0)
  disposableGeos.push(cabinGeo)

  const wheelGeos = []
  const wg = new CylinderGeometry(0.32, 0.32, 0.24, 10)
  wg.rotateX(Math.PI / 2) // ось цилиндра — вдоль Z (ось колеса)
  disposableGeos.push(wg)
  const w1 = wg.clone()
  w1.translate(0, 0.32, 0.82)
  const w2 = wg.clone()
  w2.translate(0, 0.32, -0.82)
  disposableGeos.push(w1, w2)
  const wheelGeo = mergeGeometries([w1, w2], false)
  disposableGeos.push(wheelGeo)

  const shadowGeo = new CircleGeometry(1, 18)
  shadowGeo.rotateX(-Math.PI / 2)
  shadowGeo.scale(2.3, 1, 1.15)
  shadowGeo.translate(0, 0.02, 0)
  disposableGeos.push(shadowGeo)

  const bodyMats = []
  for (let i = 0; i < COLORS.carBody.length; i++) {
    bodyMats.push(std(COLORS.carBody[i], { roughness: 0.45, metalness: 0.15 }))
  }
  const darkMat = std(COLORS.glass, { roughness: 0.25, metalness: 0.3 })
  const wheelMat = std(COLORS.wheel, { roughness: 0.9 })
  const shadowMat = new MeshBasicMaterial({
    color: 0x0c1210,
    transparent: true,
    opacity: 0.22,
    depthWrite: false
  })
  disposableMats.push(shadowMat)

  for (let i = 0; i < MAX_CARS; i++) {
    const group = new Group()
    const body = new Mesh(bodyGeo, bodyMats[0])
    const cabin = new Mesh(cabinGeo, darkMat)
    const axleF = new Mesh(wheelGeo, wheelMat)
    const axleR = new Mesh(wheelGeo, wheelMat)
    const shadow = new Mesh(shadowGeo, shadowMat)
    axleF.position.x = 1.15
    axleR.position.x = -1.15
    group.add(body, cabin, axleF, axleR, shadow)
    group.visible = false
    scene.add(group)
    carPool.push({
      group: group,
      body: body,
      axleF: axleF,
      axleR: axleR,
      active: false,
      dir: 1,
      x: 0,
      v: 0,
      vC: 2.9 + rng() * 0.8,
      wheelSpin: 0,
      colorIdx: 0,
      bodyMats: bodyMats
    })
  }
}

// --- Пешеходы: 2 на перекрёсток (идут навстречу друг другу в «окно» all-red) ---
function buildPedestrians() {
  const bodyGeos = []
  cy(bodyGeos, 0.13, 0.17, 0.8, 0, 0.72, 0) // торс/ноги — «болванка»
  const bodyGeo = mergeGeometries(bodyGeos, false)
  disposableGeos.push(bodyGeo)
  bodyGeos.forEach(function (g) {
    g.dispose()
  })
  const headGeo = new IcosahedronGeometry(0.13, 1)
  headGeo.translate(0, 1.32, 0)
  disposableGeos.push(headGeo)
  const shadowGeo = new CircleGeometry(0.42, 12)
  shadowGeo.rotateX(-Math.PI / 2)
  shadowGeo.translate(0, 0.02, 0)
  disposableGeos.push(shadowGeo)

  const matA = std(COLORS.pedA, { roughness: 0.9, flatShading: true })
  const matB = std(COLORS.pedB, { roughness: 0.9, flatShading: true })
  const skinMat = std(COLORS.skin, { roughness: 0.9 })
  const shadowMat = new MeshBasicMaterial({
    color: 0x10160f,
    transparent: true,
    opacity: 0.2,
    depthWrite: false
  })
  disposableMats.push(shadowMat)

  for (let i = 0; i < 2; i++) {
    const ix = i === 0 ? -IX : IX
    const defs = [
      { x: ix - 1.0, mat: matA, slot: 0 }, // идёт N→S во время первого all-red
      { x: ix + 1.0, mat: matB, slot: 1 } // идёт S→N во время второго all-red
    ]
    for (let k = 0; k < defs.length; k++) {
      const d = defs[k]
      const group = new Group()
      const body = new Mesh(bodyGeo, d.mat)
      const head = new Mesh(headGeo, skinMat)
      const shadow = new Mesh(shadowGeo, shadowMat)
      group.add(body, head, shadow)
      group.position.set(d.x, 0, 4.6)
      scene.add(group)
      pedestrians.push({
        group: group,
        body: body,
        ix: ix,
        slot: d.slot,
        phase: i * 1.7 + k * 0.9
      })
    }
  }
}

/* ============================================================
   ЦИКЛ СВЕТОФОРА — конечный автомат
   ============================================================ */
// Полный цикл: [зелёная G → жёлтая Y → all-red P (пешеходы) → зелёная встречного
// направления → жёлтая → all-red]. Встречное направление получает ту же
// последовательность со сдвигом фазы на C/2, поэтому одновременно зелёными
// быть не может. Второй перекрёсток дополнительно сдвинут на C/2 — фазы
// перекрёстков рассинхронизированы (зелёная волна чередуется).
const cyc = { G: 7, Y: 2.4, P: 4, GY: 9.4, C: 26.8 } // мутируем, а не пересоздаём
function refreshCycle() {
  const G = Math.max(3, props.greenDuration)
  const Y = Math.max(1, props.yellowDuration)
  const R = Math.max(G + Y + 2, props.redDuration)
  const P = Math.min(7, Math.max(4, R - (G + Y))) // окно all-red / перехода пешеходов
  cyc.G = G
  cyc.Y = Y
  cyc.P = P
  cyc.GY = G + Y
  cyc.C = 2 * (G + Y + P)
}

function mod(n, m) {
  return ((n % m) + m) % m
}

// Состояние ('g'|'y'|'r') светофора для направления dir на перекрёстке ix
function signalState(ix, dir) {
  const ph = mod(
    simT + (ix > 0 ? cyc.C / 2 : 0) + (dir < 0 ? cyc.C / 2 : 0),
    cyc.C
  )
  if (ph < cyc.G) return 'g'
  if (ph < cyc.GY) return 'y'
  return 'r'
}

// Голова светофора обновляется ТОЛЬКО при смене состояния — в кадре работы нет
const LAMP_KEYS = ['r', 'y', 'g']
function updateSignals() {
  for (let i = 0; i < signalHeads.length; i++) {
    const h = signalHeads[i]
    const st = signalState(h.ix, h.dir)
    if (st === h.last) continue
    h.last = st
    for (let k = 0; k < 3; k++) {
      const key = LAMP_KEYS[k]
      const on = st === key
      h.lamps[key].material.color.setHex(on ? LAMP_RGB[key] : LAMP_OFF[key])
      h.halos[key].visible = on
    }
  }
}

/* ============================================================
   МАШИНЫ: спавн, кинематика, пул
   ============================================================ */

function activateCar(c, dir, x, v) {
  c.active = true
  c.dir = dir
  c.x = x
  c.v = v
  c.wheelSpin = 0
  c.colorIdx = (c.colorIdx + 1 + Math.floor(rng() * 5)) % COLORS.carBody.length
  c.body.material = c.bodyMats[c.colorIdx]
  c.group.rotation.y = dir > 0 ? 0 : Math.PI
  c.group.position.set(x, 0, dir > 0 ? LANE_Z : -LANE_Z)
  c.group.visible = true
}

function deactivateCar(c) {
  c.active = false
  c.group.visible = false
}

function firstFreeCar() {
  for (let i = 0; i < carPool.length; i++) {
    if (!carPool[i].active) return carPool[i]
  }
  return null
}

// Спавн за краем видимости с случайным интервалом; условия:
// есть свободная машина в пуле (жёсткий предел MAX_CARS) и нет соседа
// того же направления у точки спавна (не рождаемся в чужом бампере).
function trySpawn(dir, sf) {
  const c = firstFreeCar()
  if (!c) return
  const sx = dir > 0 ? -spawnX : spawnX
  for (let j = 0; j < carPool.length; j++) {
    const o = carPool[j]
    if (!o.active || o.dir !== dir) continue
    const rel = (o.x - sx) * dir
    if (rel > -2 && rel < 15) return
  }
  activateCar(c, dir, sx, c.vC * sf * 0.6)
}

// Кадровое обновление потока. Вся математика — на числовых полях пуловых
// объектов, без аллокаций: O(n²) сканирование при n ≤ 14 дешевле любой
// структуры данных, а сортировка/замыкания не нужны.
function updateCars(dt, sf) {
  // --- спавн по таймерам (интервалы модифицируются плотностью) ---
  const density = Math.min(3, Math.max(0.2, props.trafficDensity))
  spawnTimerA -= dt
  if (spawnTimerA <= 0) {
    trySpawn(1, sf)
    spawnTimerA = rand(2.8, 5.4) / density
  }
  spawnTimerB -= dt
  if (spawnTimerB <= 0) {
    trySpawn(-1, sf)
    spawnTimerB = rand(2.8, 5.4) / density
  }

  const aA = 1.5 * sf // ускорение
  const aB = 2.9 * sf // торможение

  for (let i = 0; i < carPool.length; i++) {
    const c = carPool[i]
    if (!c.active) continue

    // --- 1) торможение перед стоп-линией на красный/жёлтый ---
    let vT = c.vC * sf
    for (let k = 0; k < 2; k++) {
      const ix = k === 0 ? -IX : IX
      const sx = c.dir > 0 ? ix - STOP_OFF : ix + STOP_OFF
      const dist = (sx - (c.x + c.dir * CAR_HALF)) * c.dir // >0 — линия впереди
      if (dist <= 0 || dist > 26) continue // уже переехали / слишком далеко
      const st = signalState(ix, c.dir)
      if (st === 'g') continue
      // Жёлтая: если до линии меньше тормозного пути — проезжаем (commit zone)
      if (st === 'y' && dist < c.v * 0.55 + 1.5) continue
      const need = Math.sqrt(2 * aB * Math.max(dist - 0.05, 0))
      if (need < vT) vT = need
    }

    // --- 2) дистанция до впереди идущего: без столкновений и обгонов ---
    let aheadV = 0
    let aheadGap = 1e9
    for (let j = 0; j < carPool.length; j++) {
      const o = carPool[j]
      if (o === c || !o.active || o.dir !== c.dir) continue
      const rel = (o.x - c.x) * c.dir
      if (rel <= 0.5 || rel > 16) continue
      const gap = rel - CAR_LEN
      if (gap < aheadGap) {
        aheadGap = gap
        aheadV = o.v
      }
    }
    if (aheadGap < 1e8) {
      if (aheadGap < 0.5) {
        vT = 0
      } else {
        let f = aheadV + (aheadGap - 2.1) * 1.4 // догоняем скорость впереди
        const br = Math.sqrt(2 * aB * Math.max(aheadGap - 0.3, 0))
        if (br < f) f = br
        if (f < vT) vT = f
      }
    }

    // --- 3) кинематика: плавный разгон/торможение, интегрирование по dt ---
    const dv = vT - c.v
    if (dv > aA * dt) c.v += aA * dt
    else if (dv < -aB * dt) c.v -= aB * dt
    else c.v = vT
    if (c.v < 0.001) c.v = 0
    c.x += c.dir * c.v * dt
    c.wheelSpin += (c.v * dt) / 0.32
    c.axleF.rotation.z = -c.wheelSpin
    c.axleR.rotation.z = -c.wheelSpin
    c.group.position.x = c.x

    // --- 4) выезд за дальний край — машина возвращается в пул ---
    if (c.x * c.dir > despawnX) deactivateCar(c)
  }
}

/* ============================================================
   ПЕШЕХОДЫ: переход только в окно all-red (обе стороны красные)
   ============================================================ */
// Положение вычисляется статично из фазы цикла (без накопления состояния):
// слот 0 идёт N→S в первом окне, слот 1 — S→N во втором. Скорость подбирается
// так, чтобы успеть до конца окна (9.2 м за P секунд).
function updatePedestrians() {
  for (let i = 0; i < pedestrians.length; i++) {
    const p = pedestrians[i]
    const ph = mod(simT + (p.ix > 0 ? cyc.C / 2 : 0), cyc.C)
    const walk1 = ph >= cyc.GY && ph < cyc.GY + cyc.P
    const walk2 = ph >= cyc.C - cyc.P
    let z
    let walking = false
    if (p.slot === 0) {
      if (walk1) {
        walking = true
        const pr = (ph - cyc.GY) / cyc.P
        const e = pr * pr * (3 - 2 * pr)
        z = 4.6 - 9.2 * e
      } else {
        z = ph < cyc.GY ? 4.6 : -4.6
      }
    } else if (walk2) {
      walking = true
      const pr = (ph - (cyc.C - cyc.P)) / cyc.P
      const e = pr * pr * (3 - 2 * pr)
      z = -4.6 + 9.2 * e
    } else {
      z = ph < cyc.GY + cyc.P ? 4.6 : -4.6
    }
    p.group.position.z = z
    p.group.position.y = walking
      ? Math.abs(Math.sin(simT * 9 + p.phase)) * 0.05
      : 0
    p.group.rotation.z = walking ? Math.sin(simT * 9 + p.phase) * 0.06 : 0
  }
}

/* ============================================================
   КАМЕРА: параллакс от курсора (не мешает скроллу — canvas
   pointer-events:none, слушатель на window)
   ============================================================ */

function updateParallax(dt) {
  const k = Math.min(1, dt * 2.5)
  parX += (mouseNX * 2.4 - parX) * k
  parY += (-mouseNY * 1.1 - parY) * k
  camera.position.set(camBaseX + parX, camBaseY + parY * 0.6, camBaseZ)
  lookTarget.set(parX * 0.3, 0.4, 0)
  camera.lookAt(lookTarget)
}

// --- Единственный цикл рендера на компонент ---
function loop(nowMs) {
  rafId = 0
  if (!running) return
  rafId = requestAnimationFrame(loop)
  const now = nowMs / 1000
  let dt = now - lastFrame
  lastFrame = now
  if (dt <= 0) return
  if (dt > 0.05) dt = 0.05 // clamp: одинаковое поведение на 30/60/144 fps
  simT += dt
  const sf = Math.min(3, Math.max(0.2, props.speedFactor))
  updateSignals()
  updateCars(dt, sf)
  updatePedestrians()
  updateParallax(dt)
  renderer.render(scene, camera)
}

/* ============================================================
   ЖИЗНЕННЫЙ ЦИКЛ: инициализация, размер, паузы, очистка
   ============================================================ */

let io = null
let ro = null
let ioVisible = true
let camBaseX = 0
let camBaseY = 0
let camBaseZ = 0
const lookTarget = new Vector3(0, 0.4, 0)

function onIO(entries) {
  ioVisible = entries[0].isIntersecting
  refreshRunning()
}
function onVis() {
  refreshRunning()
}
function onMouseMove(e) {
  mouseNX = (e.clientX / window.innerWidth) * 2 - 1
  mouseNY = (e.clientY / window.innerHeight) * 2 - 1
}

// Размер canvas, frustum камеры и границы спавна — без пересоздания сцены
function applySize() {
  const el = containerRef.value
  if (!el || !renderer) return
  const w = el.clientWidth
  const h = el.clientHeight
  if (w < 2 || h < 2) return
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setSize(w, h, false)
  const aspect = w / h
  viewHalfH = Math.max(13, 42 / aspect) // узкий экран: вся дорога и оба перекрёстка в кадре
  viewHalfW = viewHalfH * aspect
  camera.left = -viewHalfW
  camera.right = viewHalfW
  camera.top = viewHalfH
  camera.bottom = -viewHalfH
  camera.updateProjectionMatrix()
  spawnX = Math.min(viewHalfW + 8, ROAD_LEN - 4)
  despawnX = Math.min(viewHalfW + 9, ROAD_LEN - 1)
  if (reducedMotion) renderer.render(scene, camera) // статичный кадр для reduced-motion
}

// Единый гейт RAF: баннер в вьюпорте + вкладка видна + нет паузы.
// Цикл стартует/останавливается, а не «пропускает кадры» — ноль GPU в простое.
function refreshRunning() {
  if (!inited) return
  const want = !reducedMotion && !props.paused && ioVisible && !document.hidden
  if (want && !running) {
    running = true
    lastFrame = performance.now() / 1000
    if (rafId === 0) rafId = requestAnimationFrame(loop)
  } else if (!want && running) {
    running = false
    if (rafId) cancelAnimationFrame(rafId)
    rafId = 0
  }
}

function init() {
  const el = containerRef.value
  if (!el) return

  // Зонд WebGL: недоступен — статичный SVG-баннер в той же палитре
  let glOK = false
  try {
    const test = document.createElement('canvas')
    glOK = !!(test.getContext('webgl2') || test.getContext('webgl'))
  } catch (e) {
    glOK = false
  }

  try {
    if (!glOK) throw new Error('WebGL unavailable')

    reducedMotion = !!(
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )

    renderer = new WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    })
    renderer.setClearColor(0x000000, 0) // прозрачный фон — CSS-градиент контейнера
    renderer.toneMapping = ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    canvasEl = renderer.domElement
    canvasEl.className = 'city-road-banner__canvas'
    el.appendChild(canvasEl)

    scene = new Scene()
    scene.fog = new Fog(0xdfe9ee, 135, 205) // боковые улицы уходят в лёгкий туман

    // Фиксированная изометрия: чуть сверху и сбоку, без orbit-контролов
    const R = 125
    camBaseX = R * Math.cos(CAM_EL) * Math.sin(CAM_AZ)
    camBaseY = R * Math.sin(CAM_EL)
    camBaseZ = R * Math.cos(CAM_EL) * Math.cos(CAM_AZ)
    camera = new OrthographicCamera(-1, 1, 1, -1, 1, 400)
    camera.position.set(camBaseX, camBaseY, camBaseZ)
    camera.lookAt(0, 0.4, 0)

    // Свет: полусферный + один направленный. Тени — только fake-эллипсы,
    // shadow map не используется (ничего не пересчитывается в кадре).
    scene.add(new HemisphereLight(0xdfefff, 0x9a8f7a, 1.05))
    const dirLight = new DirectionalLight(0xfff1dd, 1.6)
    dirLight.position.set(35, 48, 18)
    scene.add(dirLight)

    refreshCycle()
    buildStatic()
    buildSignals(makeGlowTexture())
    buildCarPool()
    buildPedestrians()

    // Стартовый состав: 6 машин равномерно по дороге, на разных фазах
    const pre = [
      [1, -62],
      [1, -38],
      [1, -8],
      [-1, 62],
      [-1, 36],
      [-1, 10]
    ]
    for (let i = 0; i < pre.length; i++) {
      const c = firstFreeCar()
      if (!c) break
      activateCar(c, pre[i][0], pre[i][1], c.vC)
    }
    updateSignals()

    // --- Наблюдатели и слушатели (всё снимается при unmount) ---
    io = new IntersectionObserver(onIO, { threshold: 0.02, rootMargin: '60px' })
    io.observe(el)
    ro = new ResizeObserver(applySize)
    ro.observe(el)
    const coarse =
      window.matchMedia && window.matchMedia('(pointer: coarse)').matches
    if (!coarse && !reducedMotion) {
      window.addEventListener('mousemove', onMouseMove, { passive: true })
      onCleanup(function () {
        window.removeEventListener('mousemove', onMouseMove)
      })
    }
    document.addEventListener('visibilitychange', onVis)
    onCleanup(function () {
      document.removeEventListener('visibilitychange', onVis)
      if (io) io.disconnect()
      if (ro) ro.disconnect()
    })

    applySize()
    inited = true
    if (reducedMotion) {
      renderer.render(scene, camera) // ровно один статичный кадр
    } else {
      refreshRunning()
    }
    emit('ready')
  } catch (err) {
    // graceful fallback: ни ошибок в консоли, ни пустого блока
    showFallback()
    emit('error', err instanceof Error ? err : new Error(String(err)))
  }
}

// Полная очистка: RAF, наблюдатели, слушатели, GPU-ресурсы, canvas
function dispose() {
  running = false
  inited = false
  if (rafId) cancelAnimationFrame(rafId)
  rafId = 0
  for (let i = 0; i < cleanupFns.length; i++) cleanupFns[i]()
  cleanupFns.length = 0
  if (renderer) {
    renderer.forceContextLoss()
    renderer.dispose()
  }
  for (let i = 0; i < disposableGeos.length; i++) disposableGeos[i].dispose()
  for (let i = 0; i < disposableMats.length; i++) disposableMats[i].dispose()
  for (let i = 0; i < disposableTex.length; i++) disposableTex[i].dispose()
  disposableGeos.length = 0
  disposableMats.length = 0
  disposableTex.length = 0
  if (canvasEl && canvasEl.parentNode) canvasEl.parentNode.removeChild(canvasEl)
  renderer = null
  scene = null
  camera = null
  canvasEl = null
}

// Конфигурация светофоров и внешняя пауза — реактивно
watch(
  function () {
    return [props.greenDuration, props.yellowDuration, props.redDuration]
  },
  function () {
    refreshCycle()
  }
)
watch(
  function () {
    return props.paused
  },
  function () {
    refreshRunning()
  }
)

onMounted(function () {
  init()
})
onBeforeUnmount(function () {
  dispose()
})

/* ============================================================
   FALLBACK: статичный SVG-баннер в той же палитре (без WebGL)
   ============================================================ */

function showFallback() {
  fallbackSvg.value = makeFallbackSvg()
}

function makeFallbackSvg() {
  const W = 800
  const H = 200
  let s =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' +
    W +
    ' ' +
    H +
    '" preserveAspectRatio="xMidYMid slice" style="width:100%;height:100%;display:block" role="img" aria-label="Городская дорога">'
  s +=
    '<defs><linearGradient id="crb-sky" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="#bcd6e8"/><stop offset="0.55" stop-color="#dfe9ee"/>' +
    '<stop offset="1" stop-color="#c9d6c2"/></linearGradient></defs>'
  s += '<rect width="800" height="200" fill="url(#crb-sky)"/>'
  s += '<rect y="128" width="800" height="72" fill="#8aa872"/>' // трава
  s +=
    '<rect y="72" width="800" height="8" fill="#c3c8cd"/><rect y="122" width="800" height="8" fill="#c3c8cd"/>' // тротуары
  s += '<rect y="80" width="800" height="42" fill="#3b4046"/>' // асфальт
  s +=
    '<rect y="81.5" width="800" height="2" fill="#f2f4f6"/><rect y="118.5" width="800" height="2" fill="#f2f4f6"/>' // края
  for (let x = 10; x < W; x += 36) {
    s += '<rect x="' + x + '" y="99" width="20" height="3" fill="#f5c542"/>' // центр жёлтый
  }
  for (let k = 0; k < 2; k++) {
    const zx = k === 0 ? 280 : 520
    for (let i = 0; i < 6; i++) {
      s +=
        '<rect x="' +
        (zx - 13 + i * 5) +
        '" y="80" width="2.6" height="42" fill="#f2f4f6"/>' // зебра
    }
    s +=
      '<rect x="' +
      (zx - 34) +
      '" y="80" width="3" height="21" fill="#f2f4f6"/>' // стоп-линия
  }
  // деревья
  const trees = [
    [40, 66],
    [150, 134],
    [230, 64],
    [350, 136],
    [470, 66],
    [610, 134],
    [700, 68],
    [770, 132]
  ]
  for (let i = 0; i < trees.length; i++) {
    s +=
      '<circle cx="' +
      trees[i][0] +
      '" cy="' +
      trees[i][1] +
      '" r="9" fill="#4e7a3a"/>' +
      '<rect x="' +
      (trees[i][0] - 1) +
      '" y="' +
      trees[i][1] +
      '" width="2" height="8" fill="#6b4f35"/>'
  }
  // машины (низняя полоса — вправо, верхняя — влево)
  const carCols = [
    '#d63031',
    '#0984e3',
    '#f4b400',
    '#00a389',
    '#6c5ce7',
    '#e17055'
  ]
  const cars = [
    [90, 104, 0],
    [180, 94, 1],
    [380, 104, 2],
    [440, 94, 3],
    [620, 104, 4],
    [700, 94, 5]
  ]
  for (let i = 0; i < cars.length; i++) {
    const cx = cars[i][0]
    const cyv = cars[i][1]
    const cc = carCols[cars[i][2]]
    s +=
      '<rect x="' +
      (cx - 17) +
      '" y="' +
      (cyv - 7) +
      '" width="34" height="14" rx="3" fill="' +
      cc +
      '"/>' +
      '<rect x="' +
      (cx - 8) +
      '" y="' +
      (cyv - 5) +
      '" width="14" height="10" rx="2" fill="#18242f"/>'
  }
  // светофоры: столб + 3 секции (одна горит)
  const sigs = [
    [248, 82, 'r', '#ff2d2d'],
    [248, 122, 'g', '#2ee66b'],
    [568, 82, 'g', '#2ee66b'],
    [568, 122, 'r', '#ff2d2d']
  ]
  for (let i = 0; i < sigs.length; i++) {
    const sx = sigs[i][0]
    const sy = sigs[i][1]
    const lit = sigs[i][2]
    s +=
      '<rect x="' +
      (sx - 1.5) +
      '" y="' +
      (sy - 26) +
      '" width="3" height="26" fill="#3a3f45"/>'
    s +=
      '<rect x="' +
      (sx - 5) +
      '" y="' +
      (sy - 40) +
      '" width="10" height="22" rx="2" fill="#2d3436"/>'
    const cols = ['#ff2d2d', '#ffd23f', '#2ee66b']
    const keys = ['r', 'y', 'g']
    for (let k = 0; k < 3; k++) {
      const on = keys[k] === lit
      s +=
        '<circle cx="' +
        sx +
        '" cy="' +
        (sy - 35 + k * 7) +
        '" r="2.6" fill="' +
        (on ? cols[k] : '#3a3f45') +
        '"/>'
    }
  }
  s += '</svg>'
  return s
}
</script>

<style scoped>
.city-road-banner {
  position: relative;
  width: 100%;
  height: 280px;
  overflow: hidden;
  /* canvas не перехватывает wheel/touch — скролл страницы работает поверх баннера */
  pointer-events: none;
  background: linear-gradient(
    180deg,
    #bcd6e8 0%,
    #dfe9ee 46%,
    #e6ece4 70%,
    #cdd8c9 100%
  );
}

.city-road-banner__canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.city-road-banner__fallback {
  position: absolute;
  inset: 0;
}

@media (max-width: 640px) {
  .city-road-banner {
    height: 180px;
  }
}
</style>
