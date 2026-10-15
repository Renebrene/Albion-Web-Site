<template>
  <q-page class="administration-home">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>ГЛАВНАЯ СТРАНИЦА</h1>
        <p>Вертикальные слайды и горизонтальные карточки верхнего слайда.</p>
      </div>

      <div class="header-actions">
        <q-btn
          color="primary"
          no-caps
          label="Обновить"
          :loading="loading"
          @click="load"
        />
        <q-btn
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <div class="toolbar">
      <q-btn
        color="primary"
        no-caps
        icon="add"
        label="Добавить слайд"
        @click="addSlide"
      />
      <span class="hint">
        Верхний слайд (★) листается горизонтальными карточками по стрелкам и
        автоматически раз в 6 сек.
      </span>
    </div>

    <div
      v-for="(slide, slideIndex) in slides"
      :key="slide.id"
      class="slide-card"
      :class="{ 'is-hero': slide.is_hero }"
    >
      <div class="slide-head">
        <span class="slide-order">#{{ slideIndex + 1 }}</span>
        <span v-if="slide.is_hero" class="badge badge-hero">★ верхний</span>
        <span
          class="badge"
          :class="slide.is_active ? 'badge-on' : 'badge-off'"
          >{{ slide.is_active ? 'активен' : 'скрыт' }}</span
        >

        <span class="slide-head-actions">
          <q-btn
            flat
            dense
            no-caps
            label="Сделать верхним"
            :disable="slide.is_hero"
            @click="setHero(slide)"
          />
          <q-btn
            flat
            dense
            no-caps
            :label="slide.is_active ? 'Скрыть' : 'Показать'"
            @click="toggleActive(slide)"
          />
          <q-btn
            color="negative"
            flat
            dense
            no-caps
            label="Удалить"
            @click="removeSlide(slide)"
          />
        </span>
      </div>

      <div class="grid">
        <label class="field">
          <span>Тип слайда</span>
          <q-select
            v-model="slide.kind"
            :options="KIND_OPTIONS"
            dense
            outlined
            emit-value
            map-options
          />
        </label>

        <label class="field">
          <span>Заголовок</span>
          <q-input v-model="slide.title" dense outlined />
        </label>

        <label class="field">
          <span>Текст</span>
          <q-input
            v-model="slide.text"
            dense
            outlined
            type="textarea"
            autogrow
          />
        </label>

        <label class="field">
          <span>Текст кнопки</span>
          <q-input
            v-model="slide.button_label"
            dense
            outlined
            placeholder="Оставить заявку"
          />
        </label>

        <label class="field">
          <span>Ссылка кнопки</span>
          <q-input
            v-model="slide.button_url"
            dense
            outlined
            placeholder="/vozmozhnosti"
          />
        </label>
      </div>

      <div class="photo-row">
        <div
          class="photo-preview"
          :style="
            slide.image
              ? { backgroundImage: `url('${slide.image}')` }
              : undefined
          "
        >
          <span v-if="!slide.image">нет фото</span>
        </div>

        <div class="photo-actions">
          <MediaSourceButtons
            dense
            section="Слайдеры"
            @pick="p => (slide.image = p.url)"
            @notify="onMediaNotify"
          />
          <q-btn
            v-if="slide.image"
            flat
            dense
            no-caps
            label="Убрать фото"
            @click="slide.image = ''"
          />
        </div>
      </div>

      <div class="save-row">
        <q-btn
          color="primary"
          no-caps
          label="Сохранить слайд"
          :loading="savingKey === `slide-${slide.id}`"
          @click="saveSlide(slide)"
        />
      </div>

      <!-- Кнопки слайда (у верхнего hero кнопки задаются у карточек) -->
      <div v-if="!slide.is_hero" class="buttons-block">
        <div class="items-title">
          Кнопки
          <q-btn
            flat
            dense
            no-caps
            icon="add"
            label="Добавить кнопку"
            @click="addSlideButton(slide)"
          />
        </div>

        <div v-for="btn in slide.buttons" :key="btn.id" class="button-row">
          <q-input
            v-model="btn.label"
            dense
            outlined
            placeholder="Текст кнопки"
            class="btn-label"
          />
          <q-input
            v-model="btn.url"
            dense
            outlined
            placeholder="/vozmozhnosti или #form"
            class="btn-url"
          />
          <q-select
            v-model="btn.variant"
            :options="BUTTON_VARIANTS"
            emit-value
            map-options
            dense
            outlined
            class="btn-variant"
          />
          <q-btn
            outline
            dense
            no-caps
            label="Сохранить"
            :loading="savingKey === `btn-${btn.id}`"
            @click="saveButton(btn)"
          />
          <q-btn
            color="negative"
            flat
            dense
            no-caps
            label="Удалить"
            @click="removeButton(btn)"
          />
        </div>

        <div v-if="!(slide.buttons && slide.buttons.length)" class="hint">
          Кнопок нет — показывается стандартная кнопка слайда.
        </div>
      </div>

      <!-- Карточки верхнего слайда -->
      <div v-if="slide.is_hero" class="items-block">
        <div class="items-title">
          Горизонтальные карточки
          <q-btn
            flat
            dense
            no-caps
            icon="add"
            label="Добавить"
            @click="addItem(slide)"
          />
        </div>

        <div
          v-for="(item, itemIndex) in slide.items"
          :key="item.id"
          class="item-card"
        >
          <div class="slide-head">
            <span class="slide-order">карточка {{ itemIndex + 1 }}</span>
            <span class="slide-head-actions">
              <q-btn
                color="negative"
                flat
                dense
                no-caps
                label="Удалить"
                @click="removeItem(slide, item)"
              />
            </span>
          </div>

          <div class="grid">
            <label class="field">
              <span>Надзаголовок</span>
              <q-input
                v-model="item.eyebrow"
                dense
                outlined
                placeholder="Группа компаний"
              />
            </label>
            <label class="field">
              <span>Название/заголовок</span>
              <q-input
                v-model="item.title"
                dense
                outlined
                placeholder="АЛЬБИОН"
              />
            </label>
            <label class="field">
              <span>Слоган (крупно)</span>
              <q-input v-model="item.slogan" dense outlined />
            </label>
            <label class="field">
              <span>Описание</span>
              <q-input
                v-model="item.text"
                dense
                outlined
                type="textarea"
                autogrow
              />
            </label>
            <label class="field">
              <span>Кнопка 1: текст</span>
              <q-input v-model="item.button_label" dense outlined />
            </label>
            <label class="field">
              <span>Кнопка 1: ссылка</span>
              <q-input
                v-model="item.button_url"
                dense
                outlined
                placeholder="/vozmozhnosti"
              />
            </label>
            <label class="field">
              <span>Кнопка 2: текст</span>
              <q-input v-model="item.button2_label" dense outlined />
            </label>
            <label class="field">
              <span>Кнопка 2: ссылка</span>
              <q-input
                v-model="item.button2_url"
                dense
                outlined
                placeholder="#form"
              />
            </label>
            <label class="field">
              <span>Доп. блок</span>
              <q-select
                v-model="item.extra"
                :options="EXTRA_OPTIONS"
                emit-value
                map-options
                dense
                outlined
              />
            </label>
          </div>

          <div class="photo-row">
            <div
              class="photo-preview"
              :style="
                item.image
                  ? { backgroundImage: `url('${item.image}')` }
                  : undefined
              "
            >
              <span v-if="!item.image">нет фото</span>
            </div>

            <div class="photo-actions">
              <MediaSourceButtons
                dense
                section="Слайдеры"
                @pick="p => (item.image = p.url)"
                @notify="onMediaNotify"
              />
              <q-btn
                v-if="item.image"
                flat
                dense
                no-caps
                label="Убрать фото"
                @click="item.image = ''"
              />
            </div>
          </div>

          <div class="save-row">
            <q-btn
              outline
              no-caps
              label="Сохранить карточку"
              :loading="savingKey === `item-${item.id}`"
              @click="saveItem(item)"
            />
          </div>

          <!-- Кнопки карточки hero -->
          <div class="buttons-block">
            <div class="items-title">
              Кнопки карточки
              <q-btn
                flat
                dense
                no-caps
                icon="add"
                label="Добавить кнопку"
                @click="addItemButton(item)"
              />
            </div>

            <div v-for="btn in item.buttons" :key="btn.id" class="button-row">
              <q-input
                v-model="btn.label"
                dense
                outlined
                placeholder="Текст кнопки"
                class="btn-label"
              />
              <q-input
                v-model="btn.url"
                dense
                outlined
                placeholder="/vozmozhnosti или #form"
                class="btn-url"
              />
              <q-select
                v-model="btn.variant"
                :options="BUTTON_VARIANTS"
                emit-value
                map-options
                dense
                outlined
                class="btn-variant"
              />
              <q-btn
                outline
                dense
                no-caps
                label="Сохранить"
                :loading="savingKey === `btn-${btn.id}`"
                @click="saveButton(btn)"
              />
              <q-btn
                color="negative"
                flat
                dense
                no-caps
                label="Удалить"
                @click="removeButton(btn)"
              />
            </div>

            <div v-if="!(item.buttons && item.buttons.length)" class="hint">
              Кнопок нет — показываются старые поля «Кнопка 1/2».
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!slides.length && !loading" class="empty-text">
      Слайдов пока нет — добавьте первый.
    </div>

    <!-- Geo-контент слайда «Возможности» -->
    <section class="section-card geo-admin">
      <div class="section-title">
        <div>Города, районы и достопримечательности</div>
        <q-btn flat dense no-caps label="Обновить" @click="loadGeo" />
      </div>
      <div class="geo-settings-row">
        <q-toggle
          :model-value="geo.settings.map_links_enabled"
          label="Разрешить переходы городов и районов на карту"
          @update:model-value="saveGeoSettings"
        />
        <span class="hint"
          >Отключение оставляет список кликабельным без перехода.</span
        >
      </div>

      <div class="geo-settings-row">
        <q-select
          :model-value="geo.settings.deck_wheel_mode"
          :options="WHEEL_MODES"
          emit-value
          map-options
          dense
          outlined
          class="geo-wheel"
          label="Управление колодой карточек колесом мыши"
          @update:model-value="saveGeoWheelMode"
        />
        <span class="hint"> Клик по карточке всегда раскрывает описание. </span>
      </div>

      <div class="geo-admin-columns">
        <div>
          <div class="items-title">
            Города и районы
            <q-btn
              flat
              dense
              no-caps
              icon="add"
              label="Добавить"
              @click="addGeoLocation"
            />
          </div>
          <div
            v-for="location in geo.locations"
            :key="location.id"
            class="geo-location-admin"
          >
            <div class="geo-admin-row">
              <q-select
                v-model="location.kind"
                :options="LOCATION_KINDS"
                emit-value
                map-options
                dense
                outlined
                class="geo-kind"
                @update:model-value="saveGeoLocation(location)"
              />
              <q-input
                v-model="location.label"
                dense
                outlined
                class="geo-label"
              />
              <q-input
                v-model="location.map_value"
                dense
                outlined
                class="geo-label"
                placeholder="Значение для карты"
              />
              <q-toggle
                v-model="location.is_active"
                dense
                @update:model-value="saveGeoLocation(location)"
              />
              <q-btn
                flat
                dense
                color="negative"
                icon="delete"
                @click="removeGeoLocation(location)"
              />
            </div>
            <div class="geo-admin-sub">
              <q-input
                v-model="location.description"
                dense
                outlined
                type="textarea"
                autogrow
                class="geo-desc"
                label="Описание (абзацы — показываются в модальном окне)"
              />
              <div class="geo-admin-sub-side">
                <q-select
                  v-model="location.cover_attraction_id"
                  :options="attractionsFor(location)"
                  option-value="id"
                  option-label="title"
                  emit-value
                  map-options
                  clearable
                  dense
                  outlined
                  class="geo-cover"
                  label="Фото-обложка (достопримечательность)"
                />
                <q-btn
                  outline
                  dense
                  no-caps
                  label="Сохранить"
                  @click="saveGeoLocation(location)"
                />
              </div>
            </div>
          </div>
        </div>

        <div>
          <div class="items-title">
            Достопримечательности
            <q-btn
              flat
              dense
              no-caps
              icon="add"
              label="Добавить"
              @click="addGeoAttraction"
            />
          </div>
          <div
            v-for="attraction in geo.attractions"
            :key="attraction.id"
            class="geo-attraction-admin"
          >
            <q-input
              v-model="attraction.title"
              dense
              outlined
              label="Название"
            />
            <q-select
              v-model="attraction.location_id"
              :options="geo.locations"
              option-value="id"
              option-label="label"
              emit-value
              map-options
              dense
              outlined
              label="Город/район"
            />
            <q-input
              v-model="attraction.description"
              dense
              outlined
              type="textarea"
              autogrow
              label="Описание"
            />
            <div class="geo-admin-actions">
              <q-btn
                outline
                dense
                no-caps
                label="Сохранить"
                @click="saveGeoAttraction(attraction)"
              />
              <q-btn
                flat
                dense
                color="negative"
                label="Удалить"
                @click="removeGeoAttraction(attraction)"
              />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Сообщения из формы обратной связи -->
    <div class="section-card">
      <div class="section-title">
        Сообщения с формы
        <q-btn
          flat
          dense
          no-caps
          icon="refresh"
          label="Обновить"
          @click="loadFeedback"
        />
      </div>

      <div v-for="item in feedback" :key="item.id" class="feedback-card">
        <div class="feedback-head">
          <b>{{ item.name || 'Без имени' }}</b>
          <span v-if="item.phone">· {{ item.phone }}</span>
          <span class="feedback-date">{{
            formatDateTime(item.created_at)
          }}</span>
          <q-btn
            flat
            dense
            no-caps
            color="negative"
            label="Удалить"
            class="feedback-del"
            @click="removeFeedback(item)"
          />
        </div>
        <div class="feedback-msg">{{ item.message }}</div>
      </div>

      <div v-if="!feedback.length" class="empty-text">
        Сообщений пока нет.
      </div>
    </div>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import MediaSourceButtons from '../components/admin/MediaSourceButtons.vue'

