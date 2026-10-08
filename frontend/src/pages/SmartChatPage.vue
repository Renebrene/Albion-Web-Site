<template>
  <q-page class="placeholder-page">
    <main class="placeholder-content">
      <div class="kicker">ALBION AI</div>
      <h1>Умный чат</h1>
      <p>Интеллектуальный помощник Albion будет здесь.</p>

      <!-- Черновик обращения, переданный из портфеля (?draft=...) -->
      <section v-if="draft" class="draft-block">
        <div class="draft-hint">Скопировано из портфеля</div>

        <textarea
          class="draft-text"
          readonly
          :value="draft"
          rows="12"
        ></textarea>

        <div class="draft-actions">
          <q-btn
            outline
            no-caps
            dense
            class="draft-copy"
            label="Скопировать ещё раз"
            @click="copyDraft"
          />
          <span v-if="copied" class="draft-copied">Скопировано</span>
        </div>
      </section>
    </main>
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import { copyToClipboard } from '../services/portfolioExport'

const route = useRoute()

/*
 * Черновик из query-параметра.
 * vue-router декодирует query сам, поэтому decodeURIComponent здесь
 * применяем только как страховку — при ошибке оставляем строку как есть.
 */
const draft = computed(() => {
  const raw = route.query.draft

  if (!raw) {
    return ''
  }

  const value = Array.isArray(raw) ? raw[0] : String(raw)

  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
})

const copied = ref(false)

async function copyDraft() {
  copied.value = await copyToClipboard(draft.value)

  if (copied.value) {
    window.setTimeout(() => {
      copied.value = false
    }, 2500)
  }
}
</script>

<style scoped>
.placeholder-page {
  min-height: 100vh;
  background: #f3f5f6;
}

.placeholder-content {
  padding: 100px 8%;
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

p {
  color: #71808c;
}

/* ---------------- Черновик ---------------- */

.draft-block {
  margin-top: 24px;

  max-width: 720px;

  padding: 16px;

  border: 1px solid #e5e9ec;
  border-radius: 14px;

  background: #fff;

  box-shadow: 0 12px 30px rgba(25, 35, 45, .06);
}

.draft-hint {
  margin-bottom: 8px;

  color: var(--albion-accent);

  font-size: 11px;
  font-weight: 900;

  letter-spacing: .08em;

  text-transform: uppercase;
}

.draft-text {
  display: block;

  width: 100%;

  padding: 12px;

  border: 1px solid #e5e9ec;
  border-radius: 10px;

  background: #fafbfc;
  color: #17212b;

  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;

  resize: vertical;
}

.draft-actions {
  display: flex;
  align-items: center;

  gap: 10px;

  margin-top: 10px;
}

.draft-copied {
  color: #1b5e20;

  font-size: 12px;
  font-weight: 700;
}
</style>
