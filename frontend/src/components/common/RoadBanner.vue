<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, shallowRef, nextTick } from 'vue'
import * as THREE from 'three'

/* ============================================================
   PROPS & EMITS
   ============================================================ */
const props = defineProps<{
  /** Высота баннера в px (адаптируется под ширину) */
  height?: number
  /** Плотность трафика 0.5–2.0 (модификатор интервалов спавна) */
  trafficDensity?: number
  /** Множитель скорости машин */
  speedFactor?: number
  /** Внешняя пауза */
  paused?: boolean
}>()

const emit = defineEmits<{
  ready: []
  error: [err: Error]
}>()

/* ============================================================
   CONSTANTS & CONFIGURATION
   ============================================================ */

// Размеры сцены (мировые единицы — метры)
const WORLD = {
  // Дорога проходит по X, камера смотрит под углом
  ROAD_WIDTH: 12, // ширина проезжей части (2 полосы по 3м + разметка)
  LANE_WIDTH: 3, // ширина одной полосы
  ROAD_LENGTH: 120, // длина видимого участка
  SIDEWALK_WIDTH: 4, // ширина тротуара с каждой стороны
  CURB_HEIGHT: 0.25, // высота бордюра
  CURB_WIDTH: 0.3, // ширина бордюра
  INTERSECTION_1_X: -30, // X первого перекрёстка
  INTERSECTION_2_X: 30, // X второго перекрёстка
  CROSSWALK_WIDTH: 3, // ширина зебры
  STOP_LINE_OFFSET: 2.5, // расстояние от стоп-линии до зебры
  SIDE_ROAD_WIDTH: 8, // ширина боковой дороги
  SIDE_ROAD_DEPTH: 40 // длина боковой дороги (уходит вглубь)
}

// Половина ширины перекрёстка (для расчёта стоп-линий)
const HALF_SIDE_ROAD = WORLD.SIDE_ROAD_WIDTH / 2

// Цвета (low-poly палитра)
const COLORS = {
  asphalt: 0x2a2d30,
  markingWhite: 0xf5f5f0,
  markingYellow: 0xffd600,
  sidewalk: 0x8a9a8a,
  curb: 0x6b736b,
  grass: 0x4a6b3a,
  grassDark: 0x3a5528,
  treeTrunk: 0x4a3728,
  treeCrown: 0x3d5d2d,
  treeCrown2: 0x4d6d3d,
  lampPost: 0x5a5a5a,
  lampHead: 0x2a2a2a,
  lightGlass: 0xfff8e7,
  lightGlow: 0xfff0b0,
  // Машины — 6 насыщенных цветов
  carColors: [
    0xe53935, // красный
    0x1e88e5, // синий
    0x43a047, // зелёный
    0xfdd835, // жёлтый
    0x8e24aa, // фиолетовый
    0xff9800 // оранжевый
  ],
  carWindow: 0x2a3a4a,
  carWheel: 0x1a1a1a,
  // Светофор
  tlBody: 0x1a1a2e,
  tlRed: 0xe53935,
  tlYellow: 0xffd600,
  tlGreen: 0x43a047,
  tlRedOff: 0x4a1a1a,
  tlYellowOff: 0x4a421a,
  tlGreenOff: 0x1a4a1a,
  // Фон
  skyTop: 0x4a5a7a,
  skyBottom: 0x7a8ab5,
  fogColor: 0x5a6a8a
}

// Фазы светофора (мс)
const TL_PHASES = [
  { state: 'green', duration: 5000 },
  { state: 'yellow', duration: 2000 },
  { state: 'red', duration: 5000 },
  { state: 'red', duration: 1000 } // пауза перед зелёным (все красные)
] as const

// Машины
const CAR = {
  LENGTH: 4.2,
  WIDTH: 1.8,
  HEIGHT: 1.4,
  WHEEL_RADIUS: 0.35,
  WHEEL_WIDTH: 0.2,
  MAX_SPEED: 12, // м/с (~43 км/ч)
  ACCEL: 2.5, // м/с²
  DECEL: 4.0, // м/с² (торможение)
  MIN_GAP: 6, // мин. дистанция до впереди идущей
  STOP_GAP: 2.5, // дистанция до стоп-линии
  SPAWN_INTERVAL_BASE: 3000, // базовый интервал спавна (мс)
  MAX_CARS: 18 // жёсткий лимит машин одновременно
}

// Камера
const CAMERA = {
  FOV: 25, // узкий FOV для изометрического ощущения
  // Ортографическая камера будет вычислена под aspect
  ORTHO_SIZE: 50, // половина высоты видимой области
  POSITION: { x: 0, y: 45, z: 25 },
  TARGET: { x: 0, y: 0, z: 0 }
}

/* ============================================================
   STATE (реактивные переменные для шаблона)
   ============================================================ */
const containerRef = ref<HTMLDivElement>()
const canvasRef = ref<HTMLCanvasElement>()
const fallbackRef = ref<HTMLDivElement>()
const webglSupported = ref(true)
const isVisible = ref(true)
const reducedMotion = ref(false)

/* ============================================================
   THREE.JS OBJECTS (non-reactive, mutable)
   ============================================================ */
let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.OrthographicCamera | null = null
let animationId: number | null = null
let clock: THREE.Clock | null = null

// Пулы объектов
const carPool: CarInstance[] = []
const activeCars: CarInstance[] = []

// Светофоры
const trafficLights: TrafficLight[] = []

// Временные векторы/объекты для переиспользования (ноль аллокаций в кадре)
const tempVec3 = new THREE.Vector3()
const tempVec2 = new THREE.Vector2()
const tempBox3 = new THREE.Box3()

// Spawn timer
let lastSpawnLeft = 0
let lastSpawnRight = 0
let nextSpawnIntervalLeft = 0
let nextSpawnIntervalRight = 0

/* ============================================================
   TYPES
   ============================================================ */
interface CarInstance {
  mesh: THREE.Group
  bodyMesh: THREE.Mesh
  wheelMeshes: THREE.Mesh[]
  lane: number // -1 = left lane (влево), +1 = right lane (вправо)
  direction: number // -1 = moving left, +1 = moving right
  x: number // мировая позиция X (центр машины)
  speed: number // текущая скорость м/с
  targetSpeed: number // целевая скорость
  color: number
  inPool: boolean
  // Для предсказания торможения
  nextStopLineX: number // X ближайшей стоп-линии
  nextTLight: TrafficLight | null
}

interface TrafficLight {
  group: THREE.Group
  lights: {
    red: THREE.Mesh
    yellow: THREE.Mesh
    green: THREE.Mesh
  }
  glowSprites: {
    red: THREE.Sprite
    yellow: THREE.Sprite
    green: THREE.Sprite
  }
  intersectionX: number
  phaseIndex: number
  phaseTimer: number
  // Позиция стоп-линий для обоих направлений
  stopLineLeft: number // для машин едущих влево (direction = -1)
  stopLineRight: number // для машин едущих вправо (direction = +1)
}

