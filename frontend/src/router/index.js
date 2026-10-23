import { defineRouter } from '#q-app'
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory
} from 'vue-router'

import routes from './routes.js'
import { getAdminToken } from '../services/adminApi'

/*
 * If not building with SSR mode, you can
 * directly export the Router instantiation;
 *
 * The function below can be async too; either use
 * async/await or return a Promise which resolves
 * with the Router instance.
 */

export default defineRouter((/* { store, ssrContext } */) => {
  const createHistory = import.meta.env.QUASAR_SERVER
    ? createMemoryHistory
    : import.meta.env.QUASAR_VUE_ROUTER_MODE === 'history'
      ? createWebHistory
      : createWebHashHistory

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,

    // Leave this as is and make changes in quasar.conf.js instead!
    // quasar.conf.js -> build -> vueRouterMode
    // quasar.conf.js -> build -> publicPath
    history: createHistory(import.meta.env.QUASAR_VUE_ROUTER_BASE)
  })

  Router.beforeEach(to => {
    if (!to.meta.requiresAdmin) {
      return true
    }

    const token = getAdminToken()

    if (!token) {
      return {
        path: '/administration',
        replace: true
      }
    }

    return true
  })

  /*
   * Без этого обработчика ошибка навигации (например, исключение в
   * лениво-загружаемом компоненте) остаётся невидимой: Vue Router пишет
   * лишь VUE_ROUTER_R0010/R0011 без первопричины. Логируем реальную
   * ошибку с указанием маршрута, чтобы её было видно в консоли.
   */
  Router.onError((error, to) => {
    console.error(
      `[router] Ошибка навигации на "${to?.fullPath ?? '?'}":`,
      error
    )
  })

  return Router
})
