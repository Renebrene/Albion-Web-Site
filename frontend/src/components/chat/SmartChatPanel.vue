<template>
  <section class="chat-panel" aria-label="Спроси помощника">
    <div class="chat-title">СПРОСИ ПОМОЩНИКА</div>

    <div class="chat-messages" role="log" aria-live="polite">
      <div v-if="!messages.length" class="chat-empty">
        Спросите про конструкции, цену, доступность или загрузку.
      </div>

      <div
        v-for="(message, index) in messages"
        :key="`${index}-${message.role}`"
        class="chat-message"
        :class="`chat-message-${message.role}`"
      >
        <div class="chat-bubble">{{ message.text }}</div>
        <div v-if="message.warnings?.length" class="chat-warning">
          {{ message.warnings.join(' ') }}
        </div>
      </div>
    </div>

    <div v-if="lastResponse?.clarification" class="chat-options">
      <q-btn
        v-for="option in lastResponse.clarification.options"
        :key="option.value"
        outline
        dense
        no-caps
        :label="option.label"
        :disable="loading"
        @click="send(option.value)"
      />
    </div>

    <div v-if="lastResponse?.results?.count" class="chat-results">
      <div class="chat-result-count">
        Найдено: {{ lastResponse.results.count }}
      </div>
      <article
        v-for="item in lastResponse.results.items.slice(0, 8)"
        :key="item.id"
        class="chat-result"
      >
        <div class="chat-result-main">
          <strong>{{ item.type || item.media_type || 'Конструкция' }}</strong>
          <span>{{ item.address || 'Адрес не указан' }}</span>
          <span v-if="item.city">{{ item.city }}</span>
          <span v-if="item.price != null"
            >Цена: {{ formatPrice(item.price) }}</span
          >
          <span v-if="item.load_percent != null"
            >Загрузка: {{ item.load_percent }}%</span
          >
        </div>
        <div class="chat-result-actions">
          <q-btn
            v-if="item.photo || item.photo_large"
            flat
            dense
            no-caps
            label="Фото"
            @click="openMedia(item)"
          />
          <q-btn
            v-if="item.map_large || item.map"
            flat
            dense
            no-caps
            label="Схема"
            @click="openMedia(item, true)"
          />
          <q-btn
            flat
            dense
            no-caps
            label="В портфель"
            @click="addToPortfolio(item)"
          />
          <q-btn
            flat
            dense
            no-caps
            label="На карту"
            :disable="item.lat == null || item.lng == null"
            @click="openMap(item)"
          />
          <q-btn flat dense no-caps label="В список" @click="openList(item)" />
          <q-btn
            flat
            dense
            no-caps
            label="Экспорт XLSX"
            @click="exportResults"
          />
        </div>
      </article>
    </div>

    <form class="chat-input" @submit.prevent="submit">
      <textarea
        v-model="draft"
        rows="2"
        maxlength="2000"
        placeholder="Например: свободные пиллары на декабрь"
        :disabled="loading"
        @keydown.ctrl.enter.prevent="submit"
      />
      <div class="chat-input-actions">
        <q-btn
          flat
          dense
          no-caps
          label="Очистить"
          :disable="loading || (!messages.length && !draft)"
          @click="reset"
        />
        <q-btn
          unelevated
          dense
          no-caps
          color="primary"
          label="Спросить"
          type="submit"
          :loading="loading"
          :disable="!draft.trim() || loading"
        />
      </div>
    </form>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { useChatWorkspace } from '../../composables/useChatWorkspace'
import { usePhotoViewer } from '../../composables/usePhotoViewer'
import { usePortfolio } from '../../composables/usePortfolio'
import { downloadPortfolio } from '../../services/portfolioExport'
import { useSmartChat } from '../../composables/useSmartChat'

const props = defineProps({
  initialDraft: {
    type: String,
    default: ''
  }
})

const router = useRouter()
const draft = ref(props.initialDraft)
const { messages, loading, lastResponse, send, reset } = useSmartChat()
const { openPhoto } = usePhotoViewer()
const { toggleMonth } = usePortfolio()
const { setResults } = useChatWorkspace()

function submit() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  send(text)
}

function formatPrice(value) {
  return new Intl.NumberFormat('ru-RU').format(value)
}

function openMedia(item, map = false) {
  const url = map
    ? item.map_large || item.map_card || item.map
    : item.photo_large || item.photo || item.photo_url
  if (!url) return
  openPhoto({
    images: [{ url, label: map ? 'Схема' : 'Фото' }],
    photoTitle: item.address || item.type || 'Конструкция'
  })
}