/* ============================================================
   UTILITY FUNCTIONS
   ============================================================ */

// Гладкое затухание (как THREE.MathUtils.damp)
function smoothDamp(
  current: number,
  target: number,
  lambda: number,
  dt: number
): number {
  return current + (target - current) * (1 - Math.exp(-lambda * dt))
}

// Случайное число в диапазоне
function rand(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

// Случайный элемент массива
function randChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

/* ============================================================
   GEOMETRY & MATERIAL CREATION (кодом, без ассетов)
   ============================================================ */

// Создаём геометрии один раз
const geometries = {
  road: null as THREE.PlaneGeometry | null,
  sidewalk: null as THREE.BoxGeometry | null,
  curb: null as THREE.BoxGeometry | null,
  markingLine: null as THREE.BoxGeometry | null,
  markingDash: null as THREE.BoxGeometry | null,
  crosswalkStripe: null as THREE.PlaneGeometry | null,
  stopLine: null as THREE.BoxGeometry | null,
  carBody: null as THREE.BoxGeometry | null,
  carCab: null as THREE.BoxGeometry | null,
  carWheel: null as THREE.CylinderGeometry | null,
  treeTrunk: null as THREE.CylinderGeometry | null,
  treeCrown: null as THREE.ConeGeometry | null,
  lampPost: null as THREE.CylinderGeometry | null,
  lampHead: null as THREE.BoxGeometry | null,
  lampGlass: null as THREE.BoxGeometry | null,
  tlBody: null as THREE.BoxGeometry | null,
  tlLight: null as THREE.CircleGeometry | null
}

const materials = {
  asphalt: null as THREE.MeshStandardMaterial | null,
  sidewalk: null as THREE.MeshStandardMaterial | null,
  curb: null as THREE.MeshStandardMaterial | null,
  markingWhite: null as THREE.MeshBasicMaterial | null,
  markingYellow: null as THREE.MeshBasicMaterial | null,
  crosswalk: null as THREE.MeshBasicMaterial | null,
  grass: null as THREE.MeshStandardMaterial | null,
  grassDark: null as THREE.MeshStandardMaterial | null,
  treeTrunk: null as THREE.MeshStandardMaterial | null,
  treeCrown1: null as THREE.MeshStandardMaterial | null,
  treeCrown2: null as THREE.MeshStandardMaterial | null,
  lampPost: null as THREE.MeshStandardMaterial | null,
  lampHead: null as THREE.MeshStandardMaterial | null,
  lampGlass: null as THREE.MeshStandardMaterial | null,
  tlBody: null as THREE.MeshStandardMaterial | null,
  carWindow: null as THREE.MeshStandardMaterial | null,
  carWheel: null as THREE.MeshStandardMaterial | null,
  glowSprite: null as THREE.SpriteMaterial | null
}

function createGeometries() {
  // Дорога
  geometries.road = new THREE.PlaneGeometry(WORLD.ROAD_LENGTH, WORLD.ROAD_WIDTH)
  geometries.sidewalk = new THREE.BoxGeometry(
    WORLD.ROAD_LENGTH,
    WORLD.CURB_HEIGHT,
    WORLD.SIDEWALK_WIDTH
  )
  geometries.curb = new THREE.BoxGeometry(
    WORLD.ROAD_LENGTH,
    WORLD.CURB_HEIGHT,
    WORLD.CURB_WIDTH
  )

  // Разметка
  geometries.markingLine = new THREE.BoxGeometry(WORLD.ROAD_LENGTH, 0.02, 0.15)
  geometries.markingDash = new THREE.BoxGeometry(3, 0.02, 0.15)
  geometries.crosswalkStripe = new THREE.PlaneGeometry(
    0.5,
    WORLD.ROAD_WIDTH + 1
  )
  geometries.stopLine = new THREE.BoxGeometry(0.4, 0.02, WORLD.ROAD_WIDTH + 0.5)

  // Машина
  geometries.carBody = new THREE.BoxGeometry(
    CAR.LENGTH,
    CAR.HEIGHT * 0.6,
    CAR.WIDTH
  )
  geometries.carCab = new THREE.BoxGeometry(
    CAR.LENGTH * 0.35,
    CAR.HEIGHT * 0.5,
    CAR.WIDTH * 0.85
  )
  geometries.carWheel = new THREE.CylinderGeometry(
    CAR.WHEEL_RADIUS,
    CAR.WHEEL_RADIUS,
    CAR.WHEEL_WIDTH,
    12
  )
  geometries.carWheel.rotateX(Math.PI / 2)

  // Деревья
  geometries.treeTrunk = new THREE.CylinderGeometry(0.25, 0.35, 1.8, 6)
  geometries.treeCrown = new THREE.ConeGeometry(1.8, 3.5, 6)

  // Фонари
  geometries.lampPost = new THREE.CylinderGeometry(0.12, 0.18, 6, 6)
  geometries.lampHead = new THREE.BoxGeometry(0.8, 0.4, 0.8)
  geometries.lampGlass = new THREE.BoxGeometry(0.5, 0.8, 0.5)

  // Светофор
  geometries.tlBody = new THREE.BoxGeometry(0.6, 2.8, 0.4)
  geometries.tlLight = new THREE.CircleGeometry(0.18, 12)
}

function createMaterials() {
  materials.asphalt = new THREE.MeshStandardMaterial({
    color: COLORS.asphalt,
    roughness: 0.95,
    metalness: 0.05
  })
  materials.sidewalk = new THREE.MeshStandardMaterial({
    color: COLORS.sidewalk,
    roughness: 0.9,
    metalness: 0.0
  })
  materials.curb = new THREE.MeshStandardMaterial({
    color: COLORS.curb,
    roughness: 0.85,
    metalness: 0.0
  })
  materials.markingWhite = new THREE.MeshBasicMaterial({
    color: COLORS.markingWhite
  })
  materials.markingYellow = new THREE.MeshBasicMaterial({
    color: COLORS.markingYellow
  })
  materials.crosswalk = new THREE.MeshBasicMaterial({
    color: COLORS.markingWhite,
    transparent: true,
    opacity: 0.95,
    side: THREE.DoubleSide
  })
  materials.grass = new THREE.MeshStandardMaterial({
    color: COLORS.grass,
    roughness: 0.95,
    metalness: 0.0
  })
  materials.grassDark = new THREE.MeshStandardMaterial({
    color: COLORS.grassDark,
    roughness: 0.95,
    metalness: 0.0
  })
  materials.treeTrunk = new THREE.MeshStandardMaterial({
    color: COLORS.treeTrunk,
    roughness: 0.9,
    metalness: 0.0
  })
  materials.treeCrown1 = new THREE.MeshStandardMaterial({
    color: COLORS.treeCrown,
    roughness: 0.85,
    metalness: 0.0,
    flatShading: true
  })
  materials.treeCrown2 = new THREE.MeshStandardMaterial({
    color: COLORS.treeCrown2,
    roughness: 0.85,
    metalness: 0.0,
    flatShading: true
  })
  materials.lampPost = new THREE.MeshStandardMaterial({
    color: COLORS.lampPost,
    roughness: 0.5,
    metalness: 0.7
  })
  materials.lampHead = new THREE.MeshStandardMaterial({
    color: COLORS.lampHead,
    roughness: 0.4,
    metalness: 0.8
  })
  materials.lampGlass = new THREE.MeshStandardMaterial({
    color: COLORS.lightGlass,
    emissive: COLORS.lightGlow,
    emissiveIntensity: 0.3,
    transparent: true,
    opacity: 0.6,
    roughness: 0.2,
    metalness: 0.0
  })
  materials.tlBody = new THREE.MeshStandardMaterial({
    color: COLORS.tlBody,
    roughness: 0.7,
    metalness: 0.3
  })
  materials.carWindow = new THREE.MeshStandardMaterial({
    color: COLORS.carWindow,
    roughness: 0.1,
    metalness: 0.8,
    transparent: true,
    opacity: 0.7
  })
  materials.carWheel = new THREE.MeshStandardMaterial({
    color: COLORS.carWheel,
    roughness: 0.8,
    metalness: 0.2
  })

  // Текстура свечения для спрайтов
  const glowCanvas = document.createElement('canvas')
  glowCanvas.width = 64
  glowCanvas.height = 64
  const gctx = glowCanvas.getContext('2d')!
  const grad = gctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  grad.addColorStop(0, 'rgba(255,255,255,1)')
  grad.addColorStop(0.3, 'rgba(255,255,255,0.6)')
  grad.addColorStop(1, 'rgba(255,255,255,0)')
  gctx.fillStyle = grad
  gctx.fillRect(0, 0, 64, 64)
  const glowTexture = new THREE.CanvasTexture(glowCanvas)
  glowTexture.colorSpace = THREE.SRGBColorSpace

  materials.glowSprite = new THREE.SpriteMaterial({
    map: glowTexture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    fog: false
  })
}

/* ============================================================
   SCENE BUILDING
   ============================================================ */

function buildScene() {
  if (!scene) return

  // --- Фон / небо (большая сфера/плоскость) ---
  const skyGeo = new THREE.PlaneGeometry(500, 500)
  const skyMat = new THREE.MeshBasicMaterial({
    color: COLORS.skyBottom,
    transparent: true,
    opacity: 1,
    side: THREE.DoubleSide
  })
  // Градиент неба через вертексные цвета не сделаем просто,
  // используем два полупрозрачных слоя
  const sky = new THREE.Mesh(skyGeo, skyMat)
  sky.position.set(0, 15, -100)
  sky.rotation.x = -Math.PI / 2
  scene.add(sky)

  // --- Травяные участки (за тротуарами) ---
  const grassWidth = 60
  const grassGeo = new THREE.PlaneGeometry(WORLD.ROAD_LENGTH, grassWidth)

  const grassLeft = new THREE.Mesh(grassGeo, materials.grass!)
  grassLeft.rotation.x = -Math.PI / 2
  grassLeft.position.set(0, 0.01, -WORLD.SIDEWALK_WIDTH / 2 - grassWidth / 2)
  scene.add(grassLeft)

  const grassRight = new THREE.Mesh(grassGeo, materials.grassDark!)
  grassRight.rotation.x = -Math.PI / 2
  grassRight.position.set(0, 0.01, WORLD.SIDEWALK_WIDTH / 2 + grassWidth / 2)
  scene.add(grassRight)

  // --- Тротуары ---
  const sidewalkY = WORLD.CURB_HEIGHT / 2
  const sidewalkZ =
    WORLD.ROAD_WIDTH / 2 + WORLD.SIDEWALK_WIDTH / 2 + WORLD.CURB_WIDTH

  const sidewalkLeft = new THREE.Mesh(geometries.sidewalk!, materials.sidewalk!)
  sidewalkLeft.position.set(0, sidewalkY, -sidewalkZ)
  sidewalkLeft.receiveShadow = true
  scene.add(sidewalkLeft)

  const sidewalkRight = new THREE.Mesh(
    geometries.sidewalk!,
    materials.sidewalk!
  )
  sidewalkRight.position.set(0, sidewalkY, sidewalkZ)
  sidewalkRight.receiveShadow = true
  scene.add(sidewalkRight)

  // --- Бордюры ---
  const curbZ = WORLD.ROAD_WIDTH / 2 + WORLD.CURB_WIDTH / 2

  const curbLeft = new THREE.Mesh(geometries.curb!, materials.curb!)
  curbLeft.position.set(0, sidewalkY, -curbZ)
  curbLeft.castShadow = true
  curbLeft.receiveShadow = true
  scene.add(curbLeft)

  const curbRight = new THREE.Mesh(geometries.curb!, materials.curb!)
  curbRight.position.set(0, sidewalkY, curbZ)
  curbRight.castShadow = true
  curbRight.receiveShadow = true
  scene.add(curbRight)

  // --- Дорога ---
  const road = new THREE.Mesh(geometries.road!, materials.asphalt!)
  road.rotation.x = -Math.PI / 2
  road.position.y = 0.02
  road.receiveShadow = true
  scene.add(road)

  // --- Разметка главной дороги ---
  // Сплошные края полос (жёлтые по бокам, белые по центру)
  const laneEdgeZ = WORLD.LANE_WIDTH / 2

  // Центр — прерывистая белая
  for (let x = -WORLD.ROAD_LENGTH / 2; x < WORLD.ROAD_LENGTH / 2; x += 6) {
    // Пропускаем зоны перекрёстков
    if (isInIntersectionZone(x)) continue

    const dash = new THREE.Mesh(
      geometries.markingDash!,
      materials.markingWhite!
    )
    dash.position.set(x, 0.03, 0)
    dash.receiveShadow = true
    scene.add(dash)
  }

  // Края полос — сплошные жёлтые (внешние) и белые (внутренние между полосами)
  const markingPositions = [
    { z: -WORLD.ROAD_WIDTH / 2, color: materials.markingYellow!, solid: true }, // левый край
    { z: -laneEdgeZ, color: materials.markingWhite!, solid: true }, // между полосами
    { z: laneEdgeZ, color: materials.markingWhite!, solid: true }, // между полосами
    { z: WORLD.ROAD_WIDTH / 2, color: materials.markingYellow!, solid: true } // правый край
  ]

  markingPositions.forEach(({ z, color, solid }) => {
    const geo = solid ? geometries.markingLine! : geometries.markingDash!
    const line = new THREE.Mesh(geo, color)
    line.position.set(0, 0.03, z)
    line.receiveShadow = true
    scene.add(line)
  })

  // --- Перекрёстки ---
  buildIntersection(WORLD.INTERSECTION_1_X, 0) // фаза 0
  buildIntersection(WORLD.INTERSECTION_2_X, 2) // фаза 2 (сдвиг на красный+паузу)

  // --- Деревья и фонари по тротуарам ---
  placeStreetObjects()
}

function isInIntersectionZone(x: number): boolean {
  const halfSide = WORLD.SIDE_ROAD_WIDTH / 2 + WORLD.CROSSWALK_WIDTH
  return (
    (x > WORLD.INTERSECTION_1_X - halfSide &&
      x < WORLD.INTERSECTION_1_X + halfSide) ||
    (x > WORLD.INTERSECTION_2_X - halfSide &&
      x < WORLD.INTERSECTION_2_X + halfSide)
  )
}

function buildIntersection(centerX: number, initialPhaseIndex: number) {
  if (!scene) return

  const crosswalkZ = WORLD.ROAD_WIDTH / 2 + WORLD.CURB_WIDTH + 0.5

  // Боковые дороги (уходят вглубь по Z)
  // Левая боковая (Z < 0)
  const sideRoadLeft = new THREE.Mesh(
    new THREE.PlaneGeometry(WORLD.SIDE_ROAD_WIDTH, WORLD.SIDE_ROAD_DEPTH),
    materials.asphalt!
  )
  sideRoadLeft.rotation.x = -Math.PI / 2
  sideRoadLeft.position.set(
    centerX,
    0.02,
    -crosswalkZ - WORLD.SIDE_ROAD_DEPTH / 2
  )
  sideRoadLeft.receiveShadow = true
  scene.add(sideRoadLeft)

  // Правая боковая
  const sideRoadRight = new THREE.Mesh(
    new THREE.PlaneGeometry(WORLD.SIDE_ROAD_WIDTH, WORLD.SIDE_ROAD_DEPTH),
    materials.asphalt!
  )
  sideRoadRight.rotation.x = -Math.PI / 2
  sideRoadRight.position.set(
    centerX,
    0.02,
    crosswalkZ + WORLD.SIDE_ROAD_DEPTH / 2
  )
  sideRoadRight.receiveShadow = true
  scene.add(sideRoadRight)

  // Зебры через главную дорогу (перпендикулярно X)
  for (let i = 0; i < 8; i++) {
    const stripe = new THREE.Mesh(
      geometries.crosswalkStripe!,
      materials.crosswalk!
    )
    stripe.rotation.x = -Math.PI / 2
    stripe.position.set(
      centerX - HALF_SIDE_ROAD + i * (WORLD.SIDE_ROAD_WIDTH / 8),
      0.04,
      0
    )
    stripe.receiveShadow = true
    scene.add(stripe)
  }

  // Стоп-линии
  // Для машин едущих вправо (direction = +1) — перед левой зеброй
  const stopLineRight = new THREE.Mesh(
    geometries.stopLine!,
    materials.markingWhite!
  )
  stopLineRight.position.set(
    centerX - HALF_SIDE_ROAD - WORLD.STOP_LINE_OFFSET,
    0.035,
    0
  )
  stopLineRight.receiveShadow = true
  scene.add(stopLineRight)

  // Для машин едущих влево (direction = -1) — перед правой зеброй
  const stopLineLeft = new THREE.Mesh(
    geometries.stopLine!,
    materials.markingWhite!
  )
  stopLineLeft.position.set(
    centerX + HALF_SIDE_ROAD + WORLD.STOP_LINE_OFFSET,
    0.035,
    0
  )
  stopLineLeft.receiveShadow = true
  scene.add(stopLineLeft)

  // Светофоры — на стойках по углам перекрёстка (4 светофора на перекрёсток)
  // Но по ТЗ: "светофоры на стойках для обоих направлений движения" — делаем по 2 на перекрёсток
  // Один слева (для трафика вправо), один справа (для трафика влево)

  // Левый светофор (контролирует трафик direction=+1)
  const tlLeft = createTrafficLight(
    centerX - HALF_SIDE_ROAD - WORLD.STOP_LINE_OFFSET - 2.5, // X позиции
    -crosswalkZ - 2.5, // Z (левый тротуар)
    initialPhaseIndex
  )
  tlLeft.stopLineLeft = centerX + HALF_SIDE_ROAD + WORLD.STOP_LINE_OFFSET
  tlLeft.stopLineRight = centerX - HALF_SIDE_ROAD - WORLD.STOP_LINE_OFFSET
  trafficLights.push(tlLeft)
  scene.add(tlLeft.group)

  // Правый светофор (контролирует трафик direction=-1)
  const tlRight = createTrafficLight(
    centerX + HALF_SIDE_ROAD + WORLD.STOP_LINE_OFFSET + 2.5,
    crosswalkZ + 2.5,
    (initialPhaseIndex + 2) % TL_PHASES.length // противоположная фаза
  )
  tlRight.stopLineLeft = centerX + HALF_SIDE_ROAD + WORLD.STOP_LINE_OFFSET
  tlRight.stopLineRight = centerX - HALF_SIDE_ROAD - WORLD.STOP_LINE_OFFSET
  trafficLights.push(tlRight)
  scene.add(tlRight.group)
}

function createTrafficLight(
  x: number,
  z: number,
  initialPhaseIndex: number
): TrafficLight {
  const group = new THREE.Group()

  // Стойка
  const pole = new THREE.Mesh(
    new THREE.CylinderGeometry(0.1, 0.14, 3.5, 8),
    materials.tlBody!
  )
  pole.position.set(0, 1.75, 0)
  pole.castShadow = true
  group.add(pole)

  // Корпус
  const body = new THREE.Mesh(geometries.tlBody!, materials.tlBody!)
  body.position.set(0, 3.5 + 1.4, 0)
  body.castShadow = true
  group.add(body)

  // Три секции
  const lightPositions = [
    { y: 3.5 + 2.1, color: COLORS.tlRed, colorOff: COLORS.tlRedOff },
    { y: 3.5 + 0.0, color: COLORS.tlYellow, colorOff: COLORS.tlYellowOff },
    { y: 3.5 - 2.1, color: COLORS.tlGreen, colorOff: COLORS.tlGreenOff }
  ]

  const lights: TrafficLight['lights'] = {
    red: null!,
    yellow: null!,
    green: null!
  }
  const glowSprites: TrafficLight['glowSprites'] = {
    red: null!,
    yellow: null!,
    green: null!
  }

  lightPositions.forEach((lp, i) => {
    const key = ['red', 'yellow', 'green'][i] as keyof TrafficLight['lights']

    // Линза
    const lightMat = new THREE.MeshStandardMaterial({
      color: lp.colorOff,
      emissive: lp.color,
      emissiveIntensity: 0,
      roughness: 0.3,
      metalness: 0.0
    })
    const lightMesh = new THREE.Mesh(geometries.tlLight!, lightMat)
    lightMesh.position.set(0, lp.y, 0.22)
    lightMesh.rotation.x = -Math.PI / 2
    group.add(lightMesh)
    lights[key] = lightMesh

    // Свечение (Sprite)
    const glowMat = materials.glowSprite!.clone()
    glowMat.color.set(lp.color)
    glowMat.opacity = 0
    const glow = new THREE.Sprite(glowMat)
    glow.position.set(0, lp.y, 0.35)
    glow.scale.set(0.6, 0.6, 1)
    group.add(glow)
    glowSprites[key] = glow
  })

  group.position.set(x, 0, z)

  return {
    group,
    lights,
    glowSprites,
    intersectionX: x,
    phaseIndex: initialPhaseIndex,
    phaseTimer: 0,
    stopLineLeft: 0,
    stopLineRight: 0
  }
}

function placeStreetObjects() {
  if (!scene) return

  // Позиции по Z (левый и правый тротуары)
  const sidewalkZ =
    WORLD.ROAD_WIDTH / 2 + WORLD.SIDEWALK_WIDTH / 2 + WORLD.CURB_WIDTH + 1.5

  // Деревья и фонари по бокам дороги
  const spacing = 12
  const startX = -WORLD.ROAD_LENGTH / 2 + 10
  const endX = WORLD.ROAD_LENGTH / 2 - 10

  for (let x = startX; x < endX; x += spacing) {
    // Пропускаем зоны перекрёстков
    if (isInIntersectionZone(x)) continue

    // Случайный выбор: дерево или фонарь
    if (Math.random() < 0.6) {
      // Дерево (слева)
      addTree(x + rand(-1.5, 1.5), -sidewalkZ - rand(0, 2))
      // Дерево (справа)
      addTree(x + rand(-1.5, 1.5), sidewalkZ + rand(0, 2))
    } else {
      // Фонарь (слева)
      addLampPost(x, -sidewalkZ - 1)
      // Фонарь (справа)
      addLampPost(x, sidewalkZ + 1)
    }
  }
}

function addTree(x: number, z: number) {
  if (!scene) return
  const group = new THREE.Group()

  const trunk = new THREE.Mesh(geometries.treeTrunk!, materials.treeTrunk!)
  trunk.position.y = 0.9
  trunk.castShadow = true
  group.add(trunk)

  const crown1 = new THREE.Mesh(geometries.treeCrown!, materials.treeCrown1!)
  crown1.position.y = 2.8
  crown1.castShadow = true
  group.add(crown1)

  const crown2 = new THREE.Mesh(geometries.treeCrown!, materials.treeCrown2!)
  crown2.position.y = 4.8
  crown2.scale.setScalar(0.7)
  crown2.castShadow = true
  group.add(crown2)

  group.position.set(x, 0, z)
  scene.add(group)
}

function addLampPost(x: number, z: number) {
  if (!scene) return
  const group = new THREE.Group()

  const pole = new THREE.Mesh(geometries.lampPost!, materials.lampPost!)
  pole.position.y = 3
  pole.castShadow = true
  group.add(pole)

  const head = new THREE.Mesh(geometries.lampHead!, materials.lampHead!)
  head.position.set(0, 6.2, 0)
  head.castShadow = true
  group.add(head)

  const glass = new THREE.Mesh(geometries.lampGlass!, materials.lampGlass!)
  glass.position.set(0, 5.8, 0)
  group.add(glass)

  // Точечный свет внизу фонаря
  const light = new THREE.PointLight(0xfff8e7, 8, 15, 2)
  light.position.set(0, 5.5, 0)
  group.add(light)

  group.position.set(x, 0, z)
  scene.add(group)
}

/* ============================================================
   CAR POOL & SPAWNING
   ============================================================ */

function createCarPool() {
  for (let i = 0; i < CAR.MAX_CARS; i++) {
    const car = createCarInstance()
    car.inPool = true
    carPool.push(car)
  }
}

function createCarInstance(): CarInstance {
  const group = new THREE.Group()
  const color = randChoice(COLORS.carColors)

  // Кузов
  const bodyMat = new THREE.MeshStandardMaterial({
    color,
    roughness: 0.4,
    metalness: 0.6
  })
  const body = new THREE.Mesh(geometries.carBody!, bodyMat)
  body.position.y = CAR.HEIGHT / 2
  body.castShadow = true
  body.receiveShadow = true
  group.add(body)

  // Кабина
  const cab = new THREE.Mesh(geometries.carCab!, materials.carWindow!)
  cab.position.set(0, CAR.HEIGHT * 0.7, 0)
  cab.castShadow = true
  group.add(cab)

  // Колёса
  const wheels: THREE.Mesh[] = []
  const wheelOffsets = [
    [-CAR.LENGTH / 2 + 0.5, -CAR.WIDTH / 2 - 0.05],
    [-CAR.LENGTH / 2 + 0.5, CAR.WIDTH / 2 + 0.05],
    [CAR.LENGTH / 2 - 0.5, -CAR.WIDTH / 2 - 0.05],
    [CAR.LENGTH / 2 - 0.5, CAR.WIDTH / 2 + 0.05]
  ]

  wheelOffsets.forEach(([wx, wz]) => {
    const wheel = new THREE.Mesh(geometries.carWheel!, materials.carWheel!)
    wheel.position.set(wx, CAR.WHEEL_RADIUS, wz)
    wheel.castShadow = true
    wheel.receiveShadow = true
    group.add(wheel)
    wheels.push(wheel)
  })

  // Фары (передние) и задние фонари — просто эмиссивные плоскости
  const lightMat = new THREE.MeshBasicMaterial({
    color: 0xffffee,
    transparent: true,
    opacity: 0.9
  })
  const rearLightMat = new THREE.MeshBasicMaterial({
    color: 0xff3333,
    transparent: true,
    opacity: 0.9
  })

  const frontLightGeo = new THREE.PlaneGeometry(0.3, 0.15)
  const frontLight1 = new THREE.Mesh(frontLightGeo, lightMat)
  frontLight1.position.set(
    CAR.LENGTH / 2 + 0.01,
    CAR.HEIGHT * 0.35,
    CAR.WIDTH / 2 - 0.2
  )
  frontLight1.rotation.y = -Math.PI / 2
  group.add(frontLight1)

  const frontLight2 = new THREE.Mesh(frontLightGeo, lightMat)
  frontLight2.position.set(
    CAR.LENGTH / 2 + 0.01,
    CAR.HEIGHT * 0.35,
    -CAR.WIDTH / 2 + 0.2
  )
  frontLight2.rotation.y = -Math.PI / 2
  group.add(frontLight2)

  const rearLightGeo = new THREE.PlaneGeometry(0.3, 0.15)
  const rearLight1 = new THREE.Mesh(rearLightGeo, rearLightMat)
  rearLight1.position.set(
    -CAR.LENGTH / 2 - 0.01,
    CAR.HEIGHT * 0.35,
    CAR.WIDTH / 2 - 0.2
  )
  rearLight1.rotation.y = Math.PI / 2
  group.add(rearLight1)

  const rearLight2 = new THREE.Mesh(rearLightGeo, rearLightMat)
  rearLight2.position.set(
    -CAR.LENGTH / 2 - 0.01,
    CAR.HEIGHT * 0.35,
    -CAR.WIDTH / 2 + 0.2
  )
  rearLight2.rotation.y = Math.PI / 2
  group.add(rearLight2)

  return {
    mesh: group,
    bodyMesh: body,
    wheelMeshes: wheels,
    lane: 0,
    direction: 0,
    x: 0,
    speed: 0,
    targetSpeed: 0,
    color,
    inPool: true,
    nextStopLineX: 0,
    nextTLight: null
  }
}

function getCarFromPool(): CarInstance | null {
  const car = carPool.find(c => c.inPool)
  if (!car) return null
  car.inPool = false
  return car
}

function returnCarToPool(car: CarInstance) {
  if (!scene) return
  car.inPool = true
  car.mesh.visible = false
  // Удаляем из активных
  const idx = activeCars.indexOf(car)
  if (idx >= 0) activeCars.splice(idx, 1)
  // Сброс состояния
  car.speed = 0
  car.targetSpeed = 0
  car.nextTLight = null
}

function spawnCar(direction: number) {
  const car = getCarFromPool()
  if (!car || !scene) return null

  // Настройка машины
  car.direction = direction
  car.lane = direction > 0 ? 1 : -1 // правая полоса для направления
  car.color = randChoice(COLORS.carColors)
  car.bodyMesh.material.color.set(car.color)
  car.speed = 0
  car.targetSpeed = CAR.MAX_SPEED * (props.speedFactor || 1)
  car.nextStopLineX =
    direction > 0
      ? WORLD.INTERSECTION_1_X - HALF_SIDE_ROAD - WORLD.STOP_LINE_OFFSET
      : WORLD.INTERSECTION_2_X + HALF_SIDE_ROAD + WORLD.STOP_LINE_OFFSET

  // Найти ближайший светофор для этого направления
  car.nextTLight = findNextTrafficLight(car.x, direction)

  // Позиция спавна за краем мира
  const spawnX =
    direction > 0 ? -WORLD.ROAD_LENGTH / 2 - 5 : WORLD.ROAD_LENGTH / 2 + 5
  car.x = spawnX

  // Z позиция в полосе
  const laneZ = (car.lane * WORLD.LANE_WIDTH) / 2
  car.mesh.position.set(car.x, 0, laneZ)

  // Поворот машины по направлению
  car.mesh.rotation.y = direction > 0 ? 0 : Math.PI

  car.mesh.visible = true
  scene.add(car.mesh)
  activeCars.push(car)

  return car
}

function findNextTrafficLight(
  x: number,
  direction: number
): TrafficLight | null {
  let closest: TrafficLight | null = null
  let closestDist = Infinity

  for (const tl of trafficLights) {
    const stopLine = direction > 0 ? tl.stopLineRight : tl.stopLineLeft
    const dist = direction > 0 ? stopLine - x : x - stopLine
    if (dist > 0 && dist < closestDist) {
      closestDist = dist
      closest = tl
    }
  }
  return closest
}

function updateCarPoolSpawn(dt: number, time: number) {
  const density = props.trafficDensity || 1
  const spawnInterval = CAR.SPAWN_INTERVAL_BASE / density

  // Спавн слева (direction = +1, едут вправо)
  lastSpawnLeft += dt * 1000
  if (lastSpawnLeft >= nextSpawnIntervalLeft) {
    lastSpawnLeft = 0
    nextSpawnIntervalLeft = spawnInterval * rand(0.5, 1.5)
    spawnCar(1)
  }

  // Спавн справа (direction = -1, едут влево)
  lastSpawnRight += dt * 1000
  if (lastSpawnRight >= nextSpawnIntervalRight) {
    lastSpawnRight = 0
    nextSpawnIntervalRight = spawnInterval * rand(0.5, 1.5)
    spawnCar(-1)
  }
}

/* ============================================================
   TRAFFIC LIGHT LOGIC
   ============================================================ */

function updateTrafficLights(dt: number) {
  for (const tl of trafficLights) {
    tl.phaseTimer += dt * 1000
    const phase = TL_PHASES[tl.phaseIndex]

    if (tl.phaseTimer >= phase.duration) {
      tl.phaseTimer = 0
      tl.phaseIndex = (tl.phaseIndex + 1) % TL_PHASES.length
    }

    // Обновляем визуал
    const targetPhase = TL_PHASES[tl.phaseIndex].state
    setTrafficLightVisual(tl, targetPhase)
  }
}

function setTrafficLightVisual(
  tl: TrafficLight,
  activeState: 'red' | 'yellow' | 'green'
) {
  const states = ['red', 'yellow', 'green'] as const
  states.forEach(state => {
    const isActive = state === activeState
    const light = tl.lights[state]
    const glow = tl.glowSprites[state]

    if (isActive) {
      light.material.emissiveIntensity = 3.0
      light.material.color.set(light.material.emissive)
      glow.material.opacity = 0.9
      glow.scale.setScalar(1.2 + Math.sin(performance.now() * 0.003) * 0.1)
    } else {
      light.material.emissiveIntensity = 0
      light.material.color.set(
        state === 'red'
          ? COLORS.tlRedOff
          : state === 'yellow'
            ? COLORS.tlYellowOff
            : COLORS.tlGreenOff
      )
      glow.material.opacity = 0
      glow.scale.setScalar(0.8)
    }
  })
}

function getTrafficLightStateForDirection(
  tl: TrafficLight,
  direction: number
): 'red' | 'yellow' | 'green' {
  // Оба светофора на перекрёстке синхронизированы
  // Для direction > 0 (вправо) — смотрим правый светофор (stopLineRight)
  // Для direction < 0 (влево) — смотрим левый светофор (stopLineLeft)
  // Но так как фазы сдвинуты, просто возвращаем состояние фазы
  return TL_PHASES[tl.phaseIndex].state
}

/* ============================================================
   CAR PHYSICS & MOVEMENT
   ============================================================ */

function updateCars(dt: number) {
  const accel = CAR.ACCEL * (props.speedFactor || 1)
  const decel = CAR.DECEL * (props.speedFactor || 1)
  const maxSpeed = CAR.MAX_SPEED * (props.speedFactor || 1)

  // Сортируем активные машины по X для корректного следования
  activeCars.sort((a, b) => a.direction * a.x - b.direction * b.x)

  for (let i = 0; i < activeCars.length; i++) {
    const car = activeCars[i]
    const dir = car.direction

    // Находим впереди идущую машину в той же полосе и направлении
    let frontCar: CarInstance | null = null
    let minDist = Infinity

    for (let j = 0; j < activeCars.length; j++) {
      if (j === i) continue
      const other = activeCars[j]
      if (other.direction !== dir) continue
      if (other.lane !== car.lane) continue

      const dist = dir > 0 ? other.x - car.x : car.x - other.x
      if (dist > 0 && dist < minDist) {
        minDist = dist
        frontCar = other
      }
    }

    // Определяем целевую скорость
    let targetSpeed = maxSpeed

    // Проверка светофора
    if (car.nextTLight) {
      const tl = car.nextTLight
      const stopLine = dir > 0 ? tl.stopLineRight : tl.stopLineLeft
      const distToStopLine = dir > 0 ? stopLine - car.x : car.x - stopLine

      car.nextStopLineX = stopLine

      const tlState = getTrafficLightStateForDirection(tl, dir)

      if ((tlState === 'red' || tlState === 'yellow') && distToStopLine < 30) {
        // Нужно тормозить к стоп-линии
        if (distToStopLine > CAR.STOP_GAP) {
          // Плавное торможение
          const requiredSpeed = Math.sqrt(
            Math.max(0, 2 * decel * (distToStopLine - CAR.STOP_GAP))
          )
          targetSpeed = Math.min(targetSpeed, Math.max(0, requiredSpeed))
        } else {
          targetSpeed = 0
        }
      } else if (distToStopLine <= 0) {
        // Проехали стоп-линию — ищем следующий светофор
        car.nextTLight = findNextTrafficLight(car.x + dir * 5, dir)
      }
    }

    // Проверка дистанции до впереди идущей
    if (frontCar) {
      const safeDist = CAR.MIN_GAP + frontCar.speed * 0.5
      if (minDist < safeDist) {
        // Тормозим до скорости впереди идущей
        targetSpeed = Math.min(targetSpeed, frontCar.speed * 0.95)
      }
    }

    car.targetSpeed = targetSpeed

    // Плавное изменение скорости
    if (car.speed < car.targetSpeed) {
      car.speed = Math.min(car.targetSpeed, car.speed + accel * dt)
    } else if (car.speed > car.targetSpeed) {
      car.speed = Math.max(car.targetSpeed, car.speed - decel * dt)
    }

    // Движение
    car.x += car.speed * dt * dir

    // Обновляем позицию меша
    car.mesh.position.x = car.x

    // Анимация колёс
    const wheelRotation = car.speed * dt * 10
    car.wheelMeshes.forEach(w => (w.rotation.x += wheelRotation))

    // Проверка выхода за границы мира
    const worldLimit = WORLD.ROAD_LENGTH / 2 + 10
    if ((dir > 0 && car.x > worldLimit) || (dir < 0 && car.x < -worldLimit)) {
      returnCarToPool(car)
    }
  }
}

/* ============================================================
   INITIALIZATION
   ============================================================ */

function checkWebGLSupport(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(window.WebGLRenderingContext && canvas.getContext('webgl'))
  } catch {
    return false
  }
}

