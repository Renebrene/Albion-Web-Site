<template>
  <header class="header">
    <!-- ЛОГОТИП -->
    <RouterLink to="/" class="brand" aria-label="Albion — главная страница">
      <img src="/logo.png" alt="Albion" class="logo" />
    </RouterLink>

    <!-- АДРЕС / EMAIL -->
    <div class="header-contact">
      <div class="address"> Ростов-на-Дону · ул. Социалистическая, 73 </div>

      <div class="emails">
        <a href="mailto:reclama@albion.su"> reclama@albion.su </a>

        <span>·</span>

        <a href="mailto:albion3@albion.su"> albion3@albion.su </a>
      </div>
    </div>

    <!-- НАВИГАЦИЯ (из CMS, фолбэк на дефолт) -->
    <nav class="header-nav">
      <template v-for="item in navItems" :key="item.key">
        <a v-if="isExternalCmsUrl(item.safeUrl)" :href="item.safeUrl">
          {{ item.label }}
        </a>
        <RouterLink v-else :to="item.safeUrl">
          {{ item.label }}
        </RouterLink>
      </template>

      <!-- ПОРТФЕЛЬ — всегда последний пункт, после «Контактов».
           Клик не переходит по маршруту, а открывает панель вниз. -->
      <q-btn
        flat
        dense
        no-caps
        class="nav-portfolio"
        :class="{ 'is-active': count > 0 }"
        aria-label="Портфель"
        :aria-expanded="portfolioOpen"
      >
        <span class="nav-portfolio-icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="2" y="7" width="20" height="14" rx="2" />
            <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </span>

        <span class="nav-portfolio-label">ПОРТФЕЛЬ</span>

        <span v-if="count" class="nav-portfolio-badge">{{ count }}</span>

        <q-menu
          v-model="portfolioOpen"
          class="portfolio-menu"
          anchor="bottom middle"
          self="top middle"
          :offset="[0, 12]"
        >
          <PortfolioPanel
            variant="dropdown"
            @navigate="portfolioOpen = false"
          />
        </q-menu>
      </q-btn>
    </nav>

    <!-- ТЕЛЕФОН -->
    <a href="tel:+78633203020" class="phone">
      <span class="phone-icon">
        <svg
          viewBox="0 0 24 24"
          width="15"
          height="15"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path
            d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"
          />
        </svg>
      </span>

      <span> 8 (863) 320-30-20 </span>
    </a>

    <!-- СОЦСЕТИ -->
    <div class="socials">
      <a href="#" class="social vk" title="ВКонтакте" aria-label="ВКонтакте">
        VK
      </a>

      <a
        href="#"
        class="social ok"
        title="Одноклассники"
        aria-label="Одноклассники"
      >
        OK
      </a>

      <a href="#" class="social max" title="Макс" aria-label="Макс"> Макс </a>
    </div>

    <!-- УМНЫЙ ЧАТ — открывает окно вниз, размером как «Портфель».
         Чаты общие с большим окном (страница /chat): список и данные
         синхронизированы, оформление — компактное. -->
    <div
      class="smart-chat"
      role="button"
      tabindex="0"
      aria-label="Умный чат"
      :aria-expanded="chatOpen"
      @click="openWorkspace()"
      @keydown.enter.prevent="chatOpen = !chatOpen"
      @keydown.space.prevent="chatOpen = !chatOpen"
    >
      <span class="chat-icon">✦</span>
      <span class="smart-chat-label">УМНЫЙ ЧАТ</span>

      <q-menu
        v-model="chatOpen"
        class="smart-chat-menu"
        anchor="bottom middle"
        self="top middle"
        :offset="[0, 12]"
      >
        <div class="smart-chat-panel">
          <div class="smart-chat-head">
            <span class="smart-chat-head-icon">✦</span>
            <span class="smart-chat-head-title">УМНЫЙ ЧАТ</span>

            <ChatSaveButton compact class="smart-chat-save" />
          </div>

          <div class="smart-chat-body">
            <SmartChatPanel
              v-for="(chat, index) in chats"
              :key="chat.key"
              variant="compact"
              :chat-key="chat.key"
              :chat-number="chat.number"
              :initial-draft="chat.draft"
              :page-link="index === 0"
              @close="chatOpen = false"
            />

            <!-- После очистки чатов список пуст — даём создать новый. -->
            <div v-if="!chats.length" class="smart-chat-empty">
              <span>Чаты очищены. История осталась в журнале.</span>
              <q-btn
                flat
                dense
                no-caps
                color="primary"
                label="Новый чат"
                @click="addChat()"
              />
            </div>
          </div>
        </div>
      </q-menu>
    </div>

    <!-- АВТОРИЗАЦИЯ -->
    <q-btn flat round dense class="auth-button" aria-label="Авторизация">
      <q-icon name="person_outline" size="22px" />

      <q-menu
        class="auth-menu"
        anchor="bottom right"
        self="top right"
        :offset="[4, 8]"
      >
        <q-list dense class="auth-list">
          <q-item v-if="account" class="auth-item auth-item-user">
            <q-item-section>
              <div class="auth-user-name">{{ account.login }}</div>
              <div class="auth-user-role">
                {{ roleLabel }}
              </div>
            </q-item-section>
          </q-item>

          <q-separator v-if="account" />

          <!-- Вход в админку — только для администраторов -->
          <q-item
            v-if="isAdmin"
            clickable
            v-close-popup
            class="auth-item"
            to="/administration"
          >
            <q-item-section>АДМИНКА</q-item-section>
          </q-item>

          <q-item
            v-if="!account"
            clickable
            v-close-popup
            class="auth-item"
            to="/account"
          >
            <q-item-section>ВОЙТИ</q-item-section>
          </q-item>

          <q-item
            v-if="!account"
            clickable
            v-close-popup
            class="auth-item"
            to="/account?tab=register"
          >
            <q-item-section>РЕГИСТРАЦИЯ</q-item-section>
          </q-item>

          <q-item clickable v-close-popup class="auth-item" to="/account">
            <q-item-section>ПОРТФЕЛЬ</q-item-section>
          </q-item>

          <q-item
            v-if="account"
            clickable
            v-close-popup
            class="auth-item auth-item-exit"
            @click="handleLogout"
          >
            <q-item-section>ВЫХОД</q-item-section>
          </q-item>
        </q-list>
      </q-menu>
    </q-btn>

    <!-- БУРГЕР (только мобильная версия) -->
    <button
      type="button"
      class="burger"
      :class="{ 'is-open': mobileOpen }"
      aria-label="Меню"
      :aria-expanded="mobileOpen"
      @click="mobileOpen = !mobileOpen"
    >
      <span></span>
      <span></span>
      <span></span>
    </button>

    <!-- ВЫПАДАЮЩЕЕ МЕНЮ (мобильная версия) -->
    <Transition name="mobile-menu">
      <div v-if="mobileOpen" class="mobile-panel">
        <nav class="mobile-nav">
          <template v-for="item in navItems" :key="item.key">
            <a
              v-if="isExternalCmsUrl(item.safeUrl)"
              :href="item.safeUrl"
              class="mobile-nav-link"
              >{{ item.label }}</a
            >
            <RouterLink v-else :to="item.safeUrl" class="mobile-nav-link">
              {{ item.label }}
            </RouterLink>
          </template>

          <!-- ПОРТФЕЛЬ — последний пункт, раскрывает панель на месте -->
          <button
            type="button"
            class="mobile-nav-link mobile-portfolio-toggle"
            :class="{ 'is-open': mobilePortfolioOpen }"
            :aria-expanded="mobilePortfolioOpen"
            @click="mobilePortfolioOpen = !mobilePortfolioOpen"
          >
            <span>ПОРТФЕЛЬ</span>

            <span v-if="count" class="mobile-portfolio-badge">
              {{ count }}
            </span>
          </button>

          <div v-if="mobilePortfolioOpen" class="mobile-portfolio-panel">
            <PortfolioPanel variant="dropdown" @navigate="closeMobileMenu" />
          </div>
        </nav>

        <div class="mobile-contacts">
          <div class="mobile-address">
            Ростов-на-Дону · ул. Социалистическая, 73
          </div>

          <a href="tel:+78633203020" class="mobile-contact-link">
            8 (863) 320-30-20
          </a>

          <a href="mailto:reclama@albion.su" class="mobile-contact-link">
            reclama@albion.su
          </a>

          <a href="mailto:albion3@albion.su" class="mobile-contact-link">
            albion3@albion.su
          </a>
        </div>
      </div>
    </Transition>
  </header>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import PortfolioPanel from '../portfolio/PortfolioPanel.vue'
