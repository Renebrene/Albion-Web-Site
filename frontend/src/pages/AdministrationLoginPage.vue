<template>
  <q-page class="administration-login">
    <div class="login-card">
      <!-- Логотип как на публичном сайте; клик — переход на сайт -->
      <RouterLink
        to="/"
        class="login-brand"
        title="Перейти на сайт"
        aria-label="Albion — перейти на сайт"
      >
        <img src="/logo.png" alt="Albion" class="login-brand-logo" />
      </RouterLink>

      <h1>Администрирование</h1>

      <p class="login-subtitle"> Вход в панель управления сайтом </p>

      <q-form class="login-form" @submit.prevent="submit">
        <q-input
          v-model="login"
          outlined
          label="Логин"
          autocomplete="username"
          :disable="loading"
        />

        <q-input
          v-model="password"
          outlined
          label="Пароль"
          type="password"
          autocomplete="current-password"
          :disable="loading"
        />

        <div v-if="error" class="login-error">
          {{ error }}
        </div>

        <q-btn
          type="submit"
          unelevated
          no-caps
          class="login-button"
          label="Войти"
          :loading="loading"
          :disable="!login || !password"
        />
      </q-form>
    </div>
  </q-page>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { setAdminToken } from '../services/adminApi'

const router = useRouter()

const login = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true

  try {
    const response = await fetch('/api/admin/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        login: login.value,
        password: password.value
      })
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Не удалось выполнить вход')
    }

    setAdminToken(data.token)

    await router.push('/administration/dashboard')
  } catch (err) {
    error.value = err.message || 'Не удалось выполнить вход'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.administration-login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 440px;
  padding: 40px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
}

.login-brand {
  display: inline-flex;
  align-items: center;

  margin-bottom: 32px;
}

.login-brand-logo {
  display: block;

  width: auto;
  height: 48px;

  max-width: 180px;
}

.login-card h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.15;
}

.login-subtitle {
  margin: 10px 0 28px;
  color: #6b7280;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.login-error {
  color: #c62828;
  font-size: 14px;
}

.login-button {
  min-height: 48px;
  background: #111111;
  color: #ffffff;
}

@media (max-width: 600px) {
  .administration-login {
    padding: 16px;
  }

  .login-card {
    padding: 28px 20px;
  }

  .login-card h1 {
    font-size: 26px;
  }
}
</style>
