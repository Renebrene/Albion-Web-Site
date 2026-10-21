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

  /*
   * Поколение состояния: reset/dispose/hydrate увеличивают его, чтобы
   * поздний ответ старого запроса не воскресил очищенный чат.
   */
  let generation = 0

  function invalidate() {
    generation += 1
    loading.value = false
  }

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

    const requestGeneration = generation

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

      /* Чат очистили/пересоздали, пока шёл запрос — ответ уже не нужен. */
      if (generation !== requestGeneration) {
        return null
      }

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
      if (generation !== requestGeneration) {
        return null
      }

      error.value = exc?.message || 'Не удалось обратиться к помощнику.'
      messages.value.push({
        role: 'assistant',
        text: `Ошибка: ${error.value}`,
        error: true
      })
      persist()
      return null
    } finally {
      if (generation === requestGeneration) {
        loading.value = false
      }
    }
  }

  async function reset() {
    generation += 1
    const resetGeneration = generation
    const activeSession = sessionId.value

    /* Блокируем новые отправки, пока чистим серверную сессию. */
    loading.value = true

    if (activeSession) {
      try {
        await resetChat(activeSession)
      } catch {
        // Local reset remains useful when the server session has expired.
      }
    }

    /* Пока ждали сервер, чат могли сбросить/пересоздать ещё раз. */
    if (generation !== resetGeneration) {
      return
    }

    sessionId.value = null
    messages.value = []
    lastResponse.value = null
    error.value = ''
    loading.value = false
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
    persist,
    invalidate
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

  /* Старый in-flight ответ не должен перезаписать восстановленный чат. */
  store.invalidate()

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

  /* Поздний ответ по удалённому чату не должен снова его сохранить. */
  registry.get(key)?.invalidate()

  try {
    sessionStorage.removeItem(storageKey)
  } catch {
    /* storage может быть недоступен */
  }

  registry.delete(key)
}