import ChatSaveButton from '../chat/ChatSaveButton.vue'
import SmartChatPanel from '../chat/SmartChatPanel.vue'
import { useAccount } from '../../composables/useAccount'
import { useChatWorkspace } from '../../composables/useChatWorkspace'
import { usePortfolio } from '../../composables/usePortfolio'
import { safeCmsUrl } from '../../utils/safeCmsUrl'

const route = useRoute()
const router = useRouter()

/* Состояние личного кабинета: вход/выход прямо из шапки */
const { account, isAuthenticated, logout, loadMe } = useAccount()

/* Чаты общие с большим окном: в маленьком окне показываем тот же список. */
const { chats, addChat, openWorkspace } = useChatWorkspace()

/* Портфель: счётчик для бейджа и синхронизация с ЛК */
const { count, mergeFromAccount } = usePortfolio()

/* Подпись роли в меню аккаунта. */
const roleLabel = computed(() => {
  const role = account.value?.role

  if (role === 'admin') return 'Администратор'
  if (role === 'manager') return 'Менеджер'

  return 'Клиент'
})

/* Пункт «Админка» показываем только администраторам. */
const isAdmin = computed(() => account.value?.role === 'admin')

async function handleLogout() {
  await logout()
  router.push('/account')
}

const DEFAULT_MENU = [
  { key: 'home', label: 'ГЛАВНАЯ СТРАНИЦА', url: '/' },
  { key: 'vozmozhnosti', label: 'ВОЗМОЖНОСТИ', url: '/vozmozhnosti' },
  { key: 'napravleniya', label: 'ДЕЯТЕЛЬНОСТЬ', url: '/napravleniya' },
  { key: 'novosti', label: 'НОВОСТИ', url: '/novosti' },
  { key: 'informaciya', label: 'ИНФОРМАЦИЯ', url: '/informaciya' },
  { key: 'o-kompanii', label: 'О КОМПАНИИ', url: '/o-kompanii' },
  { key: 'kontakty', label: 'КОНТАКТЫ', url: '/kontakty' }
]

