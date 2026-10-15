import { ACCOUNT_UI_ENABLED } from '../config/features'
const routes = [
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),

    children: [
      {
        path: '',
        component: () => import('@/pages/HomePage.vue')
      },

      {
        path: 'vozmozhnosti',
        component: () => import('@/pages/AdvertisingPage.vue')
      },

      {
        path: 'napravleniya',
        component: () => import('@/pages/DirectionsPage.vue')
      },

      {
        path: 'novosti',
        component: () => import('@/pages/NewsPage.vue')
      },

      {
        path: 'novosti/:slug',
        component: () => import('@/pages/NewsDetailPage.vue')
      },

      {
        path: 'o-kompanii',
        component: () => import('@/pages/AboutPage.vue')
      },

      {
        path: 'kontakty',
        component: () => import('@/pages/ContactsPage.vue')
      },

      {
        path: 'chat',
        component: () => import('@/pages/SmartChatPage.vue')
      },

      /*
       * Личный кабинет скрыт (ACCOUNT_UI_ENABLED = false): адрес ведёт на
       * публичную страницу портфеля. Код кабинета сохранён — включается
       * флагом, см. config/features.js и doc/account-cabinet.md.
       */
      ACCOUNT_UI_ENABLED
        ? {
            path: 'account',
            component: () => import('@/pages/AccountPage.vue')
          }
        : {
            path: 'account',
            redirect: '/portfolio'
          },

      /*
       * «Информация» — закладки (ОБЩЕЕ, КОНСТРУКЦИИ, ГОРОДА И РАЙОНЫ,
       * ТЕХ ТРЕБОВАНИЯ и др.). Состав и содержание закладок задаются
       * в админке (/administration/info).
       */
      {
        path: 'informaciya',
        component: () => import('@/pages/InfoPage.vue')
      },

      {
        path: 'portfolio',
        component: () => import('@/pages/PortfolioPage.vue')
      }
    ]
  },

  {
    path: '/administration',
    component: () => import('@/layouts/AdministrationLayout.vue'),

    children: [
      {
        path: '',
        component: () => import('@/pages/AdministrationLoginPage.vue')
      },
      {
        path: 'dashboard',
        component: () => import('@/pages/AdministrationDashboardPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'media',
        component: () => import('@/pages/AdministrationMediaPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'constructions',
        component: () => import('@/pages/AdministrationConstructionsPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'chat-log',
        component: () => import('@/pages/AdministrationChatLogPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'base',
        component: () => import('@/pages/AdministrationBasePage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'site',
        component: () => import('@/pages/AdministrationSitePage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'contacts',
        component: () => import('@/pages/AdministrationContactsPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'site-menu',
        component: () => import('@/pages/AdministrationSiteMenuPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'settings',
        component: () => import('@/pages/AdministrationSettingsPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'seo',
        component: () => import('@/pages/AdministrationSeoPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'news',
        component: () => import('@/pages/AdministrationNewsPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'home',
        component: () => import('@/pages/AdministrationHomePage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'info',
        component: () => import('@/pages/AdministrationInfoPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'about',
        component: () => import('@/pages/AdministrationAboutPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'users',
        component: () => import('@/pages/AdministrationUsersPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'audit',
        component: () => import('@/pages/AdministrationAuditPage.vue'),
        meta: {
          requiresAdmin: true
        }
      },
      {
        path: 'statistics',
        component: () => import('@/pages/AdministrationStatisticsPage.vue'),
        meta: {
          requiresAdmin: true
        }
      }
    ]
  },

  {
    path: '/:catchAll(.*)*',
    component: () => import('@/pages/ErrorNotFound.vue')
  }
]

export default routes
