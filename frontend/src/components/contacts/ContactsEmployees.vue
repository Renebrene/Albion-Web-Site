<template>
  <section ref="root" class="section">
    <div
      v-for="department in departments"
      :key="department.id"
      class="department"
    >
      <div class="department-head">
        <h2>{{ department.name }}</h2>
      </div>

      <div class="employees">
        <article
          v-for="employee in department.employees"
          :key="employee.id"
          class="employee"
        >
          <div class="photo">
            <img
              v-if="photoSrc(employee) && !brokenPhotos.has(employee.id)"
              :src="photoSrc(employee)"
              :alt="employee.name || employee.position"
              @error="onPhotoError(employee.id)"
              @load="scheduleEqualize"
            />
            <span v-else-if="employee.name">
              {{ initials(employee.name) }}
            </span>
            <span v-else class="photo-empty">●</span>
          </div>

          <div class="employee-info">
            <div class="position">{{ employee.position }}</div>
            <h3 v-if="employee.name">{{ employee.name }}</h3>
            <div v-if="employee.subdivision" class="subdivision">
              {{ employee.subdivision }}
            </div>

            <div class="contacts">
              <div v-if="employee.workPhone" class="contact-row">
                <span class="contact-label">Рабочий</span>
                <a :href="`tel:${employee.workPhone.replace(/[^+0-9]/g, '')}`">
                  {{ employee.workPhone }}
                  <template v-if="employee.extension">
                    · доб. {{ employee.extension }}
                  </template>
                </a>
              </div>

              <div v-if="employee.personalPhone" class="contact-row">
                <span class="contact-label">Личный</span>
                <a
                  :href="`tel:${employee.personalPhone.replace(/[^+0-9]/g, '')}`"
                >
                  {{ employee.personalPhone }}
                </a>
              </div>

              <div v-if="employee.email" class="contact-row">
                <span class="contact-label">Почта</span>
                <a :href="`mailto:${employee.email}`">
                  {{ employee.email }}
                </a>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  departments: {
    type: Array,
    default: () => []
  }
})

// Сгенерированные low-poly мультяшные аватары (жуки, микробы, морское дно).
// Подставляются, когда у сотрудника нет своего фото.
const GENERATED_PHOTOS = [
  '/employee-photos/p1.svg',
  '/employee-photos/p2.svg',
  '/employee-photos/p3.svg',
  '/employee-photos/p4.svg',
  '/employee-photos/p5.svg',
  '/employee-photos/p6.svg',
  '/employee-photos/p7.svg',
  '/employee-photos/p8.svg',
  '/employee-photos/p9.svg',
  '/employee-photos/p10.svg',
  '/employee-photos/p11.svg',
  '/employee-photos/p12.svg'
]

const photoIndex = computed(() => {
  const map = new Map()
  let index = 0

  for (const department of props.departments) {
    for (const employee of department.employees || []) {
      if (!map.has(employee.id)) {
        map.set(employee.id, GENERATED_PHOTOS[index % GENERATED_PHOTOS.length])
        index += 1
      }
    }
  }

  return map
})

function photoSrc(employee) {
  if (employee.photo) {
    return employee.photo
  }

  return photoIndex.value.get(employee.id) || ''
}

// Если картинка не загрузилась — показываем инициалы, а не битую картинку.
const brokenPhotos = ref(new Set())

function onPhotoError(id) {
  if (brokenPhotos.value.has(id)) {
    return
  }

  const next = new Set(brokenPhotos.value)
  next.add(id)
  brokenPhotos.value = next
  scheduleEqualize()
}

function initials(name) {
  return String(name || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase()
}

// Все карточки одной высоты — по самой высокой в списке.
const root = ref(null)
let observer = null
let frame = 0

function equalize() {
  const container = root.value

  if (!container) {
    return
  }

  const cards = Array.from(container.querySelectorAll('.employee'))

  if (!cards.length) {
    return
  }

  cards.forEach(card => {
    card.style.minHeight = ''
  })

  const maxHeight = cards.reduce(
    (max, card) => Math.max(max, card.offsetHeight),
    0
  )

  if (!maxHeight) {
    return
  }

  const value = `${maxHeight}px`

  cards.forEach(card => {
    if (card.style.minHeight !== value) {
      card.style.minHeight = value
    }
  })
}

function scheduleEqualize() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(equalize)
}

onMounted(() => {
  observer = new ResizeObserver(scheduleEqualize)
  observer.observe(root.value)
  window.addEventListener('resize', scheduleEqualize)
  scheduleEqualize()
})

watch(
  () => props.departments,
  async () => {
    await nextTick()
    scheduleEqualize()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  window.removeEventListener('resize', scheduleEqualize)

  if (observer) {
    observer.disconnect()
    observer = null
  }
})
</script>

<style scoped>
.section {
  padding: 4px 4vw 56px;
}

.department {
  margin-top: 24px;
}

.department-head {
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e6e8ec;
}

h2 {
  margin: 0;
  font-size: clamp(15px, 2vw, 21px);
  letter-spacing: -0.01em;
}

.employees {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.employee {
  display: flex;
  align-items: stretch;
  gap: 14px;
  padding: 15px 16px;
  border-radius: 14px;
  border: 1px solid #ecedf0;
  background: white;
  box-shadow: 0 5px 20px rgba(23, 33, 43, 0.04);
}

/* Фото тянется по высоте карточки (чуть меньше её за счёт паддингов)
   и сохраняет пропорцию 3:4 за счёт aspect-ratio.
   Картинка вынесена из потока: её собственный размер (300×400 у SVG)
   не должен участвовать в расчёте иначе ширина флекс-элемента
   задастся контентом, а не высотой карточки. */
.photo {
  position: relative;
  flex: 0 0 auto;
  align-self: stretch;
  width: auto;
  aspect-ratio: 3 / 4;
  border-radius: 14px;
  overflow: hidden;
  background: #e9edf0;
  display: grid;
  place-items: center;
  font-size: 16px;
  font-weight: 800;
  color: #66727c;
}

.photo img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.photo-empty {
  color: #a0abb3;
  font-size: 26px;
}

.position {
  font-size: 12px;
  line-height: 1.35;
  color: #7a8791;
}

h3 {
  margin: 6px 0 0;
  font-size: 15px;
}

.subdivision {
  margin-top: 6px;
  font-size: 12px;
  color: #a0abb3;
}

.contacts {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  font-size: 13px;
}

.contact-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
  align-items: baseline;
}

.contact-label {
  color: #a0abb3;
  font-size: 11px;
}

.contact-row a {
  color: #17212b;
  text-decoration: none;
  word-break: break-word;
}

@media (max-width: 1100px) {
  .employees {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 700px) {
  .employees {
    grid-template-columns: 1fr;
  }

  .employee {
    padding: 16px;
  }
}
</style>
