<template>
  <section class="section">
    <div class="section-head">
      <div>
        <div class="eyebrow">ГДЕ МЫ</div>
        <h2>Наши офисы</h2>
      </div>
      <a class="phone" :href="phoneHref">{{ phone }}</a>
    </div>

    <div class="offices">
      <article
        v-for="office in offices"
        :key="office.id"
        class="office-card"
      >
        <div class="office-top">
          <span class="office-number">
            {{ String(office.sortOrder).padStart(2, '0') }}
          </span>
          <h3>{{ office.name }}</h3>
        </div>

        <div class="office-address">
          {{ office.address }}
        </div>

        <div class="office-details">
          <a
            v-if="office.phone"
            :href="`tel:${office.phone.replace(/[^+0-9]/g, '')}`"
          >
            {{ office.phone }}
          </a>

          <a
            v-if="office.email"
            :href="`mailto:${office.email}`"
          >
            {{ office.email }}
          </a>

          <span v-if="office.schedule">
            {{ office.schedule }}
          </span>
        </div>

        <button
          class="map-button"
          type="button"
          @click="$emit('show-map', office)"
        >
          Показать на карте →
        </button>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  offices: {
    type: Array,
    default: () => []
  },
  phone: {
    type: String,
    default: ''
  }
})

defineEmits(['show-map'])

const phoneHref = computed(() =>
  `tel:${props.phone.replace(/[^+0-9]/g, '')}`
)
</script>

<style scoped>
.section {
  padding: 72px 5vw;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 30px;
  margin-bottom: 34px;
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
  font-size: clamp(34px, 4vw, 52px);
  letter-spacing: -.035em;
}

.phone {
  color: #17212b;
  font-size: 20px;
  font-weight: 800;
  text-decoration: none;
}

.offices {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.office-card {
  min-height: 310px;
  padding: 30px;
  border-radius: 22px;
  background: white;
  box-shadow: 0 12px 40px rgba(23,33,43,.07);
  display: flex;
  flex-direction: column;
}

.office-top {
  display: flex;
  gap: 18px;
  align-items: flex-start;
}

.office-number {
  font-size: 13px;
  font-weight: 800;
  color: #a0abb3;
}

h3 {
  margin: 0;
  font-size: 27px;
}

.office-address {
  margin-top: 28px;
  font-size: 20px;
  line-height: 1.45;
  max-width: 520px;
}

.office-details {
  display: grid;
  gap: 8px;
  margin-top: 22px;
  color: #65717a;
}

.office-details a {
  color: inherit;
  text-decoration: none;
}

.map-button {
  margin-top: auto;
  align-self: flex-start;
  padding: 12px 0 0;
  border: 0;
  background: transparent;
  color: #17212b;
  font-weight: 800;
  cursor: pointer;
}

@media (max-width: 800px) {
  .section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .offices {
    grid-template-columns: 1fr;
  }
}
</style>
