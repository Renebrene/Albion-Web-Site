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

  /*
   * Активный запрос ответа: нужен кнопке «Стоп» и сбросу, чтобы прервать
   * ожидание, а не блокировать чат до перезагрузки страницы.
   */
  let activeController = null
  let stopRequested = false

  function invalidate() {
    generation += 1
    loading.value = false
    stopRequested = false
    activeController?.abort()
    activeController = null
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

      /*
       * lastResponse отдельно не храним: он дублирует последний ответ
       * ассистента и раздувает sessionStorage. Собираем обратно из
       * сообщений — данные там те же.
       */
      lastResponse.value = lastResponseFromMessages()
    } catch {
      sessionId.value = null
      messages.value = []
      lastResponse.value = null
    }
  }

  /* Ответ последнего успешного сообщения ассистента — из истории. */
  function lastResponseFromMessages() {
    for (let index = messages.value.length - 1; index >= 0; index -= 1) {
      const message = messages.value[index]

      if (message?.role !== 'assistant' || message.error) {
        continue
      }

      return {
        session_id: sessionId.value,
        answer: message.text,
        pending: message.pending,
        clarification: message.clarification,
        results: message.results,
        suggestions: message.suggestions,
        actions: message.actions,
        query: message.query,
        warnings: message.warnings
      }
    }

    return null
  }

  /*
   * Облегчённый снимок: результаты поиска (позиции с фото и ссылками)
   * тяжёлые, а sessionStorage ограничен. При переполнении оставляем их
   * только у последнего ответа, вместо того чтобы молча перестать
   * сохранять чат вовсе.
   */
  function messagesForStorage() {
    const slice = messages.value.slice(-50)

    let lastWithResults = -1

    for (let index = slice.length - 1; index >= 0; index -= 1) {
      if (slice[index]?.results) {
        lastWithResults = index
        break
      }
    }

    return slice.map((message, index) =>
      index === lastWithResults ? message : { ...message, results: undefined }
    )
  }

  function persist() {
    const base = {
      version: STORAGE_VERSION,
      sessionId: sessionId.value
    }

    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({ ...base, messages: messages.value.slice(-50) })
      )
    } catch {
      /* Квота: пробуем снимок без тяжёлых результатов в старых ответах. */
      try {
        sessionStorage.setItem(
          storageKey,
          JSON.stringify({ ...base, messages: messagesForStorage() })
        )
      } catch {
        // Private browsing or disabled storage should not break chat.
      }
    }

    try {
      // Старый ключ без версии больше не нужен.
      sessionStorage.removeItem('albion_smart_chat')
    } catch {
      /* storage может быть недоступен */
    }
  }

  restore()

  async function send(message, context = {}) {
    const text = String(message || '').trim()
    if (!text || loading.value) return null

    const requestGeneration = generation
    const controller = new AbortController()

    error.value = ''
    loading.value = true
    stopRequested = false
    activeController = controller
    messages.value.push({ role: 'user', text })

    /* Индекс оптимистичного сообщения: при отмене откатываем его. */
    const messageIndex = messages.value.length - 1

    try {
      const response = await sendChatMessage(
        {
          session_id: sessionId.value,
          request_id:
            typeof crypto?.randomUUID === 'function'
              ? crypto.randomUUID()
              : undefined,
          message: text,
          context,
          chat_key: key
        },
        controller.signal
      )

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

      /*
       * Пользователь нажал «Стоп»: считаем, что сообщение не отправлено, —
       * убираем его из ленты. Текст в поле вернёт панель ввода (send
       * возвращает null так же, как при ошибке).
       */
      if (stopRequested || exc?.code === 'aborted') {
        if (messages.value[messageIndex]?.role === 'user') {
          messages.value.splice(messageIndex, 1)
        }

        return null
      }

      error.value =
        exc?.code === 'timeout'
          ? 'Помощник не ответил вовремя. Попробуйте ещё раз.'
          : exc?.message || 'Не удалось обратиться к помощнику.'

      messages.value.push({
        role: 'assistant',
        text: `Ошибка: ${error.value}`,
        error: true
      })
      persist()

      /*
       * После таймаута сообщение пользователя остаётся в истории: запрос
       * мог дойти до сервера. Текст в поле ввода не возвращаем, иначе он
       * задвоится, — панель отличает таймаут от прочих ошибок по результату.
       */
      return exc?.code === 'timeout' ? { timedOut: true } : null
    } finally {
      if (activeController === controller) {
        activeController = null
      }

      if (generation === requestGeneration) {
        loading.value = false
      }
    }
  }

  /* Пользователь прервал ожидание ответа (кнопка «Стоп»). */
  function stop() {
    if (!loading.value || !activeController) {
      return
    }

    stopRequested = true
    activeController.abort()
  }

  async function reset() {
    generation += 1
    const resetGeneration = generation
    const activeSession = sessionId.value

    /* Незавершённый ответ уже не нужен: прерываем запрос. */
    stopRequested = false
    activeController?.abort()
    activeController = null

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
    stop,
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
