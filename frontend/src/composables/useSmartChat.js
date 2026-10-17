import { computed, ref } from 'vue'

import { resetChat, sendChatMessage } from '../services/chatApi'

/*
 * Версия схемы хранения: при изменении формата ответа старые сохранённые
 * результаты (например, с устаревшей занятостью) не восстанавливаются.
 */
const STORAGE_VERSION = 2

/*
 * Чат — не singleton: в большом окне может быть несколько независимых
 * чатиков. Состояние хранится по ключу (chatKey).
 */
const registry = new Map()

function createStore(key) {
  const storageKey = `albion_smart_chat_v${STORAGE_VERSION}_${key}`

  const sessionId = ref(null)
  const messages = ref([])
  const lastResponse = ref(null)
  const loading = ref(false)
  const error = ref('')

  function restore() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || '{}')

      if (saved.version !== STORAGE_VERSION) {
        sessionId.value = null
        messages.value = []
        lastResponse.value = null
        return
      }

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
        storageKey,
        JSON.stringify({
          version: STORAGE_VERSION,
          sessionId: sessionId.value,
          messages: messages.value.slice(-50),
          lastResponse: lastResponse.value
        })
      )

      // Старый ключ без версии больше не нужен.
      sessionStorage.removeItem('albion_smart_chat')
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
        context,
        chat_key: key
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
        query: response.query,
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

  return {
    sessionId,
    messages,
    lastResponse,
    results: computed(() => lastResponse.value?.results?.items || []),
    loading,
    error,
    send,
    reset,
    persist
  }
}

export function useSmartChat(key = 'default') {
  if (!registry.has(key)) {
    registry.set(key, createStore(key))
  }

  return registry.get(key)
}

/* Текстовый снимок чата — для сохранения в личном кабинете. */
export function chatSnapshot(key) {
  const store = useSmartChat(key)

  return {
    sessionId: store.sessionId.value,
    messages: store.messages.value,
    lastResponse: store.lastResponse.value
  }
}

/* Восстановление чата из сохранённого снимка. */
export function hydrateChat(key, snapshot) {
  const store = useSmartChat(key)

  store.sessionId.value = snapshot?.sessionId || null
  store.messages.value = Array.isArray(snapshot?.messages)
    ? snapshot.messages
    : []
  store.lastResponse.value = snapshot?.lastResponse || null

  store.persist()
}

/*
 * Полное удаление чата из рабочего пространства: чистим и память (реестр),
 * и sessionStorage. Нужно кнопке «Очистить» — чаты исчезают из отображения
 * (в журнале на сервере текстовая история остаётся).
 */
export function disposeChat(key) {
  const storageKey = `albion_smart_chat_v${STORAGE_VERSION}_${key}`

  try {
    sessionStorage.removeItem(storageKey)
  } catch {
    /* storage может быть недоступен */
  }

  registry.delete(key)
}
