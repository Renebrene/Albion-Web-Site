<template>
  <q-page class="administration-dashboard">
    <div class="dashboard-container">
      <header class="dashboard-header">
        <div>
          <!-- Логотип как на публичном сайте; клик — переход на сайт -->
          <RouterLink
            to="/"
            class="dashboard-brand"
            title="Перейти на сайт"
            aria-label="Albion — перейти на сайт"
          >
            <img src="/logo.png" alt="Albion" class="dashboard-brand-logo" />
          </RouterLink>
          <h1>Администрирование</h1>
          <p v-if="user" class="dashboard-user">
            {{ user.name || user.login }}
          </p>
        </div>

        <div class="dashboard-tools">
          <button
            type="button"
            class="dashboard-tool"
            :class="{ active: reorderMode }"
            :title="'Режим перемещения плиток'"
            @click="toggleReorder"
          >
            Перемещение
          </button>

          <button
            type="button"
            class="dashboard-tool"
            :class="{ active: renameMode }"
            title="Режим переименования плиток"
            @click="toggleRename"
          >
            Названия
          </button>

          <template v-if="editMode">
            <button type="button" class="dashboard-tool" @click="resetLayout">
              Сбросить
            </button>

            <button type="button" class="dashboard-tool" @click="cancelEdit">
              Отменить
            </button>

            <button
              type="button"
              class="dashboard-tool dashboard-tool--save"
              :disabled="saving || !dirty"
              @click="saveLayout"
            >
              {{ saving ? 'Сохраняем…' : 'Сохранить' }}
            </button>
          </template>

          <q-btn
            flat
            no-caps
            label="Выйти"
            :loading="loggingOut"
            @click="logout"
          />
        </div>
      </header>

      <p v-if="layoutError" class="dashboard-layout-error">
        {{ layoutError }}
      </p>

      <div v-if="loading" class="dashboard-loading">
        <q-spinner size="32px" />
      </div>

      <div v-else-if="error" class="dashboard-error">
        {{ error }}
      </div>

      <template v-else>
        <p v-if="renameMode" class="dashboard-hint">
          Измените названия и описания плиток, затем нажмите «Сохранить».
        </p>
        <p v-else-if="reorderMode" class="dashboard-hint">
          Перетащите плитки за значок ⠿ в нужном порядке, затем нажмите
          «Сохранить».
        </p>

        <section class="dashboard-grid" :class="{ 'is-editing': editMode }">
          <q-card
            v-for="(item, index) in items"
            :key="item.path"
            flat
            bordered
            class="dashboard-card"
            :class="{
              'is-dragging': draggingIndex === index,
              'is-drop':
                reorderMode && dropIndex === index && draggingIndex !== index
            }"
            @dragover.prevent="onDragOver(index)"
            @drop.prevent="onDrop(index)"
            @click="openCard(item)"
          >
            <!-- Значок раздела: ч.б. бейдж в правом нижнем углу плитки -->
            <span
              v-if="item.icon && !renameMode"
              class="tile-icon"
              aria-hidden="true"
            >
              <img v-if="isMediaIcon(item.icon)" :src="item.icon" alt="" />
              <svg
                v-else
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  v-for="(path, pathIndex) in presetIcon(item.icon).paths"
                  :key="pathIndex"
                  :d="path"
                />
              </svg>
            </span>

            <!-- Ручка перетаскивания видна только в режиме перемещения -->
            <span
              v-if="reorderMode"
              class="drag-handle"
              draggable="true"
              title="Перетащить"
              aria-label="Перетащить плитку"
              @dragstart="onDragStart($event, index)"
              @dragend="onDragEnd"
            >
              ⠿
            </span>

            <q-card-section>
              <input
                v-if="renameMode"
                v-model="item.title"
                class="dashboard-input dashboard-input--title"
                type="text"
                placeholder="Название"
                maxlength="60"
                @click.stop
              />

              <div v-else class="dashboard-card-title">
                {{ item.title }}
              </div>

              <textarea
                v-if="renameMode"
                v-model="item.text"
                class="dashboard-input dashboard-input--text"
                rows="2"
                maxlength="160"
                placeholder="Описание"
                @click.stop
              ></textarea>

              <div v-else class="dashboard-card-text">
                {{ item.text }}
              </div>

              <!-- Выбор значка раздела (только в режиме «Названия») -->
              <div v-if="renameMode" class="tile-icon-picker" @click.stop>
                <div class="tile-icon-grid">
                  <button
                    type="button"
                    class="tile-icon-choice"
                    :class="{ active: !item.icon }"
                    title="Без значка"
                    @click="item.icon = ''"
                  >
                    —
                  </button>

                  <button
                    v-for="preset in PRESET_ICONS"
                    :key="preset.key"
                    type="button"
                    class="tile-icon-choice"
                    :class="{ active: item.icon === preset.key }"
                    :title="preset.label"
                    @click="item.icon = preset.key"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.8"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        v-for="(path, pathIndex) in preset.paths"
                        :key="pathIndex"
                        :d="path"
                      />
                    </svg>
                  </button>

                  <button
                    type="button"
                    class="tile-icon-choice tile-icon-choice--media"
                    title="Медиатека"
                    @click="openMediaPicker(item)"
                  >
                    <q-icon name="add_photo_alternate" size="18px" />
                  </button>

                  <button
                    type="button"
                    class="tile-icon-choice tile-icon-choice--media"
                    title="Загрузить"
                    @click="triggerIconUpload(item)"
                  >
                    <q-icon name="upload" size="18px" />
                  </button>
                </div>
              </div>
            </q-card-section>
          </q-card>
        </section>

        <!-- Выбор картинки-значка из медиатеки -->
        <MediaPicker v-model="mediaPickerOpen" @select="onMediaIconPicked" />
      </template>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import MediaPicker from '../components/admin/MediaPicker.vue'
