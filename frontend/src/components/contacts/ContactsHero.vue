<template>
  <section class="contacts-hero">
    <div>
      <div class="eyebrow">{{ data?.eyebrow || 'ALBION · КОНТАКТЫ' }}</div>
      <h1>{{ data?.title || 'Давайте обсудим вашу задачу' }}</h1>
      <p>{{ data?.text }}</p>
    </div>
  </section>
</template>

<script setup>
defineProps({
  data: {
    type: Object,
    default: () => ({})
  }
})
</script>

<style scoped>
.contacts-hero {
  padding: 72px 5vw 54px;
  background: #17212b;
  color: white;
}

.eyebrow {
  margin-bottom: 16px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .16em;
  opacity: .7;
}

h1 {
  max-width: 850px;
  margin: 0;
  font-size: clamp(42px, 6vw, 76px);
  line-height: .98;
  letter-spacing: -.04em;
}

p {
  max-width: 720px;
  margin: 26px 0 0;
  font-size: 19px;
  line-height: 1.55;
  color: rgba(255,255,255,.75);
}
</style>
