<template>
  <section class="section">
    <div
      v-for="department in departments"
      :key="department.id"
      class="department"
    >
      <div class="department-head">
        <div class="eyebrow">КОМАНДА</div>
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
              v-if="employee.photo"
              :src="employee.photo"
              :alt="employee.name"
            >
            <span v-else>
              {{ initials(employee.name) }}
            </span>
          </div>

          <div class="employee-info">
            <div class="position">{{ employee.position }}</div>
            <h3>{{ employee.name }}</h3>

            <div class="contacts">
              <a
                v-if="employee.phone"
                :href="`tel:${employee.phone.replace(/[^+0-9]/g, '')}`"
              >
                {{ employee.phone }}
                <span v-if="employee.extension">
                  · доб. {{ employee.extension }}
                </span>
              </a>

              <a
                v-if="employee.email"
                :href="`mailto:${employee.email}`"
              >
                {{ employee.email }}
              </a>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  departments: {
    type: Array,
    default: () => []
  }
})

function initials(name) {
  return String(name || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0])
    .join('')
    .toUpperCase()
}
</script>

<style scoped>
.section {
  padding: 20px 5vw 80px;
}

.department {
  margin-top: 60px;
}

.department-head {
  margin-bottom: 28px;
}

.eyebrow {
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .16em;
  color: #7a8791;
}

h2 {
  margin: 0;
  font-size: clamp(28px, 3.5vw, 44px);
  letter-spacing: -.03em;
}

.employees {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.employee {
  display: flex;
  gap: 18px;
  padding: 20px;
  border-radius: 18px;
  background: white;
  box-shadow: 0 8px 30px rgba(23,33,43,.05);
}

.photo {
  flex: 0 0 70px;
  width: 70px;
  height: 70px;
  border-radius: 16px;
  overflow: hidden;
  background: #e9edf0;
  display: grid;
  place-items: center;
  font-size: 19px;
  font-weight: 800;
  color: #66727c;
}

.photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.position {
  font-size: 12px;
  line-height: 1.35;
  color: #7a8791;
}

h3 {
  margin: 7px 0 14px;
  font-size: 18px;
}

.contacts {
  display: grid;
  gap: 5px;
  font-size: 13px;
}

.contacts a {
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
