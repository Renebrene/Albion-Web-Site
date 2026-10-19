<template>
  <q-page class="smart-chat-page">
    <main class="smart-chat-content">
      <div class="chat-heading">
        <span class="kicker">ALBION AI</span>
        <h1>Умный чат</h1>
        <span class="intro">Задайте вопрос о рекламных конструкциях.</span>

        <div class="chat-head-actions">
          <ChatSaveButton />
        </div>

        <div class="chat-columns">
          <span class="chat-columns-label">Столбцов:</span>
          <button
            v-for="value in 4"
            :key="value"
            type="button"
            class="chat-columns-btn"
            :class="{ 'is-active': columns === value }"
            @click="columns = value"
          >
            {{ value }}
          </button>
        </div>
      </div>

      <div class="chat-grid" :style="{ '--cols': columns }">
        <div v-for="chat in chats" :key="chat.key" class="chat-tile">
          <SmartChatPanel
            variant="page"
            :chat-key="chat.key"
            :chat-number="chat.number"
            :columns="1"
            :initial-draft="chat.draft"
          />
        </div>

        <!-- Шаблон нового чата: контур с «+»; по клику активируется,
             а рядом появляется следующий шаблон. -->
        <button
          type="button"
          class="chat-tile chat-tile--new"
          aria-label="Новый чат"
          @click="onCreate"
        >
          <span class="chat-tile-plus" aria-hidden="true">＋</span>
        </button>
      </div>
    </main>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import ChatSaveButton from '../components/chat/ChatSaveButton.vue'
import SmartChatPanel from '../components/chat/SmartChatPanel.vue'
import { useChatWorkspace } from '../composables/useChatWorkspace'

const route = useRoute()

/* Число столбцов сетки чатиков. */
const columns = ref(1)

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

/*
 * Чаты общие с маленьким окном (шапка): один и тот же список и состояние,
 * поэтому информация и количество синхронизированы. Оформление — вариант
 * «page» (см. .chat-panel--page).
 */
const { chats, addChat, init } = useChatWorkspace()

/* Клик по шаблону: активируем чат и оставляем рядом новый шаблон. */
function onCreate() {
  addChat(chats.value.length === 0 ? draft.value : '')
}

onMounted(init)
</script>

<style scoped>
.smart-chat-page {
  min-height: 100vh;
  background: #f3f5f6;
}
.smart-chat-content {
  /* Рабочее поле — от края до края страницы. Верхний отступ резервирует
     место под фиксированную шапку чата. */
  width: 100%;
  margin: 0;
  padding: calc(var(--albion-header-h, 78px) + 64px) clamp(16px, 3vw, 48px) 48px;
}
/*
 * Шапка зафиксирована во вьюпорте под шапкой сайта: всегда видна,
 * не уезжает при прокрутке. z-index ниже шапки сайта (1000).
 */
.chat-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;

  position: fixed;
  top: var(--albion-header-h, 78px);
  left: 0;
  right: 0;
  z-index: 900;

  padding: 12px clamp(16px, 3vw, 48px);
  background: #f3f5f6;
  border-bottom: 1px solid #e5e9ec;
}
.chat-columns {
  display: flex;
  align-items: center;
  gap: 6px;

  margin-left: auto;
}
.chat-columns-label {
  color: #5f6c76;
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.chat-columns-btn {
  min-width: 24px;
  height: 22px;
  padding: 0 6px;
  border: 1px solid #dce2e6;
  border-radius: 6px;
  background: #fff;
  color: #52606a;
  font-family: inherit;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: 0.15s ease;
}
.chat-columns-btn:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}
.chat-columns-btn.is-active {
  border-color: var(--albion-accent);
  background: #fdeceb;
  color: var(--albion-accent);
}

/* Сетка независимых чатиков: слева направо, число столбцов — из переключателя. */
.chat-grid {
  display: grid;
  grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}
.chat-tile {
  min-width: 0;
  padding: 16px;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 30px rgba(25, 35, 45, 0.06);
}
/* Шаблон нового чата — только контур с «+». */
.chat-tile--new {
  display: grid;
  place-items: center;
  min-height: 220px;
  padding: 16px;
  border: 2px dashed #cfd6db;
  background: transparent;
  box-shadow: none;
  color: #5f6c76;
  cursor: pointer;
  transition: 0.15s ease;
}
.chat-tile--new:hover {
  border-color: var(--albion-accent);
  color: var(--albion-accent);
}
.chat-tile-plus {
  font-size: 40px;
  font-weight: 300;
  line-height: 1;
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
  color: #5b6873;
  font-size: 14px;
}

/* Сохранение чатов в личном кабинете. */
.chat-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (max-width: 760px) {
  .chat-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