function openList(item) {
  setResults(lastResponse.value?.results?.items || [item])
  router.push({
    path: '/vozmozhnosti',
    query: { chat: '1', surface: String(item.id) }
  })
}

function openMap(item) {
  setResults(lastResponse.value?.results?.items || [item])
  router.push({
    path: '/vozmozhnosti',
    query: { chat: '1', surface: String(item.id), mode: 'map' }
  })
}

async function exportResults() {
  const rawItems = lastResponse.value?.results?.items || []
  const monthNames = {
    1: 'Январь',
    2: 'Февраль',
    3: 'Март',
    4: 'Апрель',
    5: 'Май',
    6: 'Июнь',
    7: 'Июль',
    8: 'Август',
    9: 'Сентябрь',
    10: 'Октябрь',
    11: 'Ноябрь',
    12: 'Декабрь'
  }
  const items = rawItems.map(item => ({
    ...item,
    surfaceId: item.id,
    type: item.type || item.media_type,
    photo: item.photo || item.photo_large || '',
    months: Object.fromEntries(
      Object.entries(item.monthly_prices || {}).map(([key, price]) => [
        monthNames[key] || key,
        { price, stale: false }
      ])
    )
  }))

  if (!items.length) return
  try {
    await downloadPortfolio('xlsx', items, { title: 'Результаты поиска' })
  } catch (exc) {
    console.warn('Не удалось экспортировать результаты чата:', exc)
  }
}

function addToPortfolio(item) {
  const monthNames = {
    1: 'Январь',
    2: 'Февраль',
    3: 'Март',
    4: 'Апрель',
    5: 'Май',
    6: 'Июнь',
    7: 'Июль',
    8: 'Август',
    9: 'Сентябрь',
    10: 'Октябрь',
    11: 'Ноябрь',
    12: 'Декабрь'
  }
  const prices = item.monthly_prices || {}
  const statuses = item.monthly_statuses || {}
  const availableMonth = Object.keys(statuses).find(
    month => String(statuses[month]).toUpperCase() === 'FREE'
  )
  const monthFull = monthNames[availableMonth]

  if (!monthFull) {
    router.push('/portfolio')
    return
  }

  const displayStatuses = Object.fromEntries(
    Object.entries(statuses).map(([key, value]) => {
      const normalized = String(value || '').toUpperCase()
      const label =
        normalized === 'FREE'
          ? 'Свободно'
          : normalized === 'RESERVED'
            ? 'Резерв'
            : normalized === 'PENDING'
              ? 'На утверждении'
              : normalized === 'SOLD' || normalized === 'LOAD'
                ? 'Занято'
                : String(value || '')
      return [monthNames[key] || key, label]
    })
  )

  toggleMonth(
    {
      ...item,
      type: item.type || item.media_type,
      month_prices: Object.fromEntries(
        Object.entries(prices).map(([key, value]) => [
          monthNames[key] || key,
          value
        ])
      ),
      statuses: displayStatuses,
      months: Object.fromEntries(
        Object.entries(item.month_texts || {}).map(([key, value]) => [
          monthNames[key] || key,
          value || displayStatuses[monthNames[key] || key] || ''
        ])
      )
    },
    monthFull,
    prices[availableMonth]
  )
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: min(720px, 88vw);
}
.chat-title {
  color: #17212b;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 1.5px;
}
.chat-messages {
  max-height: 300px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chat-empty,
.chat-warning {
  color: #71808c;
  font-size: 13px;
}
.chat-message-user {
  align-self: flex-end;
}
.chat-message-assistant {
  align-self: flex-start;
}
.chat-bubble {
  max-width: 90%;
  padding: 9px 12px;
  border-radius: 10px;
  background: #f1f4f6;
  color: #17212b;
  white-space: pre-wrap;
}
.chat-message-user .chat-bubble {
  background: #17212b;
  color: #fff;
}
.chat-options,
.chat-input-actions,
.chat-result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chat-result {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px;
  border: 1px solid #e5e9ec;
  border-radius: 10px;
}
.chat-result-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}
.chat-input textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid #dce2e6;
  border-radius: 10px;
  padding: 10px;
  font: inherit;
}
.chat-input-actions {
  justify-content: flex-end;
  margin-top: 7px;
}
@media (max-width: 650px) {
  .chat-panel {
    min-width: min(92vw, 480px);
  }
  .chat-result {
    flex-direction: column;
  }
}
</style>
