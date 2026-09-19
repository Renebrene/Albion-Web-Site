<template>
  <header class="header">

    <!-- ЛОГОТИП -->
    <RouterLink
      to="/"
      class="brand"
      aria-label="Albion — главная страница"
    >
      <img
        src="/logo.png"
        alt="Albion"
        class="logo"
      >
    </RouterLink>

    <!-- АДРЕС / EMAIL -->
    <div class="header-contact">
      <div class="address">
        Ростов-на-Дону · ул. Социалистическая, 73
      </div>

      <div class="emails">
        <a href="mailto:reclama@albion.su">
          reclama@albion.su
        </a>

        <span>·</span>

        <a href="mailto:albion3@albion.su">
          albion3@albion.su
        </a>
      </div>
    </div>

    <!-- НАВИГАЦИЯ -->
    <nav class="header-nav">

      <RouterLink to="/">
        ГЛАВНАЯ СТРАНИЦА
      </RouterLink>

      <RouterLink to="/vozmozhnosti">
        ВОЗМОЖНОСТИ
      </RouterLink>

      <RouterLink to="/napravleniya">
        НАПРАВЛЕНИЯ
      </RouterLink>

      <RouterLink to="/novosti">
        НОВОСТИ
      </RouterLink>

      <RouterLink to="/o-kompanii">
        О КОМПАНИИ
      </RouterLink>

      <RouterLink to="/kontakty">
        КОНТАКТЫ
      </RouterLink>

    </nav>

    <!-- ТЕЛЕФОН -->
    <a
      href="tel:+78633203020"
      class="phone"
    >
      <span class="phone-icon">⌕</span>

      <span>
        8 (863) 320-30-20
      </span>
    </a>

    <!-- СОЦСЕТИ -->
    <div class="socials">

      <a
        href="#"
        class="social vk"
        title="ВКонтакте"
        aria-label="ВКонтакте"
      >
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

    </div>

    <!-- УМНЫЙ ЧАТ -->
    <RouterLink
      to="/chat"
      class="smart-chat"
    >
      <span class="chat-icon">✦</span>
      <span>УМНЫЙ ЧАТ</span>
    </RouterLink>

  </header>
</template>

<script setup>
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

  position: relative;
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
  color: #e12a1f;
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

  letter-spacing: .25px;

  text-decoration: none;

  transition:
    color .15s ease,
    transform .15s ease;
}

.header-nav a:hover {
  color: #e12a1f;
  transform: translateY(-1px);
}

.header-nav a.router-link-active {
  color: #e12a1f;
}

.header-nav a.router-link-active::after {
  content: '';

  position: absolute;

  left: 0;
  right: 0;
  bottom: -10px;

  height: 3px;

  border-radius: 2px;

  background: #e12a1f;
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

  font-size: 14px;
  font-weight: 900;

  letter-spacing: .1px;

  text-decoration: none;

  transition: color .15s ease;
}

.phone:hover {
  color: #e12a1f;
}

.phone-icon {
  display: grid;
  place-items: center;

  width: 28px;
  height: 28px;

  border-radius: 50%;

  background: #f1f3f4;

  font-size: 16px;
  font-weight: 900;
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

  transition: .15s ease;
}

.social:hover {
  background: #e12a1f;
  color: #fff;
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

  border-radius: 9px;

  background: #17212b;

  color: #fff;

  font-size: 9px;
  font-weight: 900;

  text-decoration: none;

  transition: .15s ease;
}

.smart-chat:hover {
  background: #e12a1f;
}

.chat-icon {
  font-size: 12px;
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

  .header-nav {
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .header {
    height: 64px;
  }

  .logo {
    height: 36px;
    max-width: 125px;
  }

  .header-nav {
    display: none;
  }

  .phone {
    margin-left: auto;
  }
}

@media (max-width: 600px) {
  .phone span:last-child {
    display: none;
  }

  .socials {
    display: none;
  }

  .smart-chat span:last-child {
    display: none;
  }
}
</style>
