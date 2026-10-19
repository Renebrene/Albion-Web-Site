import { ref } from 'vue'

import { useAccount } from './useAccount'
import { chatSnapshot, disposeChat, hydrateChat } from './useSmartChat'

/*
 * Рабочее пространство чатов — общее для маленького окна (шапка) и
 * большого окна (страница /chat).
 *
 * Список чатов и их состояние (useSmartChat по ключу) — единый источник
 * истины: оба окна показывают одни и те же чаты, различается только
 * оформление (variant). Поэтому информация и количество чатов совпадают.
 */

const CHATS_KEY = 'albion_chat_workspace_chats'

function readStoredChats() {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(CHATS_KEY) || 'null')
    const stored = Array.isArray(parsed?.chats) ? parsed.chats : []

    const chats = stored
      .filter(chat => chat && chat.key)
      .map((chat, index) => ({
        key: String(chat.key),
        number: Number(chat.number) || index + 1,
        draft: ''
      }))

    const sequence = Math.max(
      Number(parsed?.sequence) || 0,
      ...chats.map(chat => chat.number),
      0
    )

    return { chats, sequence }
  } catch {
    return { chats: [], sequence: 0 }
  }
}

const storedChats = readStoredChats()
const chats = ref(storedChats.chats)
let sequence = storedChats.sequence
let loaded = false

function persistChats() {
  try {
    sessionStorage.setItem(
      CHATS_KEY,
      JSON.stringify({
        chats: chats.value.map(chat => ({
          key: chat.key,
          number: chat.number
        })),
        sequence
      })
    )
  } catch {
    /* приватный режим/переполнение — список проживёт до reload */
  }
}

const saving = ref(false)
const savedAt = ref('')
const saveError = ref('')

const { isAuthenticated, loadMe } = useAccount()

/*
 * id конструкций из последнего результата чата.
 *
 * Нужны странице рекламных возможностей: по ссылке /vozmozhnosti?chat=1 она
 * показывает на карте/в списке ровно эти результаты (см. AdvertisingPage).
 * Синглтон, как и остальное состояние рабочего пространства.
 */
const RESULT_IDS_KEY = 'albion_chat_result_ids'

function readStoredResultIds() {
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(RESULT_IDS_KEY) || '[]'
    )

    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const resultIds = ref(readStoredResultIds())

function setResultIds(ids) {
  resultIds.value = Array.isArray(ids) ? ids.slice() : []

  try {
    window.sessionStorage.setItem(
      RESULT_IDS_KEY,
      JSON.stringify(resultIds.value)
    )
  } catch {
    /* приватный режим/переполнение — фильтрация всё равно работает */
  }
}

/* Новый чат: свой ключ и порядковый номер (номер не теряется при сохранении). */
function addChat(draft = '') {
  sequence += 1

  // Уникальный ключ, а не chat-1: после reload старый чат с тем же ключом
  // не должен «подхватываться» новым чатом.
  const unique = globalThis.crypto?.randomUUID?.()
  const key = unique ? `chat-${unique}` : `chat-${Date.now()}-${sequence}`

  chats.value.push({
    key,
    number: sequence,
    draft
  })

  persistChats()
}

/* Гарантирует хотя бы один чат — нужно маленькому окну с полем ввода. */
function ensureFirst() {
  if (!chats.value.length) {
    addChat()
  }
}

function authHeaders() {
  const token = localStorage.getItem('albion_account_token')

  return token ? { Authorization: `Bearer ${token}` } : {}
}

/*
 * Сохранение в личный кабинет. Возвращает true при успехе.
 * Без авторизации ничего не делает (кнопка показывает тултип на хосте).
 */
async function saveChats() {
  if (!isAuthenticated.value) return false

  saving.value = true
  saveError.value = ''

  try {
    const body = {
      chats: chats.value.map(chat => ({
        key: chat.key,
        number: chat.number,
        ...chatSnapshot(chat.key)
      }))
    }

    const response = await fetch('/api/account/chats', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body)
    })

    if (!response.ok) {
      throw new Error(`Не удалось сохранить (${response.status})`)
    }

    savedAt.value = new Date().toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    })

    return true
  } catch (exc) {
    saveError.value = exc?.message || 'Не удалось сохранить чаты.'
    return false
  } finally {
    saving.value = false
  }
}

