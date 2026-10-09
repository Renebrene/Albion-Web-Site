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
            <img
              src="/logo.png"
              alt="Albion"
              class="dashboard-brand-logo"
            >
          </RouterLink>
          <h1>Администрирование</h1>
          <p v-if="user" class="dashboard-user">
            {{ user.name || user.login }}
          </p>
        </div>

        <q-btn
          flat
          no-caps
          label="Выйти"
          :loading="loggingOut"
          @click="logout"
        />
      </header>

      <div v-if="loading" class="dashboard-loading">
        <q-spinner size="32px" />
      </div>

      <div v-else-if="error" class="dashboard-error">
        {{ error }}
      </div>

      <template v-else>
        <section class="dashboard-grid">
          <q-card
            v-for="item in sections"
            :key="item.path"
            flat
            bordered
            class="dashboard-card"
            @click="router.push(item.path)"
          >
            <q-card-section>
              <div class="dashboard-card-title">
                {{ item.title }}
              </div>
              <div class="dashboard-card-text">
                {{ item.text }}
              </div>
            </q-card-section>
          </q-card>
        </section>
      </template>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const user = ref(null)
const loading = ref(true)
const loggingOut = ref(false)
const error = ref('')

const sections = [
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
    title: 'Статистика',
    text: 'Посещаемость страниц и география',
    path: '/administration/statistics'
  }
]

async function loadUser() {
  const token = sessionStorage.getItem('albion_admin_token')

  if (!token) {
    await router.replace('/administration')
    return
  }

  try {
    const response = await fetch('/api/admin/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (!response.ok) {
      sessionStorage.removeItem('albion_admin_token')
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
  const token = sessionStorage.getItem('albion_admin_token')

  loggingOut.value = true

  try {
    if (token) {
      await fetch('/api/admin/logout', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
    }
  } finally {
    sessionStorage.removeItem('albion_admin_token')
    await router.replace('/administration')
    loggingOut.value = false
  }
}

onMounted(loadUser)
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

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.dashboard-card {
  min-height: 150px;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease;
}

.dashboard-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
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