function initThree() {
  if (!containerRef.value || !canvasRef.value) return

  if (!checkWebGLSupport()) {
    webglSupported.value = false
    showFallback()
    return
  }

  const container = containerRef.value
  const canvas = canvasRef.value
  const width = container.clientWidth
  const height = props.height || 280

  // Renderer
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  renderer.autoClear = true

  // Scene
  scene = new THREE.Scene()
  scene.fog = new THREE.Fog(COLORS.fogColor, 60, 140)
  scene.background = null // прозрачный фон

  // Camera — ортографическая для изометрического вида
  const aspect = width / height
  const frustumSize = CAMERA.ORTHO_SIZE
  camera = new THREE.OrthographicCamera(
    (-frustumSize * aspect) / 2,
    (frustumSize * aspect) / 2,
    frustumSize / 2,
    -frustumSize / 2,
    1,
    200
  )
  camera.position.set(CAMERA.POSITION.x, CAMERA.POSITION.y, CAMERA.POSITION.z)
  camera.lookAt(CAMERA.TARGET.x, CAMERA.TARGET.y, CAMERA.TARGET.z)

  // Lights
  scene.add(new THREE.HemisphereLight(COLORS.skyTop, COLORS.skyBottom, 1.2))

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5)
  dirLight.position.set(30, 60, 20)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.set(1024, 1024)
  dirLight.shadow.camera.near = 10
  dirLight.shadow.camera.far = 120
  dirLight.shadow.camera.left = -60
  dirLight.shadow.camera.right = 60
  dirLight.shadow.camera.top = 60
  dirLight.shadow.camera.bottom = -40
  dirLight.shadow.bias = -0.001
  dirLight.shadow.normalBias = 0.05
  scene.add(dirLight)

  // Построение сцены
  createGeometries()
  createMaterials()
  buildScene()
  createCarPool()

  clock = new THREE.Clock()
  clock.start()

  emit('ready', [])

  // ResizeObserver
  const resizeObserver = new ResizeObserver(() => onResize())
  resizeObserver.observe(container)
  ;(container as any).__resizeObserver = resizeObserver

  // Visibility pause
  const handleVisibility = () => {
    if (document.hidden) {
      if (animationId) {
        cancelAnimationFrame(animationId)
        animationId = null
      }
    } else {
      if (!animationId && clock) {
        clock.start()
        animate()
      }
    }
  }
  document.addEventListener('visibilitychange', handleVisibility)
  ;(container as any).__visibilityHandler = handleVisibility

  // Начинаем анимацию
  animate()
}