import { uploadAdminMedia } from '../services/adminMedia'
import { MEDIA_SECTION, mediaCategoryId } from '../composables/useMediaCategory'
import {
  adminFetch,
  clearAdminToken,
  getAdminToken
} from '../services/adminApi'

const router = useRouter()

const user = ref(null)
const loading = ref(true)
const loggingOut = ref(false)
const error = ref('')
const layoutError = ref('')

/*
 * Каталог плиток — источник истины: какие разделы вообще существуют и их
 * значения по умолчанию. Порядок и переименования хранятся на сервере
 * (/api/admin/dashboard) и накладываются поверх каталога. Так новые плитки,
 * добавленные в код, появляются автоматически, а сохранённые правки им не
 * мешают.
 */
const CATALOG = [
  {
    title: 'Конструкции',
    text: 'Рекламная сеть и данные конструкций',
    path: '/administration/constructions'
  },
  {
    title: 'Обновление базы',
    text: 'Загрузка Excel, обновление и архивы конструкций',
    path: '/administration/base'
  },
  {
    title: 'Бекап сайта',
    text: 'Резервные копии новостей, страниц, настроек и медиа сайта',
    path: '/administration/site'
  },
  {
    title: 'Главная страница',
    text: 'Вертикальные слайды и карточки верхнего слайда',
    path: '/administration/home'
  },
  {
    title: 'Информация',
    text: 'Закладки страницы «Информация»: состав и содержание',
    path: '/administration/info'
  },
  {
    title: 'Новости',
    text: 'Публикации и категории новостей',
    path: '/administration/news'
  },
  {
    title: 'О компании',
    text: 'Тексты, блоки, статистика и направления',
    path: '/administration/about'
  },
  {
    title: 'Контакты',
    text: 'Офисы, разделы и сотрудники',
    path: '/administration/contacts'
  },
  {
    title: 'Медиа Хранилище',
    text: 'Изображения и другие файлы сайта',
    path: '/administration/media'
  },
  {
    title: 'Меню и подвал',
    text: 'Пункты верхнего меню и подвала сайта',
    path: '/administration/site-menu'
  },
  {
    title: 'Настройки',
    text: 'Карта (оператор), внешний вид сайта: шрифты, цвета, скругления',
    path: '/administration/settings'
  },
  {
    title: 'SEO',
    text: 'Заголовки и описания страниц, ключевые слова для поиска',
    path: '/administration/seo'
  },
  {
    title: 'Пользователи',
    text: 'Учетные записи и права доступа',
    path: '/administration/users'
  },
  {
    title: 'Журнал действий',
    text: 'История изменений в административной панели',
    path: '/administration/audit'
  },
  {
    title: 'Журнал чата',
    text: 'Запросы и ответы умного чата: текст, дата и время',
    path: '/administration/chat-log'
  },
  {
    title: 'Статистика',
    text: 'Посещаемость страниц и география',
    path: '/administration/statistics'
  }
]