const menuItems = ref(DEFAULT_MENU)

/*
 * Пункт «Портфель» мы рисуем сами и всегда ставим последним, после
 * «Контактов». Любую ссылку из CMS, ведущую на /portfolio, отбрасываем,
 * чтобы не было дубля.
 */
function isPortfolioUrl(url) {
  return String(url || '').replace(/\/+$/, '') === '/portfolio'
}

const navItems = computed(() =>
  menuItems.value
    .map(item => ({ ...item, safeUrl: safeCmsUrl(item.url) }))
    .filter(item => item.safeUrl && !isPortfolioUrl(item.safeUrl))
)

function isExternalCmsUrl(url) {
  return /^(https?:|mailto:|tel:)/i.test(String(url || ''))
}

/* Выпадающая панель портфеля в шапке (десктоп/планшет) */
const portfolioOpen = ref(false)

/* Окно «Умного чата» (выпадает вниз, как портфель). */
const chatOpen = ref(false)

/* При открытии окна поднимаем чаты и создаём первый, если их ещё нет. */
watch(chatOpen, open => {
  if (open) openWorkspace()
})

/* Мобильное выпадающее меню */
const mobileOpen = ref(false)

/* Секция портфеля внутри мобильного меню */
const mobilePortfolioOpen = ref(false)

