<template>
  <section class="offices-section">
    <div class="offices">
      <article v-for="office in offices" :key="office.id" class="office-card">
        <div class="office-info">
          <h3>{{ office.name }}</h3>

          <address class="office-address">
            {{ office.address }}
          </address>

          <a
            v-if="office.phone"
            class="office-phone"
            :href="`tel:${office.phone.replace(/[^+0-9]/g, '')}`"
          >
            {{ office.phone }}
          </a>

          <div
            v-if="office.emails && office.emails.length"
            class="office-emails"
          >
            <a
              v-for="email in office.emails"
              :key="email"
              :href="`mailto:${email}`"
            >
              {{ email }}
            </a>
          </div>

          <div v-if="office.schedule" class="office-schedule">
            <span>Режим работы:</span>
            {{ office.schedule }}
          </div>
        </div>

        <div class="office-map">
          <a
            v-if="office.mapUrl"
            class="map-image-link"
            :href="office.mapUrl"
            target="_blank"
            rel="noopener"
          >
            <img
              v-if="office.image"
              :src="office.image"
              :alt="`Карта: ${office.name}`"
            />
            <span v-else class="map-placeholder"> Яндекс.Карта </span>
          </a>

          <a
            v-if="office.mapUrl"
            class="map-link"
            :href="office.mapUrl"
            target="_blank"
            rel="noopener"
          >
            смотреть на карте →
          </a>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
defineProps({
  offices: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.offices-section {
  padding: 10px 4vw 34px;
}

.offices {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.office-card {
  display: grid;
  grid-template-columns: 1fr minmax(0, 1fr);
  gap: 18px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid #e6e8ec;
  background: white;
  box-shadow: 0 8px 26px rgba(23, 33, 43, 0.05);
  align-items: start;
}

/* ——— левая часть карточки ——— */
.office-info h3 {
  margin: 0 0 10px;
  font-size: 17px;
  letter-spacing: -0.01em;
}

.office-address {
  display: block;
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.45;
  color: #17212b;
  white-space: pre-line;
}

.office-phone {
  display: block;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 700;
  color: #17212b;
  text-decoration: none;
}

.office-emails {
  display: grid;
  gap: 4px;
  margin-bottom: 10px;
}

.office-emails a {
  color: #65717a;
  font-size: 12px;
  text-decoration: none;
  word-break: break-word;
}

.office-schedule {
  color: #65717a;
  font-size: 12px;
  line-height: 1.45;
}

.office-schedule span {
  color: #a0abb3;
}

/* ——— правая часть карточки: Яндекс.Карта ——— */
.office-map {
  display: grid;
  gap: 8px;
}

.map-image-link {
  display: grid;
  place-items: center;
  min-height: 150px;
  border-radius: 12px;
  background: #eef1f3;
  overflow: hidden;
}

.map-image-link img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.map-placeholder {
  color: #8a969f;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.map-link {
  justify-self: start;
  color: #17212b;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

@media (max-width: 900px) {
  .offices {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .office-card {
    grid-template-columns: 1fr;
  }

  .map-image-link {
    min-height: 120px;
  }
}
</style>