/*
 * Значки по умолчанию для разделов — чтобы плитки не были «пустыми» сразу.
 * Админ может поменять значок или убрать его в режиме «Названия».
 */
const DEFAULT_ICONS = {
  '/administration/constructions': 'billboard',
  '/administration/base': 'database',
  '/administration/site': 'clock',
  '/administration/home': 'home',
  '/administration/info': 'info',
  '/administration/news': 'news',
  '/administration/about': 'briefcase',
  '/administration/contacts': 'pin',
  '/administration/media': 'image',
  '/administration/site-menu': 'menu',
  '/administration/settings': 'gear',
  '/administration/seo': 'search',
  '/administration/users': 'users',
  '/administration/audit': 'list',
  '/administration/chat-log': 'message',
  '/administration/statistics': 'chart'
}

/*
 * Набор значков на выбор (инлайновые SVG, без ассетов). Ключ значка
 * сохраняется в раскладке; рядом с названием плитки рисуется либо такой
 * SVG, либо загруженная из медиатеки картинка (см. isMediaIcon).
 */
const PRESET_ICONS = [
  {
    key: 'billboard',
    label: 'Рекламная конструкция',
    paths: ['M3 5h18v10H3z', 'M8 15v6', 'M16 15v6']
  },
  {
    key: 'gear',
    label: 'Настройки',
    paths: [
      'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
      'M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z'
    ]
  },
  {
    key: 'search',
    label: 'SEO и поиск',
    paths: ['M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z', 'M21 21l-4.35-4.35']
  },
  {
    key: 'globe',
    label: 'Страницы сайта',
    paths: [
      'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
      'M2 12h20',
      'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'
    ]
  },
  {
    key: 'database',
    label: 'База данных',
    paths: [
      'M21 5c0 1.66-4 3-9 3s-9-1.34-9-3 4-3 9-3 9 1.34 9 3z',
      'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5',
      'M3 12c0 1.66 4 3 9 3s9-1.34 9-3'
    ]
  },
  {
    key: 'news',
    label: 'Новости',
    paths: ['M4 5h12v14H4z', 'M16 8h4v9a2 2 0 0 1-2 2', 'M7 9h6M7 13h6M7 16h4']
  },
  {
    key: 'image',
    label: 'Медиа',
    paths: ['M3 3h18v18H3z', 'M3 16l5-5 4 4 3-3 6 6', 'M8.5 9.5h.01']
  },
  {
    key: 'home',
    label: 'Главная',
    paths: ['M3 10l9-7 9 7v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z', 'M9 21v-7h6v7']
  },
  {
    key: 'users',
    label: 'Пользователи',
    paths: [
      'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2',
      'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
      'M23 21v-2a4 4 0 0 0-3-3.87',
      'M16 3.13a4 4 0 0 1 0 7.75'
    ]
  },
  {
    key: 'chart',
    label: 'Статистика',
    paths: ['M3 3v18h18', 'M8 17v-5', 'M13 17V8', 'M18 17v-9']
  },
  {
    key: 'info',
    label: 'Информация',
    paths: [
      'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
      'M12 16v-5',
      'M12 8h.01'
    ]
  },
  {
    key: 'pin',
    label: 'Контакты',
    paths: [
      'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z',
      'M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'
    ]
  },
  {
    key: 'clock',
    label: 'Журнал',
    paths: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z', 'M12 7v5l3 2']
  },
  {
    key: 'message',
    label: 'Чат',
    paths: ['M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z']
  },
  {
    key: 'briefcase',
    label: 'Компания',
    paths: [
      'M3 7h18v13H3z',
      'M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2',
      'M3 12h18'
    ]
  },
  {
    key: 'menu',
    label: 'Меню',
    paths: ['M3 6h18M3 12h18M3 18h18']
  },
  {
    key: 'list',
    label: 'Журнал',
    paths: ['M8 6h13M8 12h13M8 18h13', 'M3 6h.01M3 12h.01M3 18h.01']
  }
]

