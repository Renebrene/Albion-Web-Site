<template>
  <footer class="site-footer">
    <nav class="footer-links" aria-label="Подвал сайта">
      <a
        v-for="item in footerItems"
        :key="item.key"
        :href="item.url"
        class="footer-link"
        title="Раздел в разработке"
      >
        {{ item.label }}
      </a>
    </nav>

    <div class="footer-brand">
      2027@АЛЬБИОН
    </div>
  </footer>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const DEFAULT_FOOTER = [
  { key: 'privacy', label: 'Политика конфиденциальности', url: '#' },
  { key: 'tech-requirements', label: 'Технические требования', url: '#' },
  { key: 'sitemap', label: 'Карта сайта', url: '#' },
  { key: 'legal', label: 'Юридическая информация', url: '#' }
]

const footerItems = ref(DEFAULT_FOOTER)

onMounted(async () => {
  try {
    const response = await fetch('/api/site-menu')
    const data = await response.json()

    if (data?.footer?.length) {
      footerItems.value = data.footer
    }
  } catch (exc) {
    /* остаёмся на значениях по умолчанию */
  }
})
</script>

<style scoped>
.site-footer {
  /* Всегда виден: зафиксирован у нижнего края, контент прокручивается
     «мимо» него (высота компенсируется padding-bottom у q-page-container). */
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;

  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;

  padding: 14px 24px;

  background: #17212b;

  color: rgba(255, 255, 255, .7);
}

.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 22px;
}

.footer-link {
  color: rgba(255, 255, 255, .7);

  font-size: 12px;

  text-decoration: none;

  transition: color .15s ease;
}

.footer-link:hover {
  color: #fff;
}

.footer-brand {
  color: rgba(255, 255, 255, .45);

  font-size: 12px;
  font-weight: 800;
  letter-spacing: .12em;
}

@media (max-width: 640px) {
  .site-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>