/* Закрываем меню при переходе по ссылке */
watch(
  () => route.path,
  () => {
    mobileOpen.value = false
    mobilePortfolioOpen.value = false
  }
)

/*
 * Единственная точка синхронизации портфеля с ЛК: шапка смонтирована
 * всегда, поэтому именно здесь ловим появление авторизации и объединяем
 * локальный и серверный портфели.
 */
watch(
  isAuthenticated,
  value => {
    if (value) {
      mergeFromAccount()
    }
  },
  { immediate: true }
)

/* Закрыть мобильное меню (после действия в панели) */
function closeMobileMenu() {
  mobileOpen.value = false
  mobilePortfolioOpen.value = false
}

onMounted(async () => {
  try {
    const response = await fetch('/api/site-menu')
    const data = await response.json()

    if (data?.main?.length) {
      menuItems.value = data.main
    }
  } catch (exc) {
    /* остаёмся на значениях по умолчанию */
  }

  /* Подтягиваем данные кабинета, если пользователь уже входил */
  await loadMe()
})
</script>

<style scoped>
.header {
  height: 78px;

  display: flex;
  align-items: center;

  gap: 20px;

  padding: 0 24px;

  background: #fff;

  border-bottom: 1px solid #e5e9ec;

  /* Шапка не уходит при прокрутке страницы */
  position: sticky;
  top: 0;
  z-index: 1000;

  white-space: nowrap;
}

/* ---------------------------------------------------------
   LOGO
--------------------------------------------------------- */

.brand {
  flex: 0 0 auto;

  display: flex;
  align-items: center;

  text-decoration: none;
}

.logo {
  display: block;

  width: auto;
  height: 42px;

  max-width: 150px;

  object-fit: contain;
}

/* ---------------------------------------------------------
   CONTACT
--------------------------------------------------------- */

.header-contact {
  flex: 0 0 auto;

  display: flex;
  flex-direction: column;

  gap: 4px;

  min-width: 245px;
}

.address {
  color: #17212b;

  font-size: 11px;
  font-weight: 700;

  line-height: 1.2;
}

.emails {
  display: flex;
  align-items: center;
  gap: 6px;

  font-size: 10px;
}

.emails a {
  color: #71808c;

  font-weight: 700;

  text-decoration: none;
}

.emails a:hover {
  color: var(--albion-accent);
}

/* ---------------------------------------------------------
   NAVIGATION
--------------------------------------------------------- */

.header-nav {
  flex: 1 1 auto;

  display: flex;
  align-items: center;
  justify-content: center;

  gap: 22px;

  min-width: 0;
}