function presetIcon(key) {
  return PRESET_ICONS.find(preset => preset.key === key) || null
}

// Значок — картинка из медиатеки (URL), если это не ключ из набора.
function isMediaIcon(key) {
  return Boolean(key) && !presetIcon(key)
}

/* Текущее состояние плиток; порядок массива = порядок на странице. */
const items = ref([])

/* Снимок сохранённого состояния: кнопка «Сохранить» активна, только если
   что-то изменилось. */
const savedState = ref('')

const reorderMode = ref(false)
const renameMode = ref(false)
const saving = ref(false)

const draggingIndex = ref(null)
const dropIndex = ref(null)

/* Медиатека для выбора значка-картинки: какой плитке назначаем. */
const mediaPickerOpen = ref(false)
const mediaTargetPath = ref('')

const editMode = computed(() => reorderMode.value || renameMode.value)

/* Каталог + сохранённые переопределения -> плитки в нужном порядке.
   Плитки, которых нет в сохранённом порядке (новые разделы), идут в конец. */
function buildItems(order, overrides) {
  const byPath = new Map(CATALOG.map(section => [section.path, section]))
  const result = []

  const take = path => {
    const base = byPath.get(path)

    if (!base) return

    const patch = overrides[path] || {}
    const defaultIcon = DEFAULT_ICONS[base.path] || ''

    result.push({
      path: base.path,
      defaultTitle: base.title,
      defaultText: base.text,
      defaultIcon,
      title: typeof patch.title === 'string' ? patch.title : base.title,
      text: typeof patch.text === 'string' ? patch.text : base.text,
      // Значок: ключ из набора или URL картинки; '' — явное «без значка».
      icon: typeof patch.icon === 'string' ? patch.icon : defaultIcon
    })

    byPath.delete(path)
  }

  order.forEach(take)
  byPath.forEach(section => take(section.path))

  return result
}

function stateSnapshot() {
  return JSON.stringify(
    items.value.map(item => [item.path, item.title, item.text, item.icon])
  )
}

const dirty = computed(
  () => items.value.length > 0 && stateSnapshot() !== savedState.value
)

function setSaved() {
  savedState.value = stateSnapshot()
}

async function loadLayout() {
  try {
    const response = await adminFetch('/api/admin/dashboard')

    if (!response.ok) {
      throw new Error()
    }

    const data = await response.json()

    items.value = buildItems(data.order || [], data.items || {})
  } catch {
    // Нет сохранённой раскладки (или сервер недоступен) — каталог по умолчанию.
    items.value = buildItems([], {})
  }

  setSaved()
}

function toggleReorder() {
  reorderMode.value = !reorderMode.value
  layoutError.value = ''
}

function toggleRename() {
  renameMode.value = !renameMode.value
  layoutError.value = ''
}

function openCard(item) {
  // В режиме редактирования клик по плитке не уводит на раздел.
  if (editMode.value) return

  router.push(item.path)
}

// ----------------------------------------------------- значок раздела

function openMediaPicker(item) {
  mediaTargetPath.value = item.path
  mediaPickerOpen.value = true
}

function onMediaIconPicked(payload) {
  const target = items.value.find(entry => entry.path === mediaTargetPath.value)

  if (target && payload?.url) {
    target.icon = payload.url
  }

  mediaTargetPath.value = ''
}

/* Загрузка иконки с компьютера: файл уходит в медиатеку, ставим его URL. */
function triggerIconUpload(item) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'

  input.onchange = async () => {
    const file = input.files && input.files[0]
    if (!file) return

    try {
      const categoryId = await mediaCategoryId(MEDIA_SECTION.tiles)
      const media = await uploadAdminMedia(file, { categoryId })
      item.icon = media.url
      error.value = ''
    } catch (exc) {
      error.value = String(exc.message || exc)
    }
  }

  input.click()
}

