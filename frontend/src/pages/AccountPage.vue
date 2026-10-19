<template>
  <q-page class="account-page">
    <div class="account-wrap">
      <!-- ЗАГОЛОВОК -->
      <div class="page-head">
        <div class="eyebrow">ALBION</div>
        <h1>Личный кабинет</h1>
        <p>Сохранённые портфели и чаты, доступ к сервисам компании</p>
      </div>

      <!-- ============================================================
           АВТОРИЗОВАН
      ============================================================ -->
      <template v-if="isAuthenticated">
        <section class="profile-card">
          <div class="profile-main">
            <div class="profile-avatar">
              {{ avatarLetter }}
            </div>
            <div class="profile-info">
              <div class="profile-login">{{ account?.login }}</div>
              <div class="profile-role">Роль: {{ roleLabel }}</div>
            </div>
          </div>

          <div class="profile-actions">
            <!-- Вход в админку — только для аккаунтов с ролью администратора.
                 Ведёт на отдельную форму входа /administration. -->
            <q-btn
              v-if="isAdmin"
              unelevated
              no-caps
              class="admin-btn"
              label="Админка"
              icon="admin_panel_settings"
              to="/administration"
            />

            <q-btn
              outline
              no-caps
              class="logout-btn"
              label="Выйти"
              :loading="loading"
              @click="handleLogout"
            />
          </div>
        </section>

        <Transition name="fade">
          <div v-if="error" class="message message-error">{{ error }}</div>
        </Transition>

        <!-- ============================================================
             СОХРАНЁННОЕ: ПОРТФЕЛИ И ЧАТЫ С ФИЛЬТРОМ
        ============================================================ -->
        <section v-if="!isAdmin" class="requests-card saved-card">
          <div class="section-head">
            <div class="section-title">
              Сохранённое
              <span v-if="accountTitle" class="section-subtitle">
                «{{ accountTitle }}»
              </span>
            </div>

            <div class="saved-actions">
              <q-btn
                v-if="savedPortfolio.length"
                outline
                no-caps
                dense
                class="refresh-btn"
                label="Очистить портфель"
                @click="askClear('portfolio')"
              />
              <q-btn
                v-if="savedChats.length"
                outline
                no-caps
                dense
                class="refresh-btn"
                label="Очистить чаты"
                @click="askClear('chats')"
              />
              <q-btn
                outline
                no-caps
                dense
                class="refresh-btn"
                icon="refresh"
                :loading="savedLoading"
                label="Обновить"
                @click="loadSaved"
              />
            </div>
          </div>

          <!-- Фильтр: тип сохранённого и диапазон дат. -->
          <div class="saved-filters">
            <div class="filter-chips">
              <button
                v-for="option in kindOptions"
                :key="option.value"
                type="button"
                class="filter-chip"
                :class="{ 'is-active': kind === option.value }"
                @click="kind = option.value"
              >
                {{ option.label }}
              </button>
            </div>

            <div class="filter-dates">
              <q-input
                v-model="dateFrom"
                type="date"
                outlined
                dense
                label="С даты"
              />
              <q-input
                v-model="dateTo"
                type="date"
                outlined
                dense
                label="По дату"
              />
              <q-btn
                v-if="dateFrom || dateTo"
                flat
                dense
                no-caps
                label="Сбросить"
                @click="resetDates"
              />
            </div>
          </div>

          <div v-if="savedLoading" class="loading-row">
            <q-spinner size="26px" />
          </div>

          <div v-else-if="!filteredItems.length" class="empty-text">
            Ничего не найдено — соберите портфель или чат и нажмите «Сохранить».
          </div>

          <ul v-else class="saved-list">
            <li
              v-for="item in filteredItems"
              :key="item.key"
              class="saved-item"
            >
              <span class="saved-kind" :class="`is-${item.kind}`">
                {{ item.kind === 'portfolio' ? 'Портфель' : 'Чат' }}
              </span>

              <div class="saved-body">
                <div class="saved-title">{{ item.title }}</div>

                <div v-if="item.kind === 'portfolio'" class="saved-desc">
                  Позиций: <b>{{ item.count }}</b> · Итого:
                  <b>{{ formatPortfolioPrice(item.sum) }} ₽</b>
                </div>

                <div v-else class="saved-desc">
                  Сообщений: <b>{{ item.count }}</b>
                  <span v-if="item.preview"> · {{ item.preview }}</span>
                </div>

                <div class="saved-date">{{ formatSavedDate(item.date) }}</div>

                <details v-if="item.kind === 'portfolio'" class="saved-details">
                  <summary>Состав портфеля</summary>

                  <ul class="portfolio-list">
                    <li
                      v-for="(position, index) in item.portfolio"
                      :key="position.surfaceId"
                      class="portfolio-item"
                    >
                      <div class="portfolio-item-num">{{ index + 1 }}</div>

                      <div class="portfolio-item-body">
                        <div class="portfolio-item-title">
                          {{ position.type || 'Формат не указан' }}
                        </div>

                        <div class="portfolio-item-address">
                          {{ savedAddress(position) }}
                        </div>

                        <div
                          v-if="savedMonths(position).length"
                          class="portfolio-item-months"
                        >
                          <span
                            v-for="month in savedMonths(position)"
                            :key="month"
                            class="portfolio-item-month"
                          >
                            {{ month }}
                          </span>
                        </div>
                      </div>

                      <div class="portfolio-item-sum">
                        {{ formatPortfolioPrice(savedSum(position)) }} ₽
                      </div>
                    </li>
                  </ul>
                </details>
              </div>

              <div v-if="item.kind === 'portfolio'" class="saved-item-actions">
                <q-btn
                  unelevated
                  no-caps
                  dense
                  color="primary"
                  label="В портфель"
                  :loading="portfolioRestoring"
                  @click="restorePortfolio"
                />
                <q-btn
                  flat
                  no-caps
                  dense
                  label="Открыть"
                  @click="router.push('/portfolio')"
                />
              </div>
            </li>
          </ul>

          <div v-if="portfolioMessage" class="portfolio-note">
            {{ portfolioMessage }}
          </div>
        </section>

        <!-- ============================================================
             РЕКВИЗИТЫ — попадают в распечатку и копирование портфеля
        ============================================================ -->
        <section v-if="!isAdmin" class="requests-card requisites-card">
          <div class="section-head">
            <div class="section-title">Реквизиты</div>
          </div>

          <p class="requisites-note">
            Эти данные попадут в распечатку и копирование портфеля.
          </p>

          <form
            class="requisites-form"
            novalidate
            @submit.prevent="submitRequisites"
          >
            <div class="requisites-grid">
              <div class="field">
                <label>Организация</label>
                <q-input
                  v-model="requisitesForm.organization"
                  outlined
                  dense
                  placeholder="Название организации"
                />
              </div>

              <div class="field">
                <label>ИНН</label>
                <q-input
                  v-model="requisitesForm.inn"
                  outlined
                  dense
                  placeholder="Только цифры"
                  :error="Boolean(requisitesErrors.inn)"
                  :error-message="requisitesErrors.inn"
                />
              </div>

              <div class="field">
                <label>КПП</label>
                <q-input
                  v-model="requisitesForm.kpp"
                  outlined
                  dense
                  placeholder="Только цифры"
                  :error="Boolean(requisitesErrors.kpp)"
                  :error-message="requisitesErrors.kpp"
                />
              </div>

              <div class="field">
                <label>Телефон</label>
                <q-input
                  v-model="requisitesForm.phone"
                  outlined
                  dense
                  placeholder="+7 ..."
                />
              </div>

              <div class="field">
                <label>E-mail</label>
                <q-input
                  v-model="requisitesForm.email"
                  outlined
                  dense
                  type="email"
                  placeholder="mail@example.ru"
                  :error="Boolean(requisitesErrors.email)"
                  :error-message="requisitesErrors.email"
                />
              </div>

              <div class="field">
                <label>Контактное лицо</label>
                <q-input
                  v-model="requisitesForm.contact"
                  outlined
                  dense
                  placeholder="ФИО"
                />
              </div>

              <div class="field requisites-field-wide">
                <label>Адрес</label>
                <q-input
                  v-model="requisitesForm.address"
                  outlined
                  dense
                  placeholder="Юридический / почтовый адрес"
                />
              </div>
            </div>

            <div class="requisites-actions">
              <q-btn
                unelevated
                no-caps
                dense
                color="primary"
                type="submit"
                label="Сохранить реквизиты"
                :loading="requisitesSaving"
              />

              <Transition name="fade">
                <span
                  v-if="requisitesMessage"
                  class="requisites-message"
                  :class="`is-${requisitesMessageType}`"
                >
                  {{ requisitesMessage }}
                </span>
              </Transition>
            </div>
          </form>
        </section>

        <!-- Подтверждение очистки сохранённого списка. -->
        <q-dialog v-model="confirmOpen" persistent>
          <q-card class="confirm-card">
            <q-card-section>
              <div class="confirm-title">{{ confirmText }}</div>
              <div class="confirm-note">
                Очищается только сохранённый список. Содержание остаётся в
                журнале и базе данных.
              </div>
            </q-card-section>

            <q-card-actions align="right">
              <q-btn flat no-caps label="Отмена" @click="confirmOpen = false" />
              <q-btn
                unelevated
                no-caps
                color="primary"
                label="Очистить"
                :loading="clearing"
                @click="doClear"
              />
            </q-card-actions>
          </q-card>
        </q-dialog>
      </template>

      <!-- ============================================================
           НЕ АВТОРИЗОВАН
      ============================================================ -->
      <section v-else class="auth-card">
        <!-- Переключатель вкладок -->
        <div class="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            class="tab"
            :class="{ 'is-active': mode !== 'register' }"
            :aria-selected="mode !== 'register'"
            @click="switchMode('login')"
          >
            Вход
          </button>

          <button
            type="button"
            role="tab"
            class="tab"
            :class="{ 'is-active': mode === 'register' }"
            :aria-selected="mode === 'register'"
            @click="switchMode('register')"
          >
            Регистрация
          </button>
        </div>

        <!-- Сообщения -->
        <Transition name="fade">
          <div v-if="successMessage" class="message message-success">
            {{ successMessage }}
          </div>
        </Transition>

        <Transition name="fade">
          <div v-if="error && mode !== 'recover'" class="message message-error">
            {{ error }}
          </div>
        </Transition>

        <!-- -------------------- ВХОД -------------------- -->
        <form
          v-if="mode === 'login'"
          class="auth-form"
          novalidate
          @submit.prevent="submitLogin"
        >
          <div class="field">
            <label>Логин</label>
            <q-input
              v-model="loginForm.login"
              outlined
              dense
              autocomplete="username"
              placeholder="Ваш логин"
              :error="Boolean(fieldErrors.login)"
              :error-message="fieldErrors.login"
            />
          </div>

          <div class="field">
            <label>Пароль</label>
            <q-input
              v-model="loginForm.password"
              outlined
              dense
              type="password"
              autocomplete="current-password"
              placeholder="Ваш пароль"
              :error="Boolean(fieldErrors.password)"
              :error-message="fieldErrors.password"
            />
          </div>

          <q-btn
            class="submit-btn"
            color="primary"
            no-caps
            type="submit"
            label="Войти"
            :loading="loading"
          />

          <button type="button" class="link-btn" @click="switchMode('recover')">
            Забыли пароль?
          </button>
        </form>

        <!-- -------------------- РЕГИСТРАЦИЯ -------------------- -->
        <form
          v-else-if="mode === 'register'"
          class="auth-form"
          novalidate
          @submit.prevent="submitRegister"
        >
          <p class="register-note">{{ REGISTER_NOTE }}</p>

          <div class="field">
            <label>Логин</label>
            <q-input
              v-model="registerForm.login"
              outlined
              dense
              autocomplete="username"
              placeholder="Минимум 3 символа"
              :error="Boolean(fieldErrors.login)"
              :error-message="fieldErrors.login"
            />
          </div>

          <div class="field">
            <label>Пароль</label>
            <q-input
              v-model="registerForm.password"
              outlined
              dense
              type="password"
              autocomplete="new-password"
              placeholder="Минимум 4 символа"
              :error="Boolean(fieldErrors.password)"
              :error-message="fieldErrors.password"
            />
          </div>

          <div class="field">
            <label>Секретная фраза (для восстановления пароля)</label>
            <q-input
              v-model="registerForm.secret_phrase"
              outlined
              dense
              placeholder="Минимум 4 символа"
              :error="Boolean(fieldErrors.secret_phrase)"
              :error-message="fieldErrors.secret_phrase"
            />
            <div class="field-hint">
              Фраза нужна, чтобы вспомнить пароль, если вы его забудете, и
              известна только вам. Это не персональные данные — укажите любую
              понятную вам комбинацию.
            </div>
          </div>

          <q-btn
            class="submit-btn"
            color="primary"
            no-caps
            type="submit"
            label="Зарегистрироваться"
            :loading="loading"
          />
        </form>

        <!-- -------------------- ВОССТАНОВЛЕНИЕ -------------------- -->
        <form
          v-else
          class="auth-form"
          novalidate
          @submit.prevent="submitRecover"
        >
          <div class="form-caption"> Вспомнить пароль по секретной фразе </div>

          <Transition name="fade">
            <div v-if="error" class="message message-error">{{ error }}</div>
          </Transition>

          <div class="field">
            <label>Логин</label>
            <q-input
              v-model="recoverForm.login"
              outlined
              dense
              autocomplete="username"
              placeholder="Ваш логин"
              :error="Boolean(fieldErrors.login)"
              :error-message="fieldErrors.login"
            />
          </div>

          <div class="field">
            <label>Секретная фраза</label>
            <q-input
              v-model="recoverForm.secret_phrase"
              outlined
              dense
              placeholder="Фраза, указанная при регистрации"
              :error="Boolean(fieldErrors.secret_phrase)"
              :error-message="fieldErrors.secret_phrase"
            />
          </div>

          <div class="field">
            <label>Новый пароль</label>
            <q-input
              v-model="recoverForm.new_password"
              outlined
              dense
              type="password"
              autocomplete="new-password"
              placeholder="Минимум 4 символа"
              :error="Boolean(fieldErrors.new_password)"
              :error-message="fieldErrors.new_password"
            />
          </div>

          <q-btn
            class="submit-btn"
            color="primary"
            no-caps
            type="submit"
            label="Восстановить пароль"
            :loading="loading"
          />

          <button type="button" class="link-btn" @click="switchMode('login')">
            Вернуться ко входу
          </button>
        </form>
      </section>
    </div>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAccount } from '@/composables/useAccount'
