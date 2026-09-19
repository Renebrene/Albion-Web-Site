<template>
  <q-page class="home-page">
    <HomeHero />

    <HomeStats />

    <HomeInventory />

    <HomeSearch />

    <HomeNetwork />

    <HomeDirections />

    <HomeAdvantages />

    <HomeNews />

    <HomeCta />
  </q-page>
</template>

<script setup>
import HomeHero from '@/components/home/HomeHero.vue'
import HomeStats from '@/components/home/HomeStats.vue'
import HomeInventory from '@/components/home/HomeInventory.vue'
import HomeSearch from '@/components/home/HomeSearch.vue'
import HomeNetwork from '@/components/home/HomeNetwork.vue'
import HomeDirections from '@/components/home/HomeDirections.vue'
import HomeAdvantages from '@/components/home/HomeAdvantages.vue'
import HomeNews from '@/components/home/HomeNews.vue'
import HomeCta from '@/components/home/HomeCta.vue'
</script>

<style scoped>
.home-page {
  background: #f4f6f7;
  color: #17212b;
}
</style>
