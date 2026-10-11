<template>
  <q-page class="placeholder-page">
    <main class="placeholder-content">
      <div class="placeholder-kicker"> ALBION </div>

      <h1>
        {{ title }}
      </h1>

      <p> Раздел находится в разработке. </p>
    </main>
  </q-page>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  }
})
</script>

<style scoped>
/*
 * Страница живёт внутри MainLayout (шапка и подвал отрисовываются там),
 * поэтому высоту контента считаем от реальных высот шапки/подвала —
 * переменные --albion-header-h / --albion-footer-h выставляет MainLayout.
 */
.placeholder-page {
  background: #f3f5f6;
}

.placeholder-content {
  min-height: calc(
    100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px)
  );

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