import { useChatWorkspace } from '@/composables/useChatWorkspace'
import { usePortfolio } from '@/composables/usePortfolio'
import { MONTHS } from '@/utils/constructionGroups'

const {
  account,
  requisites,
  isAuthenticated,
  loading,
  error,
  login,
  register,
  logout,
  recover,
  loadMe,
  saveRequisites,
  clearError
} = useAccount()

const { fetchSavedChats, clearChats } = useChatWorkspace()

const router = useRouter()

/*
 * Сохранённый в личном кабинете портфель — только для показа.
 * Текущий (несохранённый) портфель живёт в usePortfolio().
 */
const {
  fetchAccountPortfolio,
  mergeFromAccount,
  accountTitle,
  accountPortfolioUpdatedAt,
  clearAccountPortfolio
} = usePortfolio()

const savedPortfolio = ref([])
const savedChats = ref([])
const chatsUpdatedAt = ref('')
const savedLoading = ref(false)
const portfolioRestoring = ref(false)
const portfolioMessage = ref('')

const PORTFOLIO_PRICE = new Intl.NumberFormat('ru-RU')

/* ------------------------- фильтр сохранённого ------------------------- */

const kind = ref('all')
const kindOptions = [
  { value: 'all', label: 'Все вместе' },
  { value: 'portfolio', label: 'Портфели' },
  { value: 'chat', label: 'Чаты' }
]