// ----------------------------------------------------- перетаскивание

function onDragStart(event, index) {
  if (!reorderMode.value) return

  draggingIndex.value = index

  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))

    // Тянем за ручку, но «призрак» рисуем по всей плитке.
    const card = event.target.closest('.dashboard-card')

    if (card) {
      event.dataTransfer.setDragImage(card, 24, 24)
    }
  }
}

function onDragOver(index) {
  if (reorderMode.value && draggingIndex.value !== null) {
    dropIndex.value = index
  }
}

function onDrop(index) {
  const from = draggingIndex.value

  draggingIndex.value = null
  dropIndex.value = null

  if (from === null || from === index) return

  const next = [...items.value]
  const [moved] = next.splice(from, 1)

  next.splice(index, 0, moved)
  items.value = next
}

function onDragEnd() {
  draggingIndex.value = null
  dropIndex.value = null
}

// ----------------------------------------------------- сохранение

function resetLayout() {
  items.value = buildItems([], {})
}

function cancelEdit() {
  reorderMode.value = false
  renameMode.value = false
  layoutError.value = ''
  loadLayout()
}

async function saveLayout() {
  saving.value = true
  layoutError.value = ''

  const order = items.value.map(item => item.path)
  const overrides = {}

  for (const item of items.value) {
    const patch = {}

    if (item.title !== item.defaultTitle) patch.title = item.title
    if (item.text !== item.defaultText) patch.text = item.text
    if (item.icon !== item.defaultIcon) patch.icon = item.icon

    if (Object.keys(patch).length) {
      overrides[item.path] = patch
    }
  }

  try {
    const response = await adminFetch('/api/admin/dashboard', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order, items: overrides })
    })

    if (!response.ok) {
      throw new Error()
    }

    const data = await response.json()

    items.value = buildItems(data.order || order, data.items || overrides)
    setSaved()

    reorderMode.value = false
    renameMode.value = false
  } catch {
    layoutError.value = 'Не удалось сохранить расположение. Попробуйте ещё раз.'
  } finally {
    saving.value = false
  }
}

// ----------------------------------------------------- авторизация

async function loadUser() {
  const token = getAdminToken()

  if (!token) {
    await router.replace('/administration')
    return
  }

  try {
    const response = await adminFetch('/api/admin/me')

    if (!response.ok) {
      clearAdminToken()
      await router.replace('/administration')
      return
    }

    const data = await response.json()
    user.value = data.user
  } catch {
    error.value = 'Не удалось проверить авторизацию'
  } finally {
    loading.value = false
  }
}

async function logout() {
  const token = getAdminToken()

  loggingOut.value = true

  try {
    if (token) {
      await adminFetch('/api/admin/logout', { method: 'POST' })
    }
  } finally {
    clearAdminToken()
    await router.replace('/administration')
    loggingOut.value = false
  }
}

onMounted(async () => {
  await loadUser()

  if (user.value) {
    await loadLayout()
  }
})
</script>

<style scoped>
.administration-dashboard {
  min-height: 100vh;
  padding: 32px 24px;
}

.dashboard-container {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 32px;
}

.dashboard-brand {
  display: inline-flex;
  align-items: center;

  margin-bottom: 12px;
}

.dashboard-brand-logo {
  display: block;

  width: auto;
  height: 42px;

  max-width: 150px;
}

.dashboard-header h1 {
  margin: 0;
  font-size: 32px;
  line-height: 1.15;
}

.dashboard-user {
  margin: 8px 0 0;
  color: #6b7280;
}

/* --------------------------------------------------------- инструменты */

