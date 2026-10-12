/*
 * SEO для SPA: заголовок, description, keywords, canonical и Open Graph.
 *
 * Значения берутся из /api/seo (правится в админке, раздел «SEO») и
 * применяются к <head> при каждой смене маршрута — иначе у всех страниц
 * сайта был бы один и тот же заголовок из index.html, что для поиска плохо.
 */
import { ref } from 'vue'

export const seoConfig = ref(null)

let cache = null
let pending = null

function upsertMeta(attr, key, content) {
  if (!content) {
    return
  }

  let el = document.head.querySelector(`meta[${attr}="${key}"]`)

  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }

  el.setAttribute('content', content)
}

function upsertLink(rel, href) {
  let el = document.head.querySelector(`link[rel="${rel}"]`)

  if (!href) {
    el?.remove()
    return
  }

  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', rel)
    document.head.appendChild(el)
  }

  el.setAttribute('href', href)
}

function upsertJsonLd(id, data) {
  let el = document.getElementById(id)

  if (!data) {
    el?.remove()
    return
  }

  if (!el) {
    el = document.createElement('script')
    el.type = 'application/ld+json'
    el.id = id
    document.head.appendChild(el)
  }

  el.textContent = JSON.stringify(data)
}

/* Настройки страницы: для вложенных маршрутов — от первого сегмента. */
function pageSeo(config, path) {
  const pages = config?.pages || {}

  if (pages[path]) {
    return pages[path]
  }

  const segment =
    '/' +
    String(path || '')
      .split('/')
      .filter(Boolean)[0]

  return pages[segment] || null
}

function absolute(url) {
  const base = String(seoConfig.value?.site_url || '').replace(/\/+$/, '')

  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  if (!base) return url

  return base + (url.startsWith('/') ? url : '/' + url)
}

export async function loadSeo() {
  if (cache) {
    return cache
  }

  if (!pending) {
    pending = fetch('/api/seo')
      .then(response => (response.ok ? response.json() : null))
      .catch(() => null)
  }

  cache = await pending
  seoConfig.value = cache

  return cache
}

/* Применяет SEO-настройки к <head> для указанного пути. */
export function applySeo(path) {
  const config = seoConfig.value

  if (!config) {
    return
  }

  const page = pageSeo(config, path) || {}

  const title = page.title || config.default_title || config.site_name || ''
  const description = page.description || config.default_description || ''
  const keywords = page.keywords || config.default_keywords || ''
  const canonical = absolute(path === '/' ? '/' : path)

  document.title = title

  upsertMeta('name', 'description', description)
  upsertMeta('name', 'keywords', keywords)
  upsertMeta('name', 'robots', 'index, follow')

  upsertMeta('property', 'og:type', 'website')
  upsertMeta('property', 'og:site_name', config.site_name)
  upsertMeta('property', 'og:title', title)
  upsertMeta('property', 'og:description', description)
  upsertMeta('property', 'og:url', canonical)
  upsertMeta('property', 'og:image', absolute(config.og_image))
  upsertMeta('property', 'og:locale', 'ru_RU')

  upsertMeta('name', 'twitter:card', 'summary_large_image')
  upsertMeta('name', 'twitter:title', title)
  upsertMeta('name', 'twitter:description', description)

  upsertLink('canonical', canonical)

  /* Микроразметка организации — помогает Яндексу и Google. */
  upsertJsonLd(
    'seo-org',
    config.site_name
      ? {
          '@context': 'https://schema.org',
          '@type': 'Organization',
          name: config.site_name,
          url: absolute('/'),
          description: config.default_description || undefined,
          address: {
            '@type': 'PostalAddress',
            addressLocality: 'Ростов-на-Дону',
            addressCountry: 'RU'
          }
        }
      : null
  )
}

/* Подписка на смену маршрута + первичное применение. */
export async function initSeo(router) {
  await loadSeo()

  router.afterEach(to => applySeo(to.path))
  applySeo(router.currentRoute.value.path)
}