const dateFrom = ref('')
const dateTo = ref('')

function resetDates() {
  dateFrom.value = ''
  dateTo.value = ''
}

function dateMs(value) {
  if (!value) return 0

  const date = new Date(value)

  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

function startOfDay(iso) {
  const [year, month, day] = String(iso).split('-').map(Number)

  return new Date(year, month - 1, day, 0, 0, 0, 0).getTime()
}

function endOfDay(iso) {
  const [year, month, day] = String(iso).split('-').map(Number)

  return new Date(year, month - 1, day, 23, 59, 59, 999).getTime()
}

function formatSavedDate(value) {
  if (!value) return 'Дата не указана'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return String(value)

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function shorten(text) {
  const value = String(text ?? '').trim()

  return value.length > 60 ? `${value.slice(0, 60)}…` : value
}

/* Полное имя месяца -> короткая подпись («Октябрь» -> «ОКТ»). */
function monthShort(full) {
  const found = MONTHS.find(month => month.full === full)

  return found ? found.short : full
}

function savedMonths(item) {
  return Object.keys(item?.months || {}).map(monthShort)
}

function savedSum(item) {
  return Object.values(item?.months || {}).reduce(
    (sum, month) => sum + (Number(month && month.price) || 0),
    0
  )
}

function savedAddress(item) {
  const place = [item?.city, item?.address]
    .map(value => String(value ?? '').trim())
    .filter(Boolean)
    .join(', ')

  const side = String(item?.side ?? '').trim()

  return side ? `${place} · Сторона ${side}` : place
}

function formatPortfolioPrice(value) {
  return PORTFOLIO_PRICE.format(Number(value) || 0)
}

const savedTotal = computed(() =>
  savedPortfolio.value.reduce((sum, item) => sum + savedSum(item), 0)
)

/* Единый список сохранённого: портфель (одна запись) + чаты. */
const savedItems = computed(() => {
  const list = []

  if (savedPortfolio.value.length) {
    list.push({
      key: 'portfolio',
      kind: 'portfolio',
      title: accountTitle.value || 'Портфель',
      date: accountPortfolioUpdatedAt.value,
      portfolio: savedPortfolio.value,
      count: savedPortfolio.value.length,
      sum: savedTotal.value
    })
  }

  savedChats.value.forEach((chat, index) => {
    const messages = Array.isArray(chat.messages) ? chat.messages : []
    const questions = messages.filter(message => message.role === 'user')
    const lastQuestion = questions.length
      ? shorten(questions[questions.length - 1].text)
      : ''

    list.push({
      key: chat.key || `chat-${index}`,
      kind: 'chat',
      title: `Чат №${chat.number ?? index + 1}`,
      date: chatsUpdatedAt.value,
      chat,
      count: messages.length,
      preview: lastQuestion
    })
  })

  return list.sort((a, b) => dateMs(b.date) - dateMs(a.date))
})

const filteredItems = computed(() =>
  savedItems.value.filter(item => {
    if (kind.value !== 'all' && item.kind !== kind.value) {
      return false
    }

    if (!dateFrom.value && !dateTo.value) {
      return true
    }

    const ms = dateMs(item.date)

    if (!ms) return false

    if (dateFrom.value && ms < startOfDay(dateFrom.value)) return false

    if (dateTo.value && ms > endOfDay(dateTo.value)) return false

    return true
  })
)

/* ------------------------- загрузка и очистка ------------------------- */

async function loadSaved() {
  if (!isAuthenticated.value) {
    savedPortfolio.value = []
    savedChats.value = []
    chatsUpdatedAt.value = ''

    return
  }

  savedLoading.value = true

  try {
    const [portfolio, chats] = await Promise.all([
      fetchAccountPortfolio(),
      fetchSavedChats()
    ])

    savedPortfolio.value = portfolio
    savedChats.value = chats.chats
    chatsUpdatedAt.value = chats.updated_at
  } finally {
    savedLoading.value = false
  }
}

/* Подтянуть сохранённый портфель в текущий (объединение по поверхностям). */
async function restorePortfolio() {
  portfolioRestoring.value = true
  portfolioMessage.value = ''

  try {
    await mergeFromAccount()
    savedPortfolio.value = await fetchAccountPortfolio()
    portfolioMessage.value =
      'Портфель загружен — откройте его кнопкой «Портфель» в шапке.'
  } finally {
    portfolioRestoring.value = false
  }
}

const confirmOpen = ref(false)
const clearing = ref(false)
const clearTarget = ref('portfolio')

const confirmText = computed(() =>
  clearTarget.value === 'chats'
    ? 'Очистить сохранённые чаты?'
    : 'Очистить сохранённый портфель?'
)

function askClear(target) {
  clearTarget.value = target
  confirmOpen.value = true
}

async function doClear() {
  clearing.value = true

  try {
    if (clearTarget.value === 'chats') {
      await clearChats()
      savedChats.value = []
      chatsUpdatedAt.value = ''
    } else if (await clearAccountPortfolio()) {
      savedPortfolio.value = []
    }

    confirmOpen.value = false
  } finally {
    clearing.value = false
  }
}

/* ---------------- РЕКВИЗИТЫ ---------------- */

const REQUISITE_FIELDS = [
  'organization',
  'inn',
  'kpp',
  'address',
  'phone',
  'email',
  'contact'
]

function emptyRequisites() {
  return REQUISITE_FIELDS.reduce((acc, field) => {
    acc[field] = ''
    return acc
  }, {})
}

const requisitesForm = ref(emptyRequisites())
const requisitesErrors = ref({})
const requisitesSaving = ref(false)
const requisitesMessage = ref('')
const requisitesMessageType = ref('success')

/* Заполняем поля текущими реквизитами из ЛК (в т.ч. после перезагрузки). */
watch(
  requisites,
  value => {
    requisitesForm.value = { ...emptyRequisites(), ...value }
  },
  { deep: true, immediate: true }
)

function validateRequisites(values) {
  const errors = {}
  const email = String(values.email ?? '').trim()
  const inn = String(values.inn ?? '').trim()
  const kpp = String(values.kpp ?? '').trim()

  if (email && !email.includes('@')) {
    errors.email = 'E-mail должен содержать @'
  }

  if (inn && !/^\d+$/.test(inn)) {
    errors.inn = 'ИНН: только цифры'
  }

  if (kpp && !/^\d+$/.test(kpp)) {
    errors.kpp = 'КПП: только цифры'
  }

  return errors
}

async function submitRequisites() {
  requisitesMessage.value = ''

  const errors = validateRequisites(requisitesForm.value)

  requisitesErrors.value = errors
  if (Object.keys(errors).length) return

  const payload = REQUISITE_FIELDS.reduce((acc, field) => {
    acc[field] = String(requisitesForm.value[field] ?? '').trim()
    return acc
  }, {})

  requisitesSaving.value = true

  try {
    await saveRequisites(payload)
    requisitesMessage.value = 'Реквизиты сохранены'
    requisitesMessageType.value = 'success'
  } catch (exc) {
    /* локальное сообщение об ошибке — без дубля в общем баннере */
    requisitesMessage.value =
      exc && exc.message ? exc.message : 'Не удалось сохранить реквизиты'
    requisitesMessageType.value = 'error'
    clearError()
  } finally {
    requisitesSaving.value = false
  }
}

/* 'login' | 'register' | 'recover' */
const mode = ref('login')
const successMessage = ref('')
const fieldErrors = ref({})

const loginForm = ref({ login: '', password: '' })
const registerForm = ref({ login: '', password: '', secret_phrase: '' })
const recoverForm = ref({ login: '', secret_phrase: '', new_password: '' })

/* Текст выводится дословно и хранится одной строкой. */
const REGISTER_NOTE =
  'Придумайте себе логин и пароль – можно русскими буквами. Они нужны только чтобы сохранять ваши портфели и чаты, к которым вы можете вернуться позже, никакие персональные данные не указываются и не хранятся.'

const avatarLetter = computed(() =>
  String(account.value?.login || '?')
    .charAt(0)
    .toUpperCase()
)

/* Админ ли текущий пользователь ЛК — управляет показом кнопки «Админка». */
const isAdmin = computed(() => account.value?.role === 'admin')

const roleLabel = computed(() => {
  const role = account.value?.role

  if (role === 'admin') return 'администратор'
  if (role === 'user') return 'пользователь'
  return role || 'пользователь'
})

onMounted(async () => {
  await loadMe()
  await loadSaved()
})

function switchMode(next) {
  mode.value = next
  fieldErrors.value = {}
  successMessage.value = ''
  clearError()
}

function validate(values, rules) {
  const errors = {}

  for (const [key, { label, min }] of Object.entries(rules)) {
    const value = String(values[key] ?? '').trim()

    if (!value) {
      errors[key] = `${label}: поле не заполнено`
    } else if (value.length < min) {
      errors[key] = `${label}: минимум ${min} символа`
    }
  }

  return errors
}

/* ---------------- ВХОД ---------------- */

async function submitLogin() {
  successMessage.value = ''

  const errors = validate(loginForm.value, {
    login: { label: 'Логин', min: 3 },
    password: { label: 'Пароль', min: 4 }
  })

  fieldErrors.value = errors
  if (Object.keys(errors).length) return

  try {
    await login(loginForm.value.login.trim(), loginForm.value.password)

    /*
     * Админ входит через личный кабинет — сразу уводим в дашборд
     * админки: для этого получаем отдельный админ-токен (та же пара
     * логин/пароль) и кладём его в sessionStorage.
     */
    if (account.value?.role === 'admin') {
      await enterAdminArea()
      return
    }

    await loadSaved()
  } catch {
    /* текст ошибки уже в error */
  }
}

/*
 * Вход администратора в админку после ЛК-логина: запрашиваем админ-токен
 * тем же логином/паролем, сохраняем и переходим на дашборд. Если не
 * удалось — отправляем на форму входа в админку.
 */
async function enterAdminArea() {
  try {
    const response = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        login: loginForm.value.login.trim(),
        password: loginForm.value.password
      })
    })

    const data = await response.json()

    if (response.ok && data.token) {
      sessionStorage.setItem('albion_admin_token', data.token)
      await router.push('/administration/dashboard')
      return
    }
  } catch (exc) {
    /* ниже — откат на форму входа в админку */
  }

  await router.push('/administration')
}

