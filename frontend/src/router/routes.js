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
      }
    ]
  },


  {
    path: '/:catchAll(.*)*',
    component: () => import('@/pages/ErrorNotFound.vue')
  }
]

export default routes
