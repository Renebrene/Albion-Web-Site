// Configuration for your app
// https://v2.quasar.dev/quasar-cli-vite/quasar-config-file

import { defineConfig } from '#q-app'

export default defineConfig((/* ctx */) => {
  return {
    // https://v2.quasar.dev/quasar-cli-vite/prefetch-feature
    // preFetch: true,

    // app boot file (/src/boot)
    // --> boot files are part of "main.js"
    // https://v2.quasar.dev/quasar-cli-vite/boot-files
    boot: ['tracking'],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-file#css
    css: ['app.scss'],

    // https://github.com/quasarframework/quasar/tree/dev/extras
    //
    // 'roboto-font' убран: тема сайта по умолчанию использует системный
    // шрифт (font_family/font_heading = 'system'), а сам Roboto тянул в
    // бандл ~160 КБ (6 начертаний woff). Нужный шрифт теперь лениво
    // грузится с Google Fonts, только если он выбран в настройках
    // (см. src/config/fontLoader.js).
    extras: [
      'material-icons' // optional, you are not bound to it
    ],

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-file#build
    build: {
      target: {
        // browser: 'baseline-widely-available',
        // node: 'node22'
      },

      vueRouterMode: 'history', // available values: 'hash', 'history'

      // 👇 ДОБАВЛЕНО: Разрешаем конкретный хост для Vite
      extendViteConf(viteConf) {
        viteConf.server = viteConf.server || {}
        viteConf.server.allowedHosts = ['albion.cloudpub.ru']

        // Если нужно разрешить абсолютно любые хосты (например, для ngrok),
        // замените строку выше на:
        // viteConf.server.allowedHosts = true
      }

      // viteVuePluginOptions: {},
      // vueJsx: true,
      // vitePlugins: [
      //   [ 'package-name', { ..pluginOptions.. }, { server: true, client: true } ]
      // ]
    },

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-file#devserver
    devServer: {
      // vueDevtools: true,
      // https: true,
      open: true,

      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        },
        '/storage': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    },

    // https://v2.quasar.dev/quasar-cli-vite/quasar-config-file#framework
    framework: {
      config: {},
      plugins: []
    },

    // https://v2.quasar.dev/options/animations
    animations: [],

    // https://v2.quasar.dev/quasar-cli-vite/developing-ssr/configuring-ssr
    ssr: {
      prodPort: 3000,
      middlewares: [
        'render' // keep this as last one
      ]
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-ssg/configuring-ssg
    ssg: {
      // onSsgRendererError: 'abort',
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-pwa/configuring-pwa
    pwa: {
      workboxMode: 'GenerateSW' // 'GenerateSW' or 'InjectManifest'
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-cordova-apps/configuring-cordova
    cordova: {},

    // https://v2.quasar.dev/quasar-cli-vite/developing-capacitor-apps/configuring-capacitor
    capacitor: {
      hideSplashscreen: true
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-electron-apps/configuring-electron
    electron: {
      preloadScripts: ['electron-preload'],
      inspectPort: 5858,
      bundler: 'packager', // 'packager' or 'builder'

      packager: {
        // OS X / Mac App Store
        // appBundleId: '',
        // appCategoryType: '',
        // osxSign: '',
        // protocol: 'myapp://path',
        // Windows only
        // win32metadata: { ... }
      },

      builder: {
        appId: 'frontend'
      }
    },

    // https://v2.quasar.dev/quasar-cli-vite/developing-browser-extensions/configuring-bex
    bex: {
      extraScripts: []
    }
  }
})