/* ---------------- РЕГИСТРАЦИЯ ---------------- */

async function submitRegister() {
  successMessage.value = ''

  const errors = validate(registerForm.value, {
    login: { label: 'Логин', min: 3 },
    password: { label: 'Пароль', min: 4 },
    secret_phrase: { label: 'Секретная фраза', min: 4 }
  })

  fieldErrors.value = errors
  if (Object.keys(errors).length) return

  try {
    await register({
      login: registerForm.value.login.trim(),
      password: registerForm.value.password,
      secret_phrase: registerForm.value.secret_phrase
    })
    await loadSaved()
  } catch {
    /* текст ошибки уже в error */
  }
}

/* ---------------- ВОССТАНОВЛЕНИЕ ---------------- */

async function submitRecover() {
  successMessage.value = ''

  const errors = validate(recoverForm.value, {
    login: { label: 'Логин', min: 3 },
    secret_phrase: { label: 'Секретная фраза', min: 4 },
    new_password: { label: 'Новый пароль', min: 4 }
  })

  fieldErrors.value = errors
  if (Object.keys(errors).length) return

  try {
    await recover({
      login: recoverForm.value.login.trim(),
      secret_phrase: recoverForm.value.secret_phrase,
      new_password: recoverForm.value.new_password
    })

    recoverForm.value = { login: '', secret_phrase: '', new_password: '' }
    mode.value = 'login'
    fieldErrors.value = {}
    successMessage.value = 'Пароль изменён. Войдите с новым паролем.'
  } catch {
    /* текст ошибки уже в error */
  }
}

