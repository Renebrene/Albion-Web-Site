<template>
  <q-page class="portfolio-page">
    <div class="portfolio-wrap">
      <!-- ЗАГОЛОВОК СТРАНИЦЫ -->
      <div class="page-head">
        <div class="eyebrow">ALBION</div>
        <h1>Портфель</h1>
        <p>Выбранные поверхности и месяцы — экспорт, печать и заявка</p>
      </div>

      <!-- Панель портфеля (та же, что в шапке) -->
      <PortfolioPanel variant="page" />
    </div>
  </q-page>
</template>

<script setup>
import PortfolioPanel from '../components/portfolio/PortfolioPanel.vue'
</script>

<style scoped>
/*
 * Страница живёт внутри MainLayout, поэтому высоту считаем от реальных
 * высот шапки/подвала (переменные выставляет MainLayout).
 */
.portfolio-page {
  background: #f3f5f6;
}

.portfolio-wrap {
  width: min(1100px, 100%);

  margin: 0 auto;

  padding: 40px 24px 56px;

  min-height: calc(
    100dvh - var(--albion-header-h, 78px) - var(--albion-footer-h, 46px)
  );
}

.page-head {
  margin-bottom: 20px;
}

.eyebrow {
  color: var(--albion-accent);

  font-size: 10px;
  font-weight: 900;

  letter-spacing: 2px;
}

h1 {
  margin: 8px 0 6px;

  color: #17212b;

  font-size: 36px;
  line-height: 1.05;
}

p {
  margin: 0;

  color: #71808c;

  font-size: 14px;
}

@media (max-width: 600px) {
  .portfolio-wrap {
    padding: 24px 14px 40px;
  }

  h1 {
    font-size: 28px;
  }
}
</style>