function showFallback() {
  if (fallbackRef.value) {
    fallbackRef.value.style.display = 'block'
  }
  if (canvasRef.value) {
    canvasRef.value.style.display = 'none'
  }
}

function onResize() {
  if (!renderer || !camera || !containerRef.value) return

  const container = containerRef.value
  const width = container.clientWidth
  const height = props.height || 280

  renderer.setSize(width, height)

  const aspect = width / height
  const frustumSize = CAMERA.ORTHO_SIZE

  camera.left = (-frustumSize * aspect) / 2
  camera.right = (frustumSize * aspect) / 2
  camera.top = frustumSize / 2
  camera.bottom = -frustumSize / 2
  camera.updateProjectionMatrix()
}

function animate() {
  if (!renderer || !scene || !camera || !clock) return

  if (props.paused || reducedMotion.value || !isVisible.value) {
    animationId = requestAnimationFrame(animate)
    return
  }

  const dt = Math.min(clock.getDelta(), 0.1) // clamp delta
  const time = clock.getElapsedTime()

  updateTrafficLights(dt)
  updateCarPoolSpawn(dt, time)
  updateCars(dt)

  renderer.render(scene, camera)

  animationId = requestAnimationFrame(animate)
}

/* ============================================================
   INTERSECTION OBSERVER (пауза вне вьюпорта)
   ============================================================ */