/* ---------------- ВЫХОД ---------------- */

async function handleLogout() {
  await logout()
  mode.value = 'login'
  loginForm.value = { login: '', password: '' }
  fieldErrors.value = {}
  successMessage.value = ''
  requisitesForm.value = emptyRequisites()
  requisitesErrors.value = {}
  requisitesMessage.value = ''
  savedPortfolio.value = []
  savedChats.value = []
  chatsUpdatedAt.value = ''
}
</script>

<style scoped>
.account-page {
  background: #f3f5f6;
  color: #17212b;
}

.account-wrap {
  max-width: 720px;
  margin: 0 auto;
  padding: 40px 24px 64px;
}

/* ---------------- Заголовок ---------------- */

.page-head {
  margin-bottom: 24px;
}

.eyebrow {
  color: var(--albion-accent);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 2px;
}

.page-head h1 {
  margin: 8px 0 6px;
  color: #17212b;
  font-size: 32px;
  line-height: 1.1;
  font-weight: 900;
}

.page-head p {
  margin: 0;
  color: #5b6873;
  font-size: 14px;
}

/* ---------------- Карточки ---------------- */

.auth-card,
.profile-card,
.requests-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 22px;
}

.auth-card {
  margin-bottom: 18px;
}

.profile-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.profile-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.profile-avatar {
  flex: 0 0 48px;
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: #17212b;
  color: #fff;
  font-size: 20px;
  font-weight: 900;
}