.header-nav a {
  position: relative;

  color: #17212b;

  font-size: 12px;
  font-weight: 900;

  letter-spacing: 0.25px;

  text-decoration: none;

  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.header-nav a:hover {
  color: var(--albion-accent);
  transform: translateY(-1px);
}

/* Подсветка — только при точном совпадении маршрута,
   чтобы «Главная страница» (корень /) не была выделена постоянно */
.header-nav a.router-link-exact-active {
  color: var(--albion-accent);
}

.header-nav a.router-link-exact-active::after {
  content: '';

  position: absolute;

  left: 0;
  right: 0;
  bottom: -10px;

  height: 3px;

  border-radius: 2px;

  background: var(--albion-accent);
}

/* ---------------------------------------------------------
   ПОРТФЕЛЬ (кнопка с бейджем и выпадающей панелью)
--------------------------------------------------------- */

/* Кнопка выглядит как обычная ссылка навигации */
.header-nav .nav-portfolio {
  min-height: 0;
  height: auto;

  padding: 0;

  color: #17212b;

  font-size: 12px;
  font-weight: 900;

  letter-spacing: 0.25px;
  line-height: 1.2;

  transition:
    color 0.15s ease,
    transform 0.15s ease;
}

.header-nav .nav-portfolio .q-btn__content {
  gap: 6px;
}

.header-nav .nav-portfolio:hover,
.header-nav .nav-portfolio.is-active {
  color: var(--albion-accent);
}

.header-nav .nav-portfolio:hover {
  transform: translateY(-1px);
}

.nav-portfolio-icon {
  display: grid;
  place-items: center;
}

.nav-portfolio-icon svg {
  display: block;
}

.nav-portfolio-badge {
  display: grid;
  place-items: center;

  min-width: 18px;
  height: 18px;

  padding: 0 5px;

  border-radius: 9px;

  background: var(--albion-accent);
  color: #fff;

  font-size: 10px;
  font-weight: 900;

  line-height: 1;
}

/* ---------------------------------------------------------
   PHONE
--------------------------------------------------------- */

.phone {
  flex: 0 0 auto;

  display: flex;
  align-items: center;

  gap: 8px;

  color: #17212b;

  font-size: 18px;
  font-weight: 900;

  letter-spacing: 0.1px;

  text-decoration: none;

  transition: color 0.15s ease;
}

.phone:hover {
  color: var(--albion-accent);
}

.phone-icon {
  display: grid;
  place-items: center;

  width: 30px;
  height: 30px;

  border-radius: 50%;

  background: #f1f3f4;

  color: #17212b;
}

.phone-icon svg {
  display: block;
}

/* ---------------------------------------------------------
   SOCIAL
--------------------------------------------------------- */

.socials {
  display: flex;
  align-items: center;

  gap: 5px;
}

.social {
  width: 25px;
  height: 25px;

  display: grid;
  place-items: center;

  border-radius: 7px;

  background: #f1f3f4;

  color: #52606a;

  font-size: 8px;
  font-weight: 900;

  text-decoration: none;

  transition: 0.15s ease;
}

.social:hover {
  background: var(--albion-accent);
  color: #fff;
}

/* «Макс» — 4 символа, немного шире остальных */
.social.max {
  width: auto;
  min-width: 25px;
  padding: 0 4px;

  font-size: 7px;
  letter-spacing: 0;
}

/* ---------------------------------------------------------
   SMART CHAT
--------------------------------------------------------- */

.smart-chat {
  flex: 0 0 auto;

  display: flex;
  align-items: center;

  gap: 7px;

  padding: 9px 11px;

  border: 0;
  border-radius: 9px;

  background: #17212b;

  color: #fff;

  font-family: inherit;
  font-size: 9px;
  font-weight: 900;

  text-decoration: none;

  cursor: pointer;

  transition: 0.15s ease;
}

.smart-chat:hover {
  background: var(--albion-accent);
}

.chat-icon {
  font-size: 12px;
}

/* Окно «Умного чата» — размер как у панели портфеля. */
.smart-chat-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;

  width: min(760px, 92vw);
  min-height: 320px;
  max-height: 70vh;

  overflow: hidden;

  padding: 16px 18px;

  background: #fff;
  color: #17212b;
}

.smart-chat-head {
  display: flex;
  align-items: center;
  gap: 8px;

  flex-shrink: 0;

  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.smart-chat-head-icon {
  font-size: 14px;
}

/* Кнопка «Сохранить» в шапке окна — прижата вправо. */
.smart-chat-save {
  margin-left: auto;
}

.smart-chat-body {
  flex: 1 1 auto;
  min-height: 0;

  overflow-y: auto;

  color: #64748b;
  font-size: 14px;
}

/* Пустое состояние маленького окна после очистки чатов. */
.smart-chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;

  padding: 32px 12px;

  color: #8b98a3;
  font-size: 13px;
  text-align: center;
}

