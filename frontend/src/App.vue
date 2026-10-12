<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { initSeo } from './composables/useSeo'

const router = useRouter()

/* Заголовок/описание/OG для каждой страницы — из настроек админки. */
onMounted(() => {
  initSeo(router)
})
</script>