const router = useRouter()

function authHeaders() {
  const token = sessionStorage.getItem('albion_admin_token')
  return { Authorization: `Bearer ${token}` }
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...options.headers,
      ...authHeaders()
    }
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = await response.json()
      detail = data.detail || detail
    } catch (exc) {
      /* not json */
    }
    throw new Error(detail)
  }

  return response.json()
}

const slides = ref([])
const loading = ref(false)
const error = ref('')
const savingKey = ref(null)

/* Сообщения от полей выбора медиа: ошибки — в баннер, успех — тихо. */
function onMediaNotify(message, type = 'success') {
  error.value = type === 'error' ? message : ''
}

const feedback = ref([])
const geo = ref({
  settings: { map_links_enabled: true },
  locations: [],
  attractions: []
})

const LOCATION_KINDS = [
  { label: 'Город', value: 'city' },
  { label: 'Район', value: 'district' }
]

const WHEEL_MODES = [
  { label: 'Выключено — колесо листает слайды', value: 'off' },
  {
    label: 'Вариант 1: вниз — по позиции курсора, вверх — раскрыть',
    value: 'v1'
  },
  {
    label: 'Вариант 2: вверх — вперёд, вниз — назад, клик — раскрыть',
    value: 'v2'
  },
  {
    label: 'Вариант 3: вниз — вперёд, вверх — назад (на краях — слайды)',
    value: 'v3'
  }
]