/* ---------------------------------------------------------
   RESPONSIVE
--------------------------------------------------------- */

@media (max-width: 1450px) {
  .header {
    gap: 14px;
    padding: 0 18px;
  }

  .header-contact {
    min-width: 210px;
  }

  .header-nav {
    gap: 14px;
  }

  .header-nav a {
    font-size: 10px;
  }

  .phone {
    font-size: 12px;
  }
}

@media (max-width: 1200px) {
  .header-contact {
    display: none;
  }
}

/* ---------------------------------------------------------
   ДВУХРЯДНАЯ ШАПКА (планшет: 901–1200px)
   Ряд 1: логотип, телефон, соцсети, «Умный чат», авторизация
   Ряд 2: навигация в две строки (4 + 4), по центру
--------------------------------------------------------- */

@media (max-width: 1200px) and (min-width: 901px) {
  .header {
    height: auto;

    display: grid;

    grid-template-columns: auto 1fr auto auto auto auto;

    grid-template-areas:
      'brand spacer phone socials chat auth'
      'nav nav nav nav nav nav';

    align-items: center;

    column-gap: 16px;
    row-gap: 8px;

    padding: 10px 18px;
  }

  .brand {
    grid-area: brand;
  }

  .phone {
    grid-area: phone;
  }

  .socials {
    grid-area: socials;
  }

  .smart-chat {
    grid-area: chat;
  }

  .auth-button {
    grid-area: auth;
  }

  .header-nav {
    grid-area: nav;

    display: grid;
    grid-template-columns: repeat(4, max-content);

    justify-content: center;
    justify-items: center;

    column-gap: 30px;
    row-gap: 10px;
  }

  .header-nav a.router-link-exact-active::after {
    bottom: -5px;
  }
}

/* ---------------------------------------------------------
   МОБИЛЬНАЯ ВЕРСИЯ (≤900px): бургер + выпадающее меню
--------------------------------------------------------- */

@media (max-width: 900px) {
  .header {
    height: 64px;
  }

  .logo {
    height: 36px;
    max-width: 125px;
  }

  /* Основная навигация уезжает в выпадающее меню */
  .header-nav {
    display: none;
  }

  .phone {
    margin-left: auto;
  }

  /* ------------- Бургер ------------- */
  .burger {
    flex: 0 0 auto;

    display: flex;
    flex-direction: column;
    justify-content: center;

    gap: 5px;

    width: 40px;
    height: 40px;

    padding: 0 9px;

    border: none;
    border-radius: 9px;

    background: #f1f3f4;

    cursor: pointer;

    transition: background 0.15s ease;
  }

  .burger:hover {
    background: var(--albion-accent);
  }

  .burger span {
    display: block;

    width: 100%;
    height: 2px;

    border-radius: 2px;

    background: #17212b;

    transition:
      transform 0.25s ease,
      opacity 0.2s ease,
      background 0.15s ease;
  }

  .burger:hover span {
    background: #fff;
  }

  /* Крестик в открытом состоянии */
  .burger.is-open span:nth-child(1) {
    transform: translateY(7px) rotate(45deg);
  }

  .burger.is-open span:nth-child(2) {
    opacity: 0;
  }

  .burger.is-open span:nth-child(3) {
    transform: translateY(-7px) rotate(-45deg);
  }

  /* ------------- Выпадающая панель ------------- */
  .mobile-panel {
    position: fixed;
    top: 64px;
    left: 0;
    right: 0;

    z-index: 900;

    display: flex;
    flex-direction: column;

    gap: 16px;

    max-height: calc(100vh - 64px);

    overflow-y: auto;

    padding: 14px 16px 22px;

    background: #fff;

    border-bottom: 1px solid #e5e9ec;

    box-shadow: 0 16px 30px rgba(25, 35, 45, 0.14);
  }

  .mobile-nav {
    display: flex;
    flex-direction: column;
  }

  .mobile-nav-link {
    padding: 14px 6px;

    border-bottom: 1px solid #eef1f3;

    color: #17212b;

    font-size: 14px;
    font-weight: 900;

    letter-spacing: 0.3px;

    text-decoration: none;

    transition: color 0.15s ease;
  }

  .mobile-nav-link:hover,
  .mobile-nav-link.router-link-exact-active {
    color: var(--albion-accent);
  }

  /* Кнопка «Портфель» в мобильном меню */
  .mobile-portfolio-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;

    width: 100%;

    border: none;
    background: none;

    font-family: inherit;
    text-align: left;

    cursor: pointer;
  }

  .mobile-portfolio-toggle.is-open {
    color: var(--albion-accent);
  }

  .mobile-portfolio-badge {
    display: grid;
    place-items: center;

    min-width: 22px;
    height: 22px;

    padding: 0 7px;

    border-radius: 11px;

    background: var(--albion-accent);
    color: #fff;

    font-size: 11px;
    font-weight: 900;

    line-height: 1;
  }

  /* Панель портфеля внутри мобильного меню */
  .mobile-portfolio-panel {
    padding: 8px 0 4px;
  }

  .mobile-portfolio-panel :deep(.portfolio-panel--dropdown) {
    width: 100%;
    max-height: none;

    padding: 12px;
  }

  /* Компактный блок контактов */
  .mobile-contacts {
    display: flex;
    flex-direction: column;

    gap: 6px;

    padding-top: 2px;
  }

  .mobile-address {
    color: #17212b;

    font-size: 12px;
    font-weight: 700;

    line-height: 1.3;
  }

  .mobile-contact-link {
    color: #71808c;

    font-size: 13px;
    font-weight: 700;

    text-decoration: none;

    transition: color 0.15s ease;
  }

  .mobile-contact-link:hover {
    color: var(--albion-accent);
  }
}

