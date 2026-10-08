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

      {
        path: 'account',
        component: () => import('@/pages/AccountPage.vue')
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
        path: 'base',
        component: () => import('@/pages/AdministrationBasePage.vue'),
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
        path: 'news',
        component: () => import('@/pages/AdministrationNewsPage.vue'),
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
      }
    ]
  },


  {
    path: '/informaciya',
    component: () => import('@/pages/PlaceholderPage.vue'),
    props: { title: 'Информация' }
  },

  {
    path: '/portfolio',
    component: () => import('@/pages/PlaceholderPage.vue'),
    props: { title: 'Портфель' }
  },

  {
    path: '/:catchAll(.*)*',
    component: () => import('@/pages/ErrorNotFound.vue')
  }
]

export default routes
