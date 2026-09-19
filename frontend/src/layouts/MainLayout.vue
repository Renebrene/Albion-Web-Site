<template>
  <q-layout view="hHh lpR fFf">
    <AppHeader />

    <q-page-container>
      <router-view />
    </q-page-container>
  </q-layout>
</template>

<script setup>
import AppHeader from '../components/layout/AppHeader.vue'
</script>

<style>
.q-page-container {
  background: #f3f5f6;
}
</style>
