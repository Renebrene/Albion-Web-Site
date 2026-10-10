<template>
  <q-page class="smart-chat-page">
    <main class="smart-chat-content">
      <div class="chat-heading">
        <span class="kicker">ALBION AI</span>
        <h1>Умный чат</h1>
        <span class="intro">Задайте вопрос о рекламных конструкциях.</span>
      </div>

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
  /* Рабочее поле — от края до края страницы. */
  width: 100%;
  margin: 0;
  padding: 28px clamp(16px, 3vw, 48px) 48px;
}
.chat-heading {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 12px;
}
.kicker {
  color: var(--albion-accent);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 2px;
}
h1 {
  margin: 0;
  color: #17212b;
  font-size: clamp(22px, 2.6vw, 30px);
  line-height: 1;
}
.intro {
  color: #71808c;
  font-size: 14px;
}
.smart-chat-content :deep(.chat-panel) {
  margin-top: 16px;
  padding: 20px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(25, 35, 45, 0.06);
}
</style>
