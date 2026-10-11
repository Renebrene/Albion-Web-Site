<template>
  <section class="section">
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
              v-if="employee.photo"
              :src="employee.photo"
              :alt="employee.name || employee.position"
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
  gap: 14px;
  padding: 15px 16px;
  border-radius: 14px;
  border: 1px solid #ecedf0;
  background: white;
  box-shadow: 0 5px 20px rgba(23, 33, 43, 0.04);
}

.photo {
  flex: 0 0 60px;
  width: 60px;
  height: 60px;
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
