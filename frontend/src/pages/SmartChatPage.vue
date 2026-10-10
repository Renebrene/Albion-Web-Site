<template>
  <q-page class="smart-chat-page">
    <main class="smart-chat-content">
      <div class="kicker">ALBION AI</div>
      <h1>Умный чат</h1>
      <p class="intro">Задайте вопрос о рекламных конструкциях.</p>
      <SmartChatPanel :initial-draft="draft" />
    </main>
  </q-page>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import SmartChatPanel from '../components/chat/SmartChatPanel.vue'

const route = useRoute()

const draft = computed(() => {
  const raw = route.query.draft
  if (!raw) return ''
  const value = Array.isArray(raw) ? raw[0] : String(raw)
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
})
</script>

<style scoped>
.smart-chat-page {
  min-height: 100vh;
  background: #f3f5f6;
}
.smart-chat-content {
  width: min(920px, 92%);
  margin: 0 auto;
  padding: 72px 0;
}
.kicker {
  color: var(--albion-accent);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 2px;
}
h1 {
  margin: 8px 0;
  color: #17212b;
  font-size: 42px;
}
.intro {
  color: #71808c;
}
.smart-chat-content :deep(.chat-panel) {
  margin-top: 28px;
  padding: 20px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(25, 35, 45, 0.06);
}
</style>
