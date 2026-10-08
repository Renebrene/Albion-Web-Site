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
}
</style>
