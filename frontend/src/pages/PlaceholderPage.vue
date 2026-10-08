<template>
  <q-page class="placeholder-page">

    <AppHeader />

    <main class="placeholder-content">

      <div class="placeholder-kicker">
        ALBION
      </div>

      <h1>
        {{ title }}
      </h1>

      <p>
        Раздел находится в разработке.
      </p>

    </main>

    <AppFooter />

  </q-page>
</template>

<script setup>
import AppHeader from '../components/layout/AppHeader.vue'
import AppFooter from '../components/layout/AppFooter.vue'

defineProps({
  title: {
    type: String,
    required: true
  }
})
</script>

<style scoped>
.placeholder-page {
  min-height: 100vh;
  background: #f3f5f6;
}

.placeholder-content {
  min-height: calc(100vh - 115px);

  display: flex;
  align-items: center;
  justify-content: center;

  flex-direction: column;

  padding: 40px;

  text-align: center;
}

.placeholder-kicker {
  color: var(--albion-accent);

  font-size: 10px;
  font-weight: 900;
  letter-spacing: 2px;
}

h1 {
  margin: 10px 0 8px;

  color: #17212b;

  font-size: 38px;
  line-height: 1.05;
}

p {
  margin: 0;

  color: #71808c;

  font-size: 14px;
}
</style>
