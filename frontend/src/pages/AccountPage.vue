<template>
  <q-page class="account-page">
    <div class="account-wrap">
      <!-- ЗАГОЛОВОК -->
      <div class="page-head">
        <div class="eyebrow">ALBION</div>
        <h1>Личный кабинет</h1>
        <p>Ваши заявки и доступ к сервисам компании</p>
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

          <q-btn
            outline
            no-caps
            class="logout-btn"
            label="Выйти"
            :loading="loading"
            @click="handleLogout"
          />
        </section>

        <Transition name="fade">
          <div v-if="error" class="message message-error">{{ error }}</div>
        </Transition>

        <section class="requests-card">
          <div class="section-head">
            <div class="section-title">Ваши заявки</div>

            <q-btn
              outline
              no-caps
              dense
              class="refresh-btn"
              label="Обновить"
              :loading="loading"
              @click="handleRefresh"
            />
          </div>

          <div v-if="loading && !requests.length" class="loading-row">
            <q-spinner size="26px" />
          </div>

          <div v-else-if="!requests.length" class="empty-text">
            У вас пока нет заявок
          </div>

          <ul v-else class="request-list">
            <li
              v-for="(item, index) in requests"
              :key="item.id ?? index"
              class="request-item"
            >
              <div class="request-body">
                <div class="request-title">{{ requestTitle(item) }}</div>
                <div v-if="requestDescription(item)" class="request-desc">
                  {{ requestDescription(item) }}
                </div>
              </div>

              <div class="request-meta">
                <span v-if="item.status" class="request-status">
                  {{ item.status }}
                </span>
                <span v-if="requestDate(item)" class="request-date">
                  {{ requestDate(item) }}
                </span>
              </div>
            </li>
          </ul>
        </section>
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
import { computed, onMounted, ref } from 'vue'

import { useAccount } from '@/composables/useAccount'

const {
  account,
  requests,
  isAuthenticated,
  loading,
  error,
  login,
  register,
  logout,
  recover,
  loadMe,
  clearError
} = useAccount()

/* 'login' | 'register' | 'recover' */
const mode = ref('login')
const successMessage = ref('')
const fieldErrors = ref({})

const loginForm = ref({ login: '', password: '' })
const registerForm = ref({ login: '', password: '', secret_phrase: '' })
const recoverForm = ref({ login: '', secret_phrase: '', new_password: '' })

/* Текст выводится дословно и хранится одной строкой. */
const REGISTER_NOTE =
  'Придумайте себе логин и пароль – можно русскими буквами. Они нужны только чтобы запомнить ваши заявки, к которым вы можете вернуться позже, никакие персональные данные не указываются и не хранятся.'

const avatarLetter = computed(() =>
  String(account.value?.login || '?')
    .charAt(0)
    .toUpperCase()
)

const roleLabel = computed(() => {
  const role = account.value?.role

  if (role === 'admin') return 'администратор'
  if (role === 'user') return 'пользователь'
  return role || 'пользователь'
})

onMounted(() => {
  loadMe()
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
  } catch {
    /* текст ошибки уже в error */
  }
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

async function handleRefresh() {
  await loadMe()
}

async function handleLogout() {
  await logout()
  mode.value = 'login'
  loginForm.value = { login: '', password: '' }
  fieldErrors.value = {}
  successMessage.value = ''
}

/* ---------------- ЗАЯВКИ ---------------- */

function requestTitle(item) {
  return (
    item.title ||
    item.subject ||
    item.name ||
    (item.id ? `Заявка №${item.id}` : 'Заявка')
  )
}

function requestDescription(item) {
  return item.description || item.text || item.message || ''
}

function requestDate(item) {
  const raw = item.created_at || item.date || item.createdAt
  if (!raw) return ''

  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return String(raw)

  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
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
  color: #71808c;
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

/* ---------------- Заявки ---------------- */

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

.request-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.request-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  margin-bottom: 10px;
}

.request-body {
  min-width: 0;
}

.request-title {
  font-size: 15px;
  font-weight: 700;
}

.request-desc {
  margin-top: 3px;
  color: #71808c;
  font-size: 13px;
  line-height: 1.4;
}

.request-meta {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  text-align: right;
}

.request-status {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 8px;
  background: #eef1f5;
  color: #37474f;
  font-size: 11px;
  font-weight: 800;
}

.request-date {
  color: #8b8b8b;
  font-size: 11px;
}

@media (max-width: 560px) {
  .account-wrap {
    padding: 28px 16px 48px;
  }

  .page-head h1 {
    font-size: 26px;
  }

  .request-item {
    flex-direction: column;
    gap: 8px;
  }

  .request-meta {
    align-items: flex-start;
    text-align: left;
  }
}
</style>