const EXTRA_OPTIONS = [
  { label: 'Нет', value: '' },
  {
    label: 'Статистика сети (конструкции/форматы/стороны)',
    value: 'network_stats'
  }
]

const KIND_OPTIONS = [
  { label: 'Верхний (карусель о компании)', value: 'hero' },
  { label: 'Города и районы → карта', value: 'geo' },
  { label: 'Новости', value: 'news' },
  { label: 'Форма обратной связи', value: 'form' },
  { label: 'Обычный текст', value: 'text' }
]

function formatDateTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return ''
  const pad = n => String(n).padStart(2, '0')
  return (
    `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}

async function loadFeedback() {
  try {
    const data = await request('/api/admin/home/feedback')
    feedback.value = data.feedback || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function loadGeo() {
  try {
    const data = await request('/api/admin/home/geo')
    geo.value = {
      settings: data.settings || { map_links_enabled: true },
      locations: data.locations || [],
      attractions: data.attractions || []
    }
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveGeoSettings(value) {
  geo.value.settings.map_links_enabled = Boolean(value)
  try {
    const data = await request('/api/admin/home/geo/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ map_links_enabled: Boolean(value) })
    })
    geo.value.settings = data.settings
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveGeoWheelMode(value) {
  geo.value.settings.deck_wheel_mode = value
  try {
    const data = await request('/api/admin/home/geo/settings', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deck_wheel_mode: value })
    })
    geo.value.settings = data.settings
  } catch (exc) {
    error.value = String(exc)
  }
}

async function addGeoLocation() {
  try {
    const data = await request('/api/admin/home/geo/locations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: 'city',
        label: 'Новая локация',
        map_value: ''
      })
    })
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

/* Достопримечательности выбранной локации — для выбора фото-обложки. */
function attractionsFor(location) {
  return (geo.value.attractions || []).filter(
    item => String(item.location_id) === String(location.id)
  )
}

async function saveGeoLocation(location) {
  try {
    const data = await request(`/api/admin/home/geo/locations/${location.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: location.kind,
        label: location.label,
        map_value: location.map_value,
        is_active: location.is_active,
        description: location.description || '',
        cover_attraction_id: location.cover_attraction_id || null
      })
    })
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function removeGeoLocation(location) {
  if (!window.confirm('Удалить локацию?')) return
  try {
    const data = await request(`/api/admin/home/geo/locations/${location.id}`, {
      method: 'DELETE'
    })
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function addGeoAttraction() {
  try {
    const data = await request('/api/admin/home/geo/attractions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Новая достопримечательность',
        description: ''
      })
    })
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveGeoAttraction(attraction) {
  try {
    const data = await request(
      `/api/admin/home/geo/attractions/${attraction.id}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: attraction.title,
          description: attraction.description,
          location_id: attraction.location_id,
          is_active: attraction.is_active
        })
      }
    )
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function removeGeoAttraction(attraction) {
  if (!window.confirm('Удалить достопримечательность?')) return
  try {
    const data = await request(
      `/api/admin/home/geo/attractions/${attraction.id}`,
      { method: 'DELETE' }
    )
    geo.value.locations = data.locations || []
    geo.value.attractions = data.attractions || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function removeFeedback(item) {
  if (!window.confirm('Удалить сообщение?')) return

  try {
    const data = await request(`/api/admin/home/feedback/${item.id}`, {
      method: 'DELETE'
    })
    feedback.value = data.feedback || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/home/slides')
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

async function addSlide() {
  error.value = ''
  try {
    const data = await request('/api/admin/home/slides', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Новый слайд', text: '' })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function patchSlide(slide, payload, key) {
  savingKey.value = key
  error.value = ''

  try {
    const data = await request(`/api/admin/home/slides/${slide.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    savingKey.value = null
  }
}

function saveSlide(slide) {
  patchSlide(
    slide,
    {
      kind: slide.kind,
      title: slide.title,
      text: slide.text,
      button_label: slide.button_label,
      button_url: slide.button_url,
      image_path: slide.image
    },
    `slide-${slide.id}`
  )
}

function setHero(slide) {
  patchSlide(slide, { is_hero: true })
}

function toggleActive(slide) {
  patchSlide(slide, { is_active: !slide.is_active })
}

async function removeSlide(slide) {
  if (!window.confirm(`Удалить слайд «${slide.title || slide.id}»?`)) return

  try {
    const data = await request(`/api/admin/home/slides/${slide.id}`, {
      method: 'DELETE'
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function addItem(slide) {
  try {
    const data = await request(`/api/admin/home/slides/${slide.id}/items`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Новая карточка', text: '' })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveItem(item) {
  const key = `item-${item.id}`
  savingKey.value = key
  error.value = ''

  try {
    const data = await request(`/api/admin/home/items/${item.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: item.title,
        text: item.text,
        eyebrow: item.eyebrow,
        slogan: item.slogan,
        button_label: item.button_label,
        button_url: item.button_url,
        button2_label: item.button2_label,
        button2_url: item.button2_url,
        image_path: item.image,
        extra: item.extra
      })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    savingKey.value = null
  }
}

async function removeItem(slide, item) {
  if (!window.confirm('Удалить карточку?')) return

  try {
    const data = await request(`/api/admin/home/items/${item.id}`, {
      method: 'DELETE'
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

// ---------------------------------------------------------------- кнопки

/* Варианты оформления кнопки. */
const BUTTON_VARIANTS = [
  { label: 'Основная (красная)', value: 'primary' },
  { label: 'Прозрачная', value: 'ghost' }
]

async function addSlideButton(slide) {
  error.value = ''

  try {
    const data = await request(`/api/admin/home/slides/${slide.id}/buttons`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'Новая кнопка',
        url: '',
        variant: 'primary'
      })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function addItemButton(item) {
  error.value = ''

  try {
    const data = await request(`/api/admin/home/items/${item.id}/buttons`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: 'Новая кнопка',
        url: '',
        variant: 'primary'
      })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveButton(btn) {
  savingKey.value = `btn-${btn.id}`
  error.value = ''

  try {
    const data = await request(`/api/admin/home/buttons/${btn.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: btn.label,
        url: btn.url,
        variant: btn.variant
      })
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    savingKey.value = null
  }
}

async function removeButton(btn) {
  if (!window.confirm('Удалить кнопку?')) return

  try {
    const data = await request(`/api/admin/home/buttons/${btn.id}`, {
      method: 'DELETE'
    })
    slides.value = data.slides || []
  } catch (exc) {
    error.value = String(exc)
  }
}

onMounted(() => {
  load()
  loadFeedback()
  loadGeo()
})
</script>

<style scoped>
.administration-home {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.12em;
  color: #94a3b8;
  margin-bottom: 6px;
}

h1 {
  font-size: 26px;
  margin: 0 0 6px;
}
.page-header p {
  margin: 0;
  color: #64748b;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.error-text {
  color: #b91c1c;
  background: #fee2e2;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.hint {
  color: #64748b;
  font-size: 13px;
}

.slide-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
  background: #fff;
}

.slide-card.is-hero {
  border-color: #cbd5e1;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
}

.slide-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.slide-order {
  font-weight: 700;
  color: #475569;
}

.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
}

.badge-hero {
  background: #fef3c7;
  color: #92400e;
}
.badge-on {
  background: #dcfce7;
  color: #166534;
}
.badge-off {
  background: #e2e8f0;
  color: #64748b;
}

.slide-head-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field > span {
  font-size: 12px;
  color: #64748b;
}

.photo-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
}

.photo-preview {
  width: 160px;
  height: 90px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f1f5f9 center/cover no-repeat;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  font-size: 12px;
}

.photo-actions {
  display: flex;
  gap: 8px;
}

.save-row {
  margin-top: 14px;
}

.items-block {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px dashed #e2e8f0;
}

.items-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 600;
  margin-bottom: 12px;
}

/* Редактор дополнительных кнопок слайда/карточки. */
.buttons-block {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #e2e8f0;
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.button-row .btn-label {
  flex: 1 1 180px;
  min-width: 160px;
}
.button-row .btn-url {
  flex: 1 1 240px;
  min-width: 200px;
}
.button-row .btn-variant {
  flex: 0 0 190px;
}

.item-card {
  border: 1px solid #eef2f6;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: #fafbfc;
}

.empty-text {
  color: #94a3b8;
}

.section-card {
  margin-top: 24px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px 18px;
  background: #fff;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.feedback-card {
  border: 1px solid #eef2f6;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #fafbfc;
}

.feedback-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.feedback-date {
  color: #94a3b8;
  font-size: 12px;
}
.feedback-del {
  margin-left: auto;
}
.feedback-msg {
  margin-top: 6px;
  color: #334155;
  white-space: pre-wrap;
}

.geo-settings-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.geo-wheel {
  flex: 1 1 420px;
  min-width: 0;
  max-width: 560px;
}
.geo-admin-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.geo-admin-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.geo-kind {
  flex: 0 0 110px;
}
.geo-label {
  min-width: 0;
  flex: 1;
}
.geo-location-admin {
  padding: 10px;
  margin-bottom: 10px;
  border: 1px solid #eef2f6;
  border-radius: 8px;
  background: #fafbfc;
}
.geo-admin-sub {
  display: grid;
  gap: 8px;
  margin-top: 6px;
}
.geo-admin-sub-side {
  display: flex;
  align-items: center;
  gap: 8px;
}
.geo-cover {
  flex: 1;
  min-width: 0;
}
.geo-attraction-admin {
  padding: 10px;
  margin-bottom: 10px;
  border: 1px solid #eef2f6;
  border-radius: 8px;
  display: grid;
  gap: 8px;
}
.geo-admin-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 900px) {
  .geo-admin-columns {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .administration-home {
    padding: 16px;
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