/* Восстановление сохранённых чатов: нумерация берётся из сохранённого. */
async function loadChats() {
  if (!isAuthenticated.value) return

  try {
    const response = await fetch('/api/account/chats', {
      headers: authHeaders()
    })

    if (!response.ok) return

    const data = await response.json()
    const saved = Array.isArray(data.chats) ? data.chats : []

    if (!saved.length) return

    chats.value = saved.map((chat, index) => ({
      key: chat.key || `chat-${index + 1}`,
      number: chat.number || index + 1,
      draft: ''
    }))

    sequence = chats.value.reduce((max, chat) => Math.max(max, chat.number), 0)
    persistChats()

    saved.forEach((chat, index) => {
      hydrateChat(chats.value[index].key, {
        sessionId: chat.sessionId,
        messages: chat.messages,
        lastResponse: chat.lastResponse
      })
    })
  } catch {
    /* восстановление не критично */
  }
}

/* Однократная инициализация: проверка авторизации и подъём сохранённых чатов. */
async function init() {
  if (loaded) return

  loaded = true
  await loadMe()
  await loadChats()
}

/*
 * Чтение сохранённых чатов ЛК БЕЗ гидратации рабочего пространства.
 * Нужно странице личного кабинета: показать, что сохранено, и дату.
 */
async function fetchSavedChats() {
  if (!isAuthenticated.value) {
    return { chats: [], updated_at: '' }
  }

  try {
    const response = await fetch('/api/account/chats', {
      headers: authHeaders()
    })

    if (!response.ok) {
      return { chats: [], updated_at: '' }
    }

    const data = await response.json()

    return {
      chats: Array.isArray(data.chats) ? data.chats : [],
      updated_at: data.updated_at || ''
    }
  } catch {
    return { chats: [], updated_at: '' }
  }
}

/*
 * Очищает сохранённые чаты ЛК (журнал чата не затрагивается).
 * Рабочее пространство в памяти не трогаем.
 */
async function clearSavedChats() {
  if (!isAuthenticated.value) return false

  try {
    const response = await fetch('/api/account/chats', {
      method: 'DELETE',
      headers: authHeaders()
    })

    return response.ok
  } catch {
    return false
  }
}

/* Открытие маленького окна: гарантированный первый чат + подъём данных. */
async function openWorkspace() {
  ensureFirst()
  await init()
}

/* ---------------------------------------------------------------- очистка */

/*
 * Кнопка «Очистить» работает с задержкой: после нажатия идёт таймер на
 * 10 секунд, в течение которых нажатие можно отменить (отжать). По истечении
 * чаты исчезают из отображения. Текстовая история остаётся в журнале чата
 * на сервере. Состояние общее для обоих окон.
 */
const CLEAR_DELAY = 10
const clearArmed = ref(false)
const clearSeconds = ref(0)
let clearTimer = null

function stopClearTimer() {
  if (clearTimer) {
    clearInterval(clearTimer)
    clearTimer = null
  }
}

function disarmClear() {
  clearArmed.value = false
  clearSeconds.value = 0
  stopClearTimer()
}

function armClear() {
  if (!chats.value.length) return

  clearArmed.value = true
  clearSeconds.value = CLEAR_DELAY
  stopClearTimer()

  clearTimer = setInterval(() => {
    clearSeconds.value -= 1

    if (clearSeconds.value <= 0) {
      disarmClear()
      clearChats()
    }
  }, 1000)
}

/* Нажатие кнопки: первый раз — взводим таймер, повторно — отменяем. */
function toggleClear() {
  if (clearArmed.value) {
    disarmClear()
  } else {
    armClear()
  }
}

/*
 * Очистка: чаты убираются из отображения (рабочее пространство) и из
 * сохранённого списка ЛК. Журнал чата (chat_turns) не затрагивается —
 * вопросы и ответы там остаются.
 */
async function clearChats() {
  chatKeys().forEach(key => disposeChat(key))

  chats.value = []
  sequence = 0
  persistChats()
  savedAt.value = ''
  saveError.value = ''
  disarmClear()
  setResultIds([])

  if (isAuthenticated.value) {
    try {
      await fetch('/api/account/chats', {
        method: 'DELETE',
        headers: authHeaders()
      })
    } catch {
      /* локальная очистка уже выполнена */
    }
  }
}

function chatKeys() {
  return chats.value.map(chat => chat.key)
}

export function useChatWorkspace() {
  return {
    chats,
    addChat,
    ensureFirst,
    init,
    openWorkspace,
    saveChats,
    fetchSavedChats,
    clearSavedChats,
    clearChats,
    toggleClear,
    clearArmed,
    clearSeconds,
    resultIds,
    setResultIds,
    isAuthenticated,
    saving,
    savedAt,
    saveError
  }
}