function setupIntersectionObserver() {
  if (!containerRef.value) return

  const observer = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        isVisible.value = entry.isIntersecting
        if (entry.isIntersecting && clock && !animationId) {
          clock.start()
          animate()
        }
      })
    },
    {
      rootMargin: '100px', // начнёт рендерить заранее
      threshold: 0.01
    }
  )

  observer.observe(containerRef.value)
  ;(containerRef.value as any).__intersectionObserver = observer
}

/* ============================================================
   PREFERS-REDUCED-MOTION
   ============================================================ */

function setupReducedMotion() {
  const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = mediaQuery.matches

  const handler = (e: MediaQueryListEvent) => {
    reducedMotion.value = e.matches
  }
  mediaQuery.addEventListener?.('change', handler)
  ;(containerRef.value as any).__reducedMotionHandler = handler
}

/* ============================================================
   CLEANUP
   ============================================================ */

function cleanup() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }

  if (containerRef.value) {
    const container = containerRef.value

    const resizeObserver = (container as any).__resizeObserver
    if (resizeObserver) resizeObserver.disconnect()

    const visibilityHandler = (container as any).__visibilityHandler
    if (visibilityHandler)
      document.removeEventListener('visibilitychange', visibilityHandler)

    const intersectionObserver = (container as any).__intersectionObserver
    if (intersectionObserver) intersectionObserver.disconnect()

    const reducedMotionHandler = (container as any).__reducedMotionHandler
    if (reducedMotionHandler) {
      const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
      mq.removeEventListener?.('change', reducedMotionHandler)
    }
  }

  // Three.js disposal
  if (scene) {
    scene.traverse(obj => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry?.dispose()
        if (Array.isArray(obj.material)) {
          obj.material.forEach(m => m.dispose())
        } else {
          obj.material?.dispose()
        }
      }
      if (obj instanceof THREE.Sprite) {
        obj.material?.dispose()
      }
      if (
        obj instanceof THREE.PointLight ||
        obj instanceof THREE.DirectionalLight
      ) {
        if (obj.shadow?.map) obj.shadow.map.dispose()
      }
    })
  }

  // Материалы пула машин
  carPool.forEach(car => {
    car.bodyMesh.material.dispose()
    car.wheelMeshes.forEach(w => w.material.dispose())
    car.mesh.children.forEach(child => {
      if (child instanceof THREE.Mesh) {
        child.material?.dispose()
      }
    })
  })
  carPool.length = 0
  activeCars.length = 0

  // Материалы светофоров
  trafficLights.forEach(tl => {
    Object.values(tl.lights).forEach(l => l.material.dispose())
    Object.values(tl.glowSprites).forEach(g => g.material.dispose())
    tl.group.children.forEach(c => {
      if (c instanceof THREE.Mesh) c.material?.dispose()
    })
  })
  trafficLights.length = 0

  // Глобальные материалы
  Object.values(materials).forEach(m => m?.dispose())
  Object.values(geometries).forEach(g => g?.dispose())

  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss()
    renderer = null
  }

  scene = null
  camera = null
  clock = null
}

