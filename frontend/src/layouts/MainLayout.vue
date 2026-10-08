<template>
  <q-layout view="hHh lpR fFf">
    <AppHeader />

    <q-page-container>
      <router-view />
    </q-page-container>

    <AppFooter />
  </q-layout>
</template>

<script setup>
import { onMounted } from 'vue'

import AppHeader from '../components/layout/AppHeader.vue'
import AppFooter from '../components/layout/AppFooter.vue'
import { applySiteSettings } from '../boot/settings'

onMounted(() => {
  applySiteSettings()
})
</script>

<style>
.q-page-container {
  background: var(--albion-bg);
}
</style>