.profile-login {
  font-size: 18px;
  font-weight: 800;
  word-break: break-word;
}

.profile-role {
  margin-top: 2px;
  color: #8b8b8b;
  font-size: 12px;
  font-weight: 700;
}

.profile-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.admin-btn {
  background: #17212b;
  color: #ffffff;
  font-weight: 700;
}

.logout-btn {
  color: #17212b;
}

/* ---------------- Вкладки ---------------- */

.tabs {
  display: flex;
  gap: 6px;
  padding: 4px;
  margin-bottom: 20px;
  border-radius: 12px;
  background: #f1f3f4;
}

.tab {
  flex: 1 1 0;
  padding: 10px 12px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #66727c;
  font-family: inherit;
  font-size: 13px;
  font-weight: 900;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.tab:hover {
  color: #17212b;
}

.tab.is-active {
  background: #17212b;
  color: #fff;
}

/* ---------------- Сообщения ---------------- */

.message {
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.45;
  margin-bottom: 16px;
}

.message-error {
  color: #b3261e;
  background: #fff0f0;
}

.message-success {
  color: #1b5e20;
  background: #eef7ee;
}

/* Плавное появление сообщений (без плагина Notify) */
.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ---------------- Формы ---------------- */

.auth-form {
  display: block;
}

.field {
  margin-bottom: 14px;
}

.field label {
  display: block;
  margin-bottom: 5px;
  color: #66727c;
  font-size: 12px;
  font-weight: 700;
}

.field-hint {
  margin-top: 6px;
  color: #8b8b8b;
  font-size: 12px;
  line-height: 1.45;
}

.form-caption {
  margin-bottom: 14px;
  font-size: 15px;
  font-weight: 800;
}

.register-note {
  margin: 0 0 18px;
  padding: 12px 14px;
  border-left: 3px solid var(--albion-accent);
  border-radius: 0 10px 10px 0;
  background: #f7f8f9;
  color: #45525c;
  font-size: 13px;
  line-height: 1.5;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
  font-weight: 800;
}

.link-btn {
  display: block;
  margin: 14px auto 0;
  padding: 4px;
  border: 0;
  background: transparent;
  color: var(--albion-accent);
  font-family: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

/* ---------------- Секции ---------------- */

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.section-title {
  margin-bottom: 16px;
  font-size: 17px;
  font-weight: 800;
}

.section-head .section-title {
  margin-bottom: 0;
}

/* Название сохранённого портфеля — рядом с заголовком раздела. */
.section-subtitle {
  margin-left: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #6b7785;
}

.refresh-btn {
  color: #17212b;
  font-weight: 700;
}

.loading-row {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}

.empty-text {
  padding: 8px 0;
  color: #777;
  font-size: 14px;
}

/* ---------------- Сохранённое: фильтр ---------------- */

.saved-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.saved-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;

  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #eceef1;
}

.filter-chips {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border-radius: 10px;
  background: #f1f3f4;
}

.filter-chip {
  padding: 6px 12px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #66727c;
  font-family: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.filter-chip:hover {
  color: #17212b;
}

.filter-chip.is-active {
  background: #17212b;
  color: #fff;
}

.filter-dates {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-dates :deep(.q-field) {
  width: 150px;
}

/* ---------------- Сохранённое: список ---------------- */

.saved-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.saved-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;

  padding: 14px 16px;
  margin-bottom: 10px;

  border: 1px solid #e4e6ea;
  border-radius: 12px;
}

.saved-kind {
  flex: 0 0 auto;

  padding: 3px 9px;
  border-radius: 8px;

  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

.saved-kind.is-portfolio {
  background: #e8f0fe;
  color: #1a56b8;
}

.saved-kind.is-chat {
  background: #fdeceb;
  color: var(--albion-accent);
}

.saved-body {
  flex: 1 1 auto;
  min-width: 0;
}

.saved-title {
  font-size: 15px;
  font-weight: 800;
}

.saved-desc {
  margin-top: 3px;
  color: #5b6873;
  font-size: 13px;
  line-height: 1.4;
}

.saved-date {
  margin-top: 4px;
  color: #8b8b8b;
  font-size: 11px;
}

.saved-details {
  margin-top: 10px;
}

.saved-details summary {
  color: var(--albion-accent);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.saved-details .portfolio-list {
  margin-top: 10px;
}

.saved-item-actions {
  flex: 0 0 auto;

  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ---------------- Портфель в ЛК ---------------- */

.portfolio-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.portfolio-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;

  padding: 14px 16px;
  margin-bottom: 10px;

  border: 1px solid #e4e6ea;
  border-radius: 12px;
}

.portfolio-item-num {
  flex: 0 0 auto;

  color: #5b6873;
  font-size: 13px;
  font-weight: 900;
  line-height: 1.4;
}

.portfolio-item-body {
  flex: 1 1 auto;
  min-width: 0;
}

.portfolio-item-title {
  font-size: 15px;
  font-weight: 700;
}

.portfolio-item-address {
  margin-top: 3px;
  color: #5b6873;
  font-size: 13px;
  line-height: 1.4;
}

.portfolio-item-months {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;

  margin-top: 8px;
}

.portfolio-item-month {
  padding: 2px 8px;

  border: 1px solid var(--albion-accent);
  border-radius: 7px;

  color: var(--albion-accent);

  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.3px;
}

.portfolio-item-sum {
  flex: 0 0 auto;

  font-size: 15px;
  font-weight: 800;
  white-space: nowrap;
}

.portfolio-note {
  margin-top: 10px;
  padding: 8px 12px;

  border-radius: 10px;
  background: #e8f5e9;
  color: #2e7d32;

  font-size: 13px;
}

/* ---------------- Подтверждение ---------------- */

.confirm-card {
  min-width: 320px;
  max-width: 420px;
  border-radius: 14px;
}

.confirm-title {
  font-size: 16px;
  font-weight: 800;
}

.confirm-note {
  margin-top: 8px;
  color: #5b6873;
  font-size: 13px;
  line-height: 1.45;
}

/* --- Реквизиты --- */

.requisites-card {
  margin-top: 18px;
}

.requisites-note {
  margin: 0 0 16px;
  color: #5b6873;
  font-size: 13px;
  line-height: 1.5;
}

.requisites-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.requisites-grid .field {
  margin-bottom: 14px;
}

.requisites-field-wide {
  grid-column: 1 / -1;
}

.requisites-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;

  margin-top: 4px;
}

.requisites-message {
  font-size: 13px;
  font-weight: 700;
}

.requisites-message.is-success {
  color: #1b5e20;
}

.requisites-message.is-error {
  color: #b3261e;
}

@media (max-width: 560px) {
  .account-wrap {
    padding: 28px 16px 48px;
  }

  .page-head h1 {
    font-size: 26px;
  }

  .saved-item {
    flex-direction: column;
    gap: 8px;
  }

  .saved-item-actions {
    flex-direction: row;
  }

  .saved-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-dates {
    flex-wrap: wrap;
  }

  .requisites-grid {
    grid-template-columns: 1fr;
  }
}
</style>