/* ============================================================
   LIFECYCLE
   ============================================================ */

onMounted(async () => {
  await nextTick()

  // Проверка prefers-reduced-motion
  setupReducedMotion()

  // Инициализация Three.js
  initThree()

  // IntersectionObserver
  setupIntersectionObserver()
})

onBeforeUnmount(() => {
  cleanup()
})

/* ============================================================
   FALLBACK RENDERING (SVG/Canvas 2D)
   ============================================================ */

function renderFallback() {
  if (!fallbackRef.value) return

  const width = containerRef.value?.clientWidth || 800
  const height = props.height || 280

  // Простой SVG фоллбэк в тех же цветах
  fallbackRef.value.innerHTML = `
    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="display:block;">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${COLORS.skyTop.toString(16).padStart(6, '0')}"/>
          <stop offset="100%" stop-color="${COLORS.skyBottom.toString(16).padStart(6, '0')}"/>
        </linearGradient>
        <linearGradient id="road" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#2a2d30"/>
          <stop offset="100%" stop-color="#1a1d20"/>
        </linearGradient>
        <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#4a6b3a"/>
          <stop offset="100%" stop-color="#3a5528"/>
        </linearGradient>
      </defs>
      <!-- Небо -->
      <rect width="${width}" height="${height}" fill="url(#sky)"/>
      <!-- Трава -->
      <rect y="${height * 0.55}" width="${width}" height="${height * 0.45}" fill="url(#grass)"/>
      <!-- Дорога -->
      <rect y="${height * 0.35}" width="${width}" height="${height * 0.2}" fill="url(#road)"/>
      <!-- Разметка -->
      <g stroke="#f5f5f0" stroke-width="${Math.max(1, height * 0.003)}" stroke-dasharray="20,15">
        <line x1="0" y1="${height * 0.45}" x2="${width}" y2="${height * 0.45}"/>
        <line x1="0" y1="${height * 0.5}" x2="${width}" y2="${height * 0.5}" stroke="#ffd600"/>
      </g>
      <!-- Тротуары -->
      <rect y="${height * 0.3}" width="${width}" height="${height * 0.05}" fill="#8a9a8a"/>
      <rect y="${height * 0.55}" width="${width}" height="${height * 0.05}" fill="#8a9a8a"/>
      <!-- Некоторые деревья/фонари как простые формы -->
      <g fill="#3d5d2d">
        ${Array.from({ length: 10 }, (_, i) => {
          const x = (width / 10) * i + width / 20
          const y = height * 0.25
          return `<polygon points="${x},${y} ${x - 15},${y + 30} ${x + 15},${y + 30}"/>`
        }).join('')}
      </g>
      <g fill="#43a047">
        ${Array.from({ length: 10 }, (_, i) => {
          const x = (width / 10) * i + width / 20
          const y = height * 0.68
          return `<polygon points="${x},${y} ${x - 15},${y - 30} ${x + 15},${y - 30}"/>`
        }).join('')}
      </g>
    </svg>
  `
}

/* ============================================================
   TEMPLATE
   ============================================================ */
</script>

<template>
  <div
    ref="containerRef"
    class="road-banner"
    :style="{ height: height + 'px', width: '100%' }"
    role="img"
    aria-label="Анимированная низкополигональная городская дорога с транспортом и светофорами"
  >
    <!-- Canvas для Three.js -->
    <canvas
      ref="canvasRef"
      class="road-banner__canvas"
      v-show="webglSupported"
      style="display: block; width: 100%; height: 100%"
    />

    <!-- Fallback для no-WebGL или reduced-motion -->
    <div
      ref="fallbackRef"
      class="road-banner__fallback"
      v-show="!webglSupported || reducedMotion"
      style="display: none; width: 100%; height: 100%"
    />
  </div>
</template>

<style scoped>
.road-banner {
  position: relative;
  border-radius: 0;
  overflow: hidden;
  background: transparent;
  /* Чтобы скролл работал поверх баннера */
  pointer-events: none;
}

.road-banner__canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.road-banner__fallback {
  width: 100%;
  height: 100%;
}

/* На мобильных уменьшаем высоту через пропсы родителя */
@media (max-width: 600px) {
  .road-banner {
    /* высота задаётся через prop */
  }
}
</style>