.dashboard-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.dashboard-tool {
  height: 36px;
  padding: 0 14px;

  border: 1px solid #d7dde3;
  border-radius: 10px;

  background: #fff;
  color: #374151;

  font-size: 13px;
  font-weight: 600;

  cursor: pointer;

  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.dashboard-tool:hover:not(:disabled) {
  background: #f3f5f7;
}

.dashboard-tool.active {
  background: #17212b;
  border-color: #17212b;
  color: #fff;
}

.dashboard-tool--save {
  background: var(--albion-accent);
  border-color: var(--albion-accent);
  color: #fff;
}

.dashboard-tool--save:hover:not(:disabled) {
  filter: brightness(1.05);
}

.dashboard-tool:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.dashboard-hint {
  margin: 0 0 16px;
  color: #6b7280;
  font-size: 13px;
}

.dashboard-layout-error {
  margin: 0 0 16px;
  color: #c62828;
  font-size: 13px;
}

/* --------------------------------------------------------- сетка */

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.dashboard-card {
  position: relative;
  min-height: 150px;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.dashboard-grid.is-editing .dashboard-card {
  cursor: default;
}

.dashboard-grid.is-editing .dashboard-card:hover {
  transform: none;
  box-shadow: none;
}

.dashboard-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

/* Ручка перетаскивания */
.drag-handle {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 2;

  width: 28px;
  height: 28px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px;

  background: #eef1f4;
  color: #5b6b76;

  font-size: 16px;
  line-height: 1;

  cursor: grab;
  user-select: none;
}

.drag-handle:active {
  cursor: grabbing;
}

.dashboard-card.is-dragging {
  opacity: 0.45;
}

.dashboard-card.is-drop {
  outline: 2px dashed var(--albion-accent);
  outline-offset: 2px;
}

.dashboard-card-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 10px;
}

.dashboard-card-text {
  color: #6b7280;
  line-height: 1.5;
}

/* Значок раздела: ч.б. бейдж в правом нижнем углу плитки */
.tile-icon {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 1;

  width: 30px;
  height: 30px;

  display: flex;
  align-items: center;
  justify-content: center;

  border-radius: 8px;

  background: rgba(23, 33, 43, 0.05);

  color: #17212b;
}

.tile-icon svg {
  display: block;

  width: 22px;
  height: 22px;
}

.tile-icon img {
  display: block;

  width: 22px;
  height: 22px;

  object-fit: contain;

  /* Картинка из медиатеки — чёрно-белая */
  filter: grayscale(1);
}

/* Выбор значка раздела (режим «Названия») */
.tile-icon-picker {
  margin-top: 12px;
  padding-top: 10px;

  border-top: 1px dashed #e2e6ea;
}

.tile-icon-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tile-icon-choice {
  width: 30px;
  height: 30px;
  padding: 0;

  display: inline-flex;
  align-items: center;
  justify-content: center;

  border: 1px solid #d7dde3;
  border-radius: 8px;

  background: #fff;
  color: #47525c;

  font-size: 14px;
  line-height: 1;

  cursor: pointer;
}

.tile-icon-choice svg {
  width: 17px;
  height: 17px;
}

.tile-icon-choice:hover {
  background: #f3f5f7;
}

.tile-icon-choice.active {
  background: #17212b;
  border-color: #17212b;
  color: #fff;
}

.tile-icon-choice--media {
  border-style: dashed;
  color: #47525c;
}

/* Поля переименования */
.dashboard-input {
  display: block;
  width: 100%;
  box-sizing: border-box;

  padding: 8px 10px;

  border: 1px solid #cfd7de;
  border-radius: 8px;

  background: #fff;
  color: #17212b;

  font-family: inherit;
}

.dashboard-input:focus {
  outline: none;
  border-color: var(--albion-accent);
}

.dashboard-input--title {
  margin-bottom: 8px;

  font-size: 16px;
  font-weight: 700;
}

.dashboard-input--text {
  min-height: 56px;

  font-size: 13px;
  line-height: 1.4;

  resize: vertical;
}

.dashboard-loading {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}

.dashboard-error {
  padding: 20px;
  color: #c62828;
  background: #fff;
  border-radius: 12px;
}

@media (max-width: 1000px) {
  .dashboard-header {
    flex-direction: column;
  }

  .dashboard-tools {
    justify-content: flex-start;
  }

  .dashboard-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 600px) {
  .administration-dashboard {
    padding: 20px 16px;
  }

  .dashboard-header h1 {
    font-size: 26px;
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-card {
    min-height: auto;
  }
}
</style>