@media (max-width: 600px) {
  .phone span:last-child {
    display: none;
  }

  .socials {
    display: none;
  }

  .smart-chat-label {
    display: none;
  }
}

/* Бургер и выпадающая панель скрыты только на десктопе.
   Не размещать эти правила после мобильного media query: тогда они
   переопределят display:flex у бургера на узком экране. */
@media (min-width: 901px) {
  .burger,
  .mobile-panel {
    display: none;
  }
}

/* Плавное появление выпадающего меню */
.mobile-menu-enter-active,
.mobile-menu-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.mobile-menu-enter-from,
.mobile-menu-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Кнопка авторизации (сам элемент в шапке) */
.auth-button {
  flex: 0 0 auto;
  color: #17212b;
}

.auth-button:hover {
  color: var(--albion-accent);
  background: #f1f3f4;
}
</style>

<style>
/* Меню авторизации рендерится в портале — нужны глобальные стили */
.auth-menu {
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(25, 35, 45, 0.15);
  overflow: hidden;
}

.auth-menu .auth-list {
  min-width: 170px;
}

.auth-menu .auth-item {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #17212b;
}

.auth-menu .auth-item:hover {
  background: #f5f6f7;
}

.auth-menu .auth-item-exit {
  color: #c62828;
}

.auth-menu .auth-item-user {
  cursor: default;
}

.auth-menu .auth-item-user:hover {
  background: transparent;
}

.auth-user-name {
  color: #17212b;
  font-size: 13px;
  font-weight: 900;
}

.auth-user-role {
  color: #71808c;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* Меню портфеля рендерится в портале — нужны глобальные стили */
.portfolio-menu {
  border-radius: 14px;
  box-shadow: 0 18px 40px rgba(25, 35, 45, 0.18);
  overflow: hidden;

  /* Снимаем умолчательный max-height q-menu (65vh): высотой управляет
     сама панель портфеля, иначе её нижний блок с кнопками обрезался
     меню, хотя список внутри панели прокручивался. */
  max-height: none;
}
</style>
