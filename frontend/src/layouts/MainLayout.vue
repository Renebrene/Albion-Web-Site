<template>
  <q-layout view="hHh lpR fFf">
    <AppHeader />

    <q-page-container>
      <router-view />
    </q-page-container>

    <AppFooter />

    <!-- Общее окно просмотра фото — доступно на всех публичных страницах -->
    <PhotoViewer />
  </q-layout>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import AppHeader from '../components/layout/AppHeader.vue'
import AppFooter from '../components/layout/AppFooter.vue'
import PhotoViewer from '../components/common/PhotoViewer.vue'
import { applySiteSettings } from '../boot/settings'

const route = useRoute()

/*
 * Меряем реальные высоты шапки и подвала и кладём их в CSS-переменные:
 * страницы считают высоту контента от них, поэтому зазора перед подвалом нет.
 */
function syncChromeHeights() {
  const root = document.documentElement

  const header = document.querySelector('.header')
  const footer = document.querySelector('.site-footer')

  if (header) {
    root.style.setProperty('--albion-header-h', `${header.offsetHeight}px`)
  }

  if (footer) {
    root.style.setProperty('--albion-footer-h', `${footer.offsetHeight}px`)
  }
}

onMounted(() => {
  applySiteSettings()

  nextTick(syncChromeHeights)

  window.addEventListener('resize', syncChromeHeights)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncChromeHeights)
})

watch(
  () => route.fullPath,
  () => nextTick(syncChromeHeights)
)
</script>

<style>
.q-page-container {
  background: var(--albion-bg);

  /* Подвал зафиксирован у низа — компенсируем его высоту, чтобы контент
     не заезжал под него и прокручивался «мимо». */
  padding-bottom: var(--albion-footer-h, 46px);
}

/* Страница карты на десктопе сама считает высоту (100dvh − шапка − подвал)
   и держит контейнер в своих границах — лишний паддинг там не нужен.
   На мобильном контент прокручивается, поэтому отступ под подвал сохраняем. */
@media (min-width: 761px) {
  body:has(.advertising-page) .q-page-container {
    padding-bottom: 0;
  }
}
</style>
