import { computed, ref } from 'vue'

import { resetChat, sendChatMessage } from '../services/chatApi'

const STORAGE_KEY = 'albion_smart_chat'
const sessionId = ref(null)
const messages = ref([])
const lastResponse = ref(null)
const loading = ref(false)
const error = ref('')

function restore() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '{}')
    sessionId.value = saved.sessionId || null
    messages.value = Array.isArray(saved.messages) ? saved.messages : []
    lastResponse.value = saved.lastResponse || null
  } catch {
    sessionId.value = null
    messages.value = []
    lastResponse.value = null
  }
}

function persist() {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        sessionId: sessionId.value,
        messages: messages.value.slice(-50),
        lastResponse: lastResponse.value
      })
    )
  } catch {
    // Private browsing or disabled storage should not break chat.
  }
}

restore()

async function send(message, context = {}) {
  const text = String(message || '').trim()
  if (!text || loading.value) return null

  error.value = ''
  loading.value = true
  messages.value.push({ role: 'user', text })

  try {
    const response = await sendChatMessage({
      session_id: sessionId.value,
      request_id:
        typeof crypto?.randomUUID === 'function'
          ? crypto.randomUUID()
          : undefined,
      message: text,
      context
    })

    sessionId.value = response.session_id
    lastResponse.value = response
    messages.value.push({
      role: 'assistant',
      text: response.answer,
      pending: response.pending,
      clarification: response.clarification,
      results: response.results,
      suggestions: response.suggestions,
      actions: response.actions,
      warnings: response.warnings
    })
    persist()
    return response
  } catch (exc) {
    error.value = exc?.message || 'Не удалось обратиться к помощнику.'
    messages.value.push({
      role: 'assistant',
      text: `Ошибка: ${error.value}`,
      error: true
    })
    persist()
    return null
  } finally {
    loading.value = false
  }
}

async function reset() {
  if (sessionId.value) {
    try {
      await resetChat(sessionId.value)
    } catch {
      // Local reset remains useful when the server session has expired.
    }
  }
  sessionId.value = null
  messages.value = []
  lastResponse.value = null
  error.value = ''
  persist()
}

export function useSmartChat() {
  return {
    sessionId,
    messages,
    lastResponse,
    results: computed(() => lastResponse.value?.results?.items || []),
    loading,
    error,
    send,
    reset
  }
}
