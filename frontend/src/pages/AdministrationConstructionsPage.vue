<template>
  <q-page class="administration-constructions">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>КОНСТРУКЦИИ</h1>
        <p>Рекламная сеть и данные конструкций</p>
      </div>

      <q-btn
        flat
        no-caps
        icon="arrow_back"
        label="Назад"
        @click="router.push('/administration/dashboard')"
      />
    </div>

    <!-- Факт восстановления старой базы из архива. -->
    <div v-if="baseStats.last_restore" class="restore-banner">
      <q-icon name="history" size="18px" />
      <span>
        База восстановлена из архива
        <b>{{ baseStats.last_restore.import_key }}</b>
        · {{ formatDate(baseStats.last_restore.restored_at) }}
      </span>
    </div>

    <div class="status-grid">
      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">СОСТОЯНИЕ БАЗЫ</div>

          <div class="status-row">
            <span
              class="status-dot"
              :class="{
                'status-green': baseStatus.kind === 'fresh',
                'status-orange': baseStatus.kind === 'stale',
                'status-red': baseStatus.kind === 'error',
                'status-gray': baseStatus.kind === 'pending'
              }"
            ></span>
            <strong>{{ baseStatus.label }}</strong>
          </div>

          <div class="card-meta">
            Дата актуальной базы: {{ formatDate(baseStats.last_update) }}
          </div>

          <div v-if="baseStats.last_restore" class="card-meta restore-meta">
            Сейчас восстановлена база из архива
            <b>{{ baseStats.last_restore.import_key }}</b>
            <template v-if="baseStats.last_restore.base_date">
              — от
              {{
                (baseStats.last_restore.base_date || '')
                  .split('-')
                  .reverse()
                  .join('.')
              }}
            </template>
            · восстановление
            {{ formatDate(baseStats.last_restore.restored_at) }}
          </div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">КОНСТРУКЦИИ</div>

          <div class="stat-value">{{ baseStats.constructions || '—' }}</div>

          <div class="card-meta"> конструкций в базе </div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">МЕДИА</div>

          <div class="stat-value">{{ baseStats.previews || '—' }}</div>

          <div class="card-meta"> фотографий конструкций (скачано) </div>
        </q-card-section>
      </q-card>
    </div>

    <q-card flat bordered class="section-card">
      <q-card-section>
        <div class="section-title">КАТАЛОГ КОНСТРУКЦИЙ</div>

        <div class="catalog-toolbar">
          <q-input
            v-model="searchQuery"
            dense
            outlined
            placeholder="Поиск по адресу..."
            style="max-width: 320px"
            clearable
          >
            <template #prepend>
              <q-icon name="search" />
            </template>
          </q-input>

          <q-select
            v-model="locationFilter"
            dense
            outlined
            multiple
            use-chips
            clearable
            clear-icon="close"
            :options="filterCityOptions"
            label="Город / Район"
            placeholder="Город / Район"
            style="min-width: 220px"
          />

          <q-select
            v-model="formatFilter"
            dense
            outlined
            multiple
            use-chips
            clearable
            clear-icon="close"
            :options="filterFormatOptions"
            label="Формат"
            placeholder="ФОРМАТ"
            style="min-width: 170px"
          />

          <q-space />

          <q-checkbox
            v-model="showOnlyChanged"
            dense
            label="Показать изменённые"
            class="changed-filter"
          />

          <div class="construction-count">
            Выбрано {{ visibleConstructions.length }} конструкций
          </div>

          <div class="catalog-toolbar-actions">
            <q-btn-toggle
              v-model="viewMode"
              unelevated
              toggle-color="primary"
              :options="[
                { label: 'Компактный', value: 'compact' },
                { label: 'Полный', value: 'full' },
                { label: 'Список', value: 'list' }
              ]"
            />

            <q-btn-toggle
              v-if="viewMode === 'compact'"
              v-model="compactColumns"
              unelevated
              toggle-color="primary"
              :options="compactColumnOptions"
            />
          </div>
        </div>

        <div
          class="construction-grid"
          :class="`construction-grid--${viewMode}`"
          :style="
            viewMode === 'compact'
              ? { '--construction-compact-columns': compactColumns }
              : undefined
          "
        >
          <q-card
            v-for="item in visibleConstructions"
            :key="item.id"
            flat
            bordered
            class="construction-card"
          >
            <div class="construction-photo">
              <img
                v-if="cardImage(item)"
                :src="cardImage(item)"
                :alt="item.address"
                loading="lazy"
              />
              <div v-else class="photo-placeholder"> ALBION </div>

              <!-- Переключатель: фото ↔ карта -->
              <div
                v-if="item.photo && item.mapLarge"
                class="media-switch"
                @click.stop
              >
                <button
                  type="button"
                  class="media-switch__btn"
                  :class="{ 'is-active': mediaMode(item.id) === 'photo' }"
                  @click.stop="setCardMedia(item, 'photo')"
                >
                  Фото
                </button>
                <button
                  type="button"
                  class="media-switch__btn"
                  :class="{ 'is-active': mediaMode(item.id) === 'map' }"
                  @click.stop="setCardMedia(item, 'map')"
                >
                  Карта
                </button>
              </div>
            </div>

            <q-card-section class="construction-card-content">
              <div class="construction-topline">
                <div class="construction-type">
                  {{ item.type }}
                  <span>{{ item.size }}</span>
                </div>

                <span
                  v-if="item.overridden?.length"
                  class="construction-changed"
                  :title="
                    'Изменено: ' + item.overridden.map(fieldLabel).join(', ')
                  "
                  >изменено *</span
                >

                <div class="construction-id"> #{{ item.id }} </div>
              </div>

              <div class="construction-city">
                {{ item.city }}
              </div>

              <div class="construction-address">
                {{ item.address }} · СТОРОНА {{ item.side }}
              </div>

              <div class="construction-meta">
                <span
                  class="meta-feature"
                  :title="isLightOn(item) ? 'Подсветка есть' : 'Без подсветки'"
                >
                  <span
                    class="feature-picto lightbulb"
                    :class="isLightOn(item) ? 'on' : 'off'"
                    >💡</span
                  >
                  <span class="feature-label">подсветка</span>
                </span>

                <span class="meta-feature" title="статика/динамика">
                  <span class="feature-dyn">
                    <span
                      class="dyn-word"
                      :class="{ 'is-active': !isDynamic(item) }"
                      >статика</span
                    >

                    <span class="dyn-sep">/</span>

                    <span
                      class="dyn-word"
                      :class="{ 'is-active': isDynamic(item) }"
                      >динамика</span
                    >
                  </span>
                </span>

                <span v-if="item.material">Материал: {{ item.material }}</span>
              </div>

              <!-- Распорка: свободная высота уходит сюда, поэтому блоки
                   от «ЦЕНА ПО МЕСЯЦАМ» и ниже выровнены по низу карточки. -->
              <div class="card-spacer" aria-hidden="true"></div>

              <div class="months-title"> ЦЕНА ПО МЕСЯЦАМ </div>

              <div
                class="months-grid"
                :style="{ '--months-count': monthColumns.length }"
              >
                <div
                  v-for="month in monthColumns"
                  :key="month"
                  class="month-cell"
                  :class="item.months[month]?.status || 'free'"
                >
                  <div class="month-name">{{ MONTH_SHORT[month] }}</div>
                  <div class="month-price">
                    {{
                      item.months[month]
                        ? formatPrice(item.months[month].price)
                        : '—'
                    }}
                  </div>
                  <div class="month-status">
                    {{ item.months[month]?.statusLabel || '' }}
                  </div>
                </div>
              </div>

              <div class="card-footer">
                <div
                  v-if="item.extra.some(field => field.name || field.value)"
                  class="extra-fields"
                >
                  <div class="extra-title">ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ</div>

                  <div
                    v-for="(field, index) in item.extra"
                    :key="index"
                    v-show="field.name || field.value"
                    class="extra-field"
                  >
                    <span>{{ field.name }}</span>
                    <strong>{{ field.value }}</strong>
                  </div>
                </div>

                <q-btn
                  unelevated
                  no-caps
                  color="primary"
                  label="Редактировать"
                  icon="edit"
                  class="edit-button"
                  @click="openEdit(item)"
                />
              </div>
            </q-card-section>
          </q-card>
        </div>
      </q-card-section>
    </q-card>
    <q-dialog v-model="editDialog">
      <q-card class="edit-dialog">
        <q-card-section class="edit-dialog-header">
          <div>
            <div class="section-title">РЕДАКТИРОВАНИЕ</div>
            <div class="edit-dialog-title">
              {{ editingItem?.city }}
            </div>
            <div class="edit-dialog-address">
              {{ editingItem?.address }} · СТОРОНА {{ editingItem?.side }}
            </div>
          </div>

          <q-btn flat round dense icon="close" @click="editDialog = false" />
        </q-card-section>

        <q-separator />

        <q-card-section v-if="editingItem">
          <div class="edit-section-title">
            ФОТО КОНСТРУКЦИИ
            <span v-if="showStar('photo')" class="field-star" title="Изменено"
              >*</span
            >
          </div>

          <div class="edit-photo">
            <div class="edit-photo-preview">
              <img v-if="editingItem.photo" :src="editingItem.photo" alt="" />
              <div v-else class="edit-photo-placeholder"> ALBION </div>
            </div>

            <div class="edit-photo-content">
              <div class="edit-photo-actions">
                <q-btn
                  outline
                  no-caps
                  icon="photo_library"
                  label="Медиатека"
                  :disable="!editingItem.surface_hash || overriding"
                  @click="pickerOpen = true"
                />

                <label
                  class="upload-file-btn"
                  :class="{
                    'is-disabled': !editingItem.surface_hash || overriding
                  }"
                  for="construction-photo-input"
                >
                  {{ overriding ? 'Загрузка…' : 'Загрузить' }}
                </label>

                <q-btn
                  v-if="editingItem.photo"
                  flat
                  no-caps
                  color="negative"
                  icon="delete_outline"
                  label="Удалить фото"
                  @click="clearEditingPhoto"
                />

                <input
                  id="construction-photo-input"
                  type="file"
                  accept="image/*"
                  class="file-input-hidden"
                  :disabled="!editingItem.surface_hash || overriding"
                  @change="onPhotoFilePicked"
                />
              </div>

              <div class="photo-note">
                Медиатека конструкций — каталог превью. Замена фото сохраняется
                во временный каталог и действует на всём сайте до следующего
                обновления базы.
              </div>
            </div>
          </div>

          <div class="edit-section-title edit-main-section">
            ОСНОВНЫЕ ДАННЫЕ
          </div>

          <div class="edit-main-grid">
            <q-select
              v-model="editingItem.city"
              label="Город"
              dense
              outlined
              :options="cityOptions(editingItem.city)"
            >
              <template #append>
                <span
                  v-if="showStar('city')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-select>

            <q-input v-model="editingItem.address" label="Адрес" dense outlined>
              <template #append>
                <span
                  v-if="showStar('address')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-input>

            <q-select
              v-model="editingItem.side"
              label="Сторона"
              dense
              outlined
              :options="sideOptions"
            >
              <template #append>
                <span
                  v-if="showStar('side')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-select>

            <q-select
              v-model="editingItem.type"
              label="Тип конструкции"
              dense
              outlined
              :options="typeOptions"
            >
              <template #append>
                <span
                  v-if="showStar('type')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-select>

            <q-input v-model="editingItem.size" label="Размер" dense outlined>
              <template #append>
                <span
                  v-if="showStar('size')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-input>

            <q-select
              v-model="editingItem.material"
              label="Материал"
              dense
              outlined
              :options="materialOptions"
            >
              <template #append>
                <span
                  v-if="showStar('material')"
                  class="field-star"
                  title="Изменено"
                  >*</span
                >
              </template>
            </q-select>

            <div class="edit-checkbox">
              <q-checkbox
                v-model="editingItem.lightEnabled"
                label="Освещение"
              />
              <span v-if="showStar('light')" class="field-star" title="Изменено"
                >*</span
              >
            </div>
          </div>

          <div class="edit-section-title months-edit-section">
            ЦЕНЫ И СТАТУСЫ ПО МЕСЯЦАМ
          </div>

          <div class="edit-months">
            <div
              v-for="month in editingMonthColumns"
              :key="month"
              class="edit-month"
            >
              <div class="edit-month-name">
                {{ MONTH_SHORT[month] }}
              </div>

              <q-input
                v-model.number="editingItem.months[month].price"
                dense
                outlined
                type="number"
                label="Цена, ₽"
              />

              <q-select
                v-model="editingItem.months[month].status"
                dense
                outlined
                emit-value
                map-options
                label="Статус"
                :options="statusOptions"
                @update:model-value="updateStatusLabel(month)"
              />
            </div>
          </div>

          <q-btn
            flat
            no-caps
            icon="content_copy"
            label="Применить цену ко всем месяцам"
            class="apply-price-button"
            @click="applyPriceToAll"
          />

          <div class="edit-section-title extra-section-title">
            ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ
          </div>

          <div class="extra-edit-grid">
            <div
              v-for="(field, index) in editingItem.extra"
              :key="index"
              class="extra-edit-row"
            >
              <q-input v-model="field.name" dense outlined label="Название" />

              <q-input v-model="field.value" label="Значение" dense outlined>
                <template #append>
                  <span
                    v-if="
                      (field.name === 'Номер' && showStar('number')) ||
                      (field.name === 'Район' && showStar('district'))
                    "
                    class="field-star"
                    title="Изменено"
                    >*</span
                  >
                </template>
              </q-input>
            </div>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="edit-dialog-actions">
          <q-btn
            flat
            dense
            round
            icon="settings_backup_restore"
            color="grey-8"
            :loading="resetting"
            :disable="!editingItem.surface_hash"
            @click="resetToDefault"
          >
            <q-tooltip
              >Вернуть по умолчанию (снять временные изменения)</q-tooltip
            >
          </q-btn>

          <q-space />

          <q-btn flat no-caps label="Отмена" @click="editDialog = false" />

          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Сохранить"
            :loading="savingEdit"
            :disable="!changedFields.length"
            @click="saveEdit"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Каталог превью конструкций (медиатека конструкций). -->
    <ConstructionMediaPicker v-model="pickerOpen" @select="onPreviewPicked" />
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'

import ConstructionMediaPicker from '../components/admin/ConstructionMediaPicker.vue'
import {
  clearConstructionFieldOverride,
  clearConstructionPhotoOverride,
  setConstructionFieldOverride,
  setConstructionPhotoOverride
} from '../services/constructionMedia'
import { isDynamicSide } from '../utils/constructionGroups'

/* Подсветка включена, если в источнике «Да» */
function isLightOn(item) {
  const light = String(item?.light || '')
    .trim()
    .toLowerCase()
  return ['да', 'yes', 'true', '1'].includes(light)
}

/* Динамика — сторона с несколькими поверхностями (см. constructionGroups) */
function isDynamic(item) {
  return isDynamicSide(String(item?.side || ''), item?.type)
}

const router = useRouter()

/* Календарный порядок месяцев и короткие подписи. */
const MONTH_ORDER = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь'
]

const MONTH_SHORT = {
  Январь: 'ЯНВ',
  Февраль: 'ФЕВ',
  Март: 'МАР',
  Апрель: 'АПР',
  Май: 'МАЙ',
  Июнь: 'ИЮН',
  Июль: 'ИЮЛ',
  Август: 'АВГ',
  Сентябрь: 'СЕН',
  Октябрь: 'ОКТ',
  Ноябрь: 'НОЯ',
  Декабрь: 'ДЕК'
}

function sortMonths(names) {
  return [...names].sort((a, b) => {
    const ia = MONTH_ORDER.indexOf(a)
    const ib = MONTH_ORDER.indexOf(b)

    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
}

function formatPrice(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('ru-RU').format(value)
}

const editDialog = ref(false)
const editingItem = ref(null)
/* Снимок исходных значений — для звёздочек у изменённых полей. */
const originalItem = ref(null)
const savingEdit = ref(false)

/* Object URL превью загруженного фото — отзываем при замене/закрытии, иначе
   Blob удерживается в памяти. */
const objectUrls = new Set()

function releaseObjectUrl(url) {
  if (url && objectUrls.has(url)) {
    URL.revokeObjectURL(url)
    objectUrls.delete(url)
  }
}

function releaseAllObjectUrls() {
  objectUrls.forEach(url => URL.revokeObjectURL(url))
  objectUrls.clear()
}

const viewMode = ref('full')
const compactColumns = ref(6)

const compactColumnOptions = [
  { label: '4', value: 4 },
  { label: '5', value: 5 },
  { label: '6', value: 6 },
  { label: '7', value: 7 },
  { label: '8', value: 8 }
]

const displayConstructions = ref([])
const loadingConstructions = ref(false)
const constructionsError = ref('')

const baseStats = ref({
  last_update: null,
  constructions: 0,
  media: 0,
  photos: 0,
  previews: 0
})

/* Порог «свежести» базы, дней. */
const FRESH_DAYS = 7

/*
 * Состояние базы:
 *   fresh   — зелёный: обновлена не старше 7 дней;
 *   stale   — оранжевый: старше 7 дней (неактуальна);
 *   error   — красный: последняя загрузка завершилась ошибкой;
 *   pending — серый: базы ещё нет.
 */
const baseStatus = computed(() => {
  const stats = baseStats.value || {}

  const state = String(stats.update_state || '').toLowerCase()

  if (state === 'error') {
    return { kind: 'error', label: 'Ошибка загрузки' }
  }

  if (!stats.last_update) {
    return { kind: 'pending', label: 'Ожидание обновления' }
  }

  const time = new Date(stats.last_update).getTime()

  if (!Number.isFinite(time)) {
    return { kind: 'pending', label: 'Ожидание обновления' }
  }

  const days = Math.floor((Date.now() - time) / 86400000)

  if (days > FRESH_DAYS) {
    return {
      kind: 'stale',
      label: `База неактуальна — обновлена ${days} дн. назад`
    }
  }

  return { kind: 'fresh', label: 'База актуальна' }
})

const searchQuery = ref('')
const locationFilter = ref([])
const formatFilter = ref([])
/* Фильтр «Показать изменённые»: только конструкции с переопределениями. */
const showOnlyChanged = ref(false)

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  const pad = n => String(n).padStart(2, '0')

  return (
    `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.` +
    `${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

async function loadBaseStats() {
  const token = sessionStorage.getItem('albion_admin_token')

  try {
    const response = await fetch('/api/admin/constructions/stats', {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    if (data && typeof data === 'object') {
      baseStats.value = data
    }
  } catch (error) {
    console.error('Ошибка загрузки состояния базы:', error)
  }
}

const statusMap = {
  Свободно: 'free',
  'В резерве': 'reserved',
  'На утверждении': 'pending',
  Занято: 'busy',
  Доступность: 'free'
}

function parsePrice(value) {
  if (value === null || value === undefined || value === '') return 0

  const normalized = String(value).replace(/\s/g, '').replace(',', '.')

  const number = Number(normalized)
  return Number.isFinite(number) ? number : 0
}

/* Актуальные месяцы, присутствующие в текущей базе (по всем конструкциям). */
const monthColumns = computed(() => {
  const found = new Set()

  for (const item of displayConstructions.value) {
    Object.keys(item.months || {}).forEach(name => found.add(name))
  }

  return sortMonths(found)
})

/* Месяцы редактируемой конструкции. */
const editingMonthColumns = computed(() =>
  sortMonths(Object.keys(editingItem.value?.months || {}))
)

function mapConstruction(item) {
  /*
   * Ключ — полное имя месяца (как отдаёт база: «Октябрь», «Ноябрь»…).
   * Состав берём из данных, без фиксированного списка месяцев и без
   * подстановки базовой цены: цена — только реальная месячная.
   */
  const mappedMonths = {}
  const names = new Set([
    ...Object.keys(item.months || {}),
    ...Object.keys(item.statuses || {}),
    ...Object.keys(item.month_prices || {})
  ])

  for (const monthName of names) {
    const rawStatus = item.statuses?.[monthName] || 'Свободно'
    const rawPrice = item.month_prices?.[monthName] ?? ''

    mappedMonths[monthName] = {
      price: parsePrice(rawPrice),
      status: statusMap[rawStatus] || 'free',
      statusLabel: rawStatus.toLowerCase()
    }
  }

  return {
    id: item.id,
    surface_hash: item.surface_hash || '',
    overridden: Array.isArray(item.overridden) ? item.overridden : [],
    city: item.city || '',
    address: item.address || '',
    side: item.side || '',
    type: item.type || '',
    size: item.size || '',
    light: item.light || '',
    material: item.material || '',
    photo: item.photo || '',
    lat: item.lat,
    lng: item.lng,
    map: item.map || '',
    /*
     * Только локальные файлы. `item.map` — исходная ссылка на страницу
     * Яндекс.Диска, а не картинка: как src она не работает и блокируется
     * CSP, поэтому в фолбэк не попадает (нет локальной карты — заглушка).
     */
    mapLarge: item.map_large || item.map_card || item.map_thumb || '',
    name: item.name || '',
    number: item.number || '',
    district: item.district || '',
    months: mappedMonths,
    extra: [
      { name: 'Номер', value: item.number || '' },
      { name: 'Район', value: item.district || '' },
      { name: '', value: '' }
    ]
  }
}

/* -------- фото ↔ карта-схема на карточке -------- */
const cardMedia = ref({})

function mediaMode(id) {
  return cardMedia.value[id] || 'photo'
}

function cardImage(item) {
  if (mediaMode(item.id) === 'map' && item.mapLarge) {
    return item.mapLarge
  }

  return item.photo || item.mapLarge || ''
}

function setCardMedia(item, mode) {
  cardMedia.value = {
    ...cardMedia.value,
    [item.id]: mode
  }
}

async function loadConstructions() {
  loadingConstructions.value = true
  constructionsError.value = ''

  try {
    const response = await fetch('/api/constructions')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    if (!Array.isArray(data)) {
      throw new Error('Некорректный формат данных')
    }

    displayConstructions.value = data.map(mapConstruction)
  } catch (error) {
    console.error('Ошибка загрузки конструкций:', error)
    constructionsError.value = 'Не удалось загрузить конструкции'
    displayConstructions.value = []
  } finally {
    loadingConstructions.value = false
  }
}

function distinctValues(accessor) {
  const seen = []

  displayConstructions.value.forEach(item => {
    const value = String(accessor(item) || '').trim()

    if (value && !seen.includes(value)) {
      seen.push(value)
    }
  })

  return seen.sort((a, b) => a.localeCompare(b, 'ru'))
}

/* Выбранные элементы списка поднимаются наверх. */
function withSelectedFirst(allValues, selected) {
  const rest = allValues.filter(value => !selected.includes(value))
  return [...selected, ...rest]
}

const filterCityOptions = computed(() =>
  withSelectedFirst(
    distinctValues(item => item.city),
    locationFilter.value
  )
)

const filterFormatOptions = computed(() =>
  withSelectedFirst(
    distinctValues(item => item.type),
    formatFilter.value
  )
)

const visibleConstructions = computed(() =>
  displayConstructions.value.filter(item => {
    // Фильтр «Показать изменённые» — оставляем только конструкции с правками.
    if (showOnlyChanged.value && !item.overridden?.length) {
      return false
    }

    const query = searchQuery.value.trim().toLowerCase()

    if (query) {
      const haystack =
        `${item.address} ${item.city} ${item.district}`.toLowerCase()
      if (!haystack.includes(query)) return false
    }

    if (
      locationFilter.value.length &&
      !locationFilter.value.includes(item.city)
    ) {
      return false
    }

    if (formatFilter.value.length && !formatFilter.value.includes(item.type)) {
      return false
    }

    return true
  })
)

loadConstructions()
loadBaseStats()

const cities = [
  'РОСТОВ-НА-ДОНУ',
  'БАТАЙСК',
  'АКСАЙ',
  'НОВОЧЕРКАССК',
  'ТАГАНРОГ',
  'ШАХТЫ'
]

const sideOptions = [
  'A',
  'B',
  'C',
  'A1',
  'A2',
  'A(1)',
  'A(2)',
  'A(3)',
  'A1(1)',
  'A2(3)',
  'B(1)',
  'B(2)',
  'B(3)',
  'B(5)'
]

const typeOptions = [
  'ЩИТ',
  'СИТИБОРД',
  'ПИЛЛАР',
  'СТЕЛА',
  'СВЕТОВОЙ КОРОБ',
  'ДРУГОЕ'
]

const materialOptions = ['Металл', 'Алюминий', 'Композит', 'Пластик', 'Другое']

function cityOptions(currentCity) {
  return [currentCity, ...cities.filter(city => city !== currentCity)]
}

/* Убрать фото из редактора и освободить object URL. */
function clearEditingPhoto() {
  if (!editingItem.value) return

  releaseObjectUrl(editingItem.value.photo)
  editingItem.value.photo = ''
}

/* ------------------------------------------------- медиатека конструкций */

const pickerOpen = ref(false)
const overriding = ref(false)
const resetting = ref(false)

function onPhotoFilePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''

  if (file) applyPhotoOverride({ file })
}

function onPreviewPicked(payload) {
  if (payload?.url) applyPhotoOverride({ sourceUrl: payload.url })
}

/*
 * Переопределяет фото конструкции: новая картинка сохраняется во временный
 * каталог превью и подхватывается на всём сайте до следующего обновления базы.
 */
async function applyPhotoOverride({ file, sourceUrl }) {
  const target = editingItem.value

  if (!target) return

  if (!target.surface_hash) {
    constructionsError.value =
      'У этой конструкции нет surface_hash — переопределение недоступно.'
    return
  }

  overriding.value = true
  constructionsError.value = ''

  try {
    const result = await setConstructionPhotoOverride({
      surface_hash: target.surface_hash,
      media_type: 'photo',
      file,
      sourceUrl
    })

    if (result?.photo) {
      target.photo = result.photo
    }
  } catch (exc) {
    constructionsError.value = String(exc?.message || exc)
  } finally {
    overriding.value = false
  }
}

/* ---------- временное изменение основных полей конструкции ---------- */

const FIELD_LABELS = {
  city: 'Город',
  address: 'Адрес',
  side: 'Сторона',
  type: 'Тип',
  size: 'Размер',
  material: 'Материал',
  light: 'Освещение',
  number: 'Номер',
  district: 'Район',
  photo: 'Фото',
  map: 'Карта'
}

function extraValue(item, name) {
  const found = (item?.extra || []).find(field => field.name === name)

  return found ? String(found.value ?? '') : ''
}

/* Геттеры значений формы по ключам переопределяемых полей. */
const FIELD_GETTERS = {
  city: item => String(item?.city ?? ''),
  address: item => String(item?.address ?? ''),
  side: item => String(item?.side ?? ''),
  type: item => String(item?.type ?? ''),
  size: item => String(item?.size ?? ''),
  material: item => String(item?.material ?? ''),
  light: item => (item?.lightEnabled ? 'Да' : 'Нет'),
  number: item => extraValue(item, 'Номер'),
  district: item => extraValue(item, 'Район')
}

/* Изменено ли поле относительно исходного значения. */
function fieldChanged(key) {
  if (!editingItem.value || !originalItem.value) return false

  const get = FIELD_GETTERS[key]

  // У медиа-пунктов (photo/map) геттера нет — их сравнивать не с чем.
  if (typeof get !== 'function') return false

  return get(editingItem.value) !== get(originalItem.value)
}

/*
 * Показывать звёздочку у поля: оно уже временно переопределено в базе
 * ИЛИ изменено сейчас в форме (как бейдж «изменено *» на карточке).
 */
function showStar(key) {
  if (!editingItem.value) return false

  const overridden = editingItem.value.overridden || []

  return overridden.includes(key) || fieldChanged(key)
}

const changedFields = computed(() =>
  Object.keys(FIELD_GETTERS).filter(fieldChanged)
)

function fieldLabel(key) {
  return FIELD_LABELS[key] || key
}

/* Собирает переопределённые поля из формы. */
function collectOverrideFields() {
  const fields = {}

  for (const key of changedFields.value) {
    fields[key] = FIELD_GETTERS[key](editingItem.value)
  }

  return fields
}

const statusOptions = [
  { label: 'Свободно', value: 'free' },
  { label: 'Резерв', value: 'reserved' },
  { label: 'Утверждение', value: 'pending' },
  { label: 'Занято', value: 'busy' }
]

function cloneConstruction(item) {
  return JSON.parse(JSON.stringify(item))
}

/* Заполняет форму копией конструкции; исходник — для сравнения «изменено». */
function applyItemToForm(item) {
  const copy = cloneConstruction(item)

  copy.lightEnabled =
    String(copy.light || '')
      .trim()
      .toLowerCase() === 'да'

  editingItem.value = copy
  originalItem.value = cloneConstruction(copy)
}

function openEdit(item) {
  releaseObjectUrl(editingItem.value?.photo)

  applyItemToForm(item)
  editDialog.value = true
}

function updateStatusLabel(monthKey) {
  const month = editingItem.value?.months?.[monthKey]
  if (!month) return

  const option = statusOptions.find(item => item.value === month.status)

  month.statusLabel = option?.label?.toLowerCase() || ''
}

function applyPriceToAll() {
  if (!editingItem.value) return

  const columns = editingMonthColumns.value

  if (!columns.length) return

  const price = editingItem.value.months[columns[0]].price

  columns.forEach(month => {
    editingItem.value.months[month].price = price
  })
}

/*
 * Сохраняет изменения основных полей как временное переопределение: значения
 * применяются на всём сайте (карта, список, чат) до следующего импорта.
 */
async function saveEdit() {
  const target = editingItem.value

  if (!target) return

  const fields = collectOverrideFields()

  if (!Object.keys(fields).length) {
    // Нечего сохранять — кнопка «Сохранить» для этого и заблокирована.
    return
  }

  if (!target.surface_hash) {
    constructionsError.value =
      'У этой конструкции нет surface_hash — изменения недоступны.'
    return
  }

  savingEdit.value = true
  constructionsError.value = ''

  try {
    await setConstructionFieldOverride({
      surface_hash: target.surface_hash,
      fields
    })

    editDialog.value = false
    await loadConstructions()
  } catch (exc) {
    constructionsError.value = String(exc?.message || exc)
  } finally {
    savingEdit.value = false
  }
}

/*
 * Вернуть конструкцию по умолчанию: снять временные изменения (поля, фото,
 * карта). Окно НЕ закрывается — форма перезаполняется значениями по умолчанию,
 * все отметки «изменено» снимаются, «Сохранить» снова гаснет.
 */
async function resetToDefault() {
  const target = editingItem.value

  if (!target?.surface_hash) return

  const hash = target.surface_hash

  resetting.value = true
  constructionsError.value = ''

  try {
    await clearConstructionFieldOverride({ surface_hash: hash })

    for (const mediaType of ['photo', 'map']) {
      await clearConstructionPhotoOverride({
        surface_hash: hash,
        media_type: mediaType
      })
    }

    await loadConstructions()

    const fresh = displayConstructions.value.find(
      item => item.surface_hash === hash
    )

    if (fresh) {
      releaseObjectUrl(editingItem.value?.photo)
      applyItemToForm(fresh)
    } else if (editingItem.value) {
      // Конструкция пропала из списка — хотя бы гасим отметки.
      editingItem.value.overridden = []
      originalItem.value = cloneConstruction(editingItem.value)
    }
  } catch (exc) {
    constructionsError.value = String(exc?.message || exc)
  } finally {
    resetting.value = false
  }
}

onBeforeUnmount(() => {
  releaseAllObjectUrls()
})
</script>

<style scoped>
.administration-constructions {
  max-width: 1500px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 28px;
}

.eyebrow,
.card-label,
.section-title,
.progress-header {
  color: #8b8b8b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.page-header h1 {
  margin: 4px 0 4px;
  font-size: 30px;
  line-height: 1.1;
  font-weight: 800;
}

/* Баннер восстановления базы из архива */
.restore-banner {
  display: flex;
  align-items: center;
  gap: 10px;

  margin-bottom: 20px;
  padding: 12px 16px;

  border: 1px solid #e6c77a;
  border-radius: 12px;
  background: #fff8e6;
  color: #8a5a00;
  font-size: 14px;
}

.restore-meta {
  color: #8a5a00;
}

.page-header p {
  margin: 0;
  color: #777;
}

.status-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.status-card,
.section-card {
  border-radius: 14px;
  background: #fff;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 12px;
  font-size: 16px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-gray {
  background: #9e9e9e;
}

.status-green {
  background: #2e7d32;
}

.status-orange {
  background: #e6a51c;
}

.status-red {
  background: #e24b42;
}

.card-meta {
  margin-top: 8px;
  color: #888;
  font-size: 13px;
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 800;
}

.section-card {
  margin-bottom: 16px;
}

.section-title {
  margin-bottom: 18px;
}

.upload-area {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 24px;
  border: 1px dashed #cfcfcf;
  border-radius: 12px;
  background: #fafafa;
}

.upload-content {
  flex: 1;
}

.upload-title {
  font-size: 16px;
  font-weight: 700;
}

.upload-text {
  margin-top: 4px;
  color: #888;
  font-size: 13px;
}

.progress-placeholder {
  margin-top: 24px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.section-title-row,
.catalog-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.empty-state {
  min-height: 150px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #999;
  text-align: center;
  border: 1px solid #eee;
  border-radius: 12px;
}

.catalog-empty {
  min-height: 280px;
  margin-top: 18px;
}

.empty-title {
  color: #555;
  font-weight: 700;
}

.empty-text {
  color: #999;
  font-size: 13px;
}

/* Форма редактирования конструкции */

.edit-photo {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

/* Правая колонка блока фото: кнопки, а под ними — пояснение. */
.edit-photo-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.edit-photo-preview {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  border: 1px solid #e6e6e6;
  border-radius: 10px;
  background: #f2f2f2;
}

.edit-photo-preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.edit-photo-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #aaa;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.12em;
  background: linear-gradient(
    135deg,
    #eeeeee 25%,
    #e6e6e6 25%,
    #e6e6e6 50%,
    #eeeeee 50%,
    #eeeeee 75%,
    #e6e6e6 75%
  );
  background-size: 28px 28px;
}

.edit-photo-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding-top: 2px;
}

/* Кнопка-лейбл: нативный триггер выбора файла (минуя JS click()). */
.upload-file-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--q-primary);
  border-radius: 6px;
  color: var(--q-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
}

.upload-file-btn:hover {
  background: rgba(0, 0, 0, 0.03);
}

.upload-file-btn.is-disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* Скрытый (но кликабельный через label[for]) файловый инпут. */
.file-input-hidden {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
}

/* Пометка о временном действии переопределения фото. */
.photo-note {
  margin-top: 10px;
  max-width: 560px;
  color: #8a5a00;
  font-size: 12px;
  line-height: 1.45;
}

/* Звёздочка у изменённого поля / пометка изменённой карточки. */
.field-star {
  margin-left: 3px;
  color: var(--q-primary);
  font-weight: 900;
}

.construction-changed {
  flex: 0 0 auto;

  padding: 1px 7px;
  border-radius: 6px;

  background: #fff0d2;
  color: #b96b00;

  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.changed-filter {
  margin-right: 8px;
  font-size: 13px;
}

.edit-main-section {
  margin-top: 28px;
}

.edit-main-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.edit-checkbox {
  display: flex;
  align-items: center;
  min-height: 40px;
  padding-left: 4px;
}

.months-edit-section {
  margin-top: 28px;
}

.edit-dialog .edit-month {
  padding: 12px;
}

.edit-dialog .edit-month-name {
  margin-bottom: 10px;
}

.edit-dialog .q-field + .q-field {
  margin-top: 8px;
}

/*
 * Правило выше — для вертикального стека полей. Внутри 2-колоночных сеток
 * отступ уже даёт gap, а лишний margin-top сдвигал второе поле строки вниз
 * (Город/Адрес вставали на разной высоте).
 */
.edit-main-grid > .q-field + .q-field,
.extra-edit-row > .q-field + .q-field {
  margin-top: 0;
}

@media (max-width: 800px) {
  .edit-dialog {
    width: calc(100vw - 20px);
  }

  .edit-photo {
    grid-template-columns: 1fr;
  }

  .edit-photo-preview {
    max-width: 420px;
  }

  .edit-main-grid {
    grid-template-columns: 1fr;
  }

  .edit-months {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .extra-edit-row {
    grid-template-columns: 1fr;
  }
}

.edit-dialog {
  width: min(1100px, calc(100vw - 32px));
  max-width: 1100px;
  border-radius: 16px;
}

.edit-dialog-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.edit-dialog-title {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 800;
}

.edit-dialog-address {
  margin-top: 4px;
  color: #777;
  font-size: 13px;
}

.edit-section-title {
  margin-bottom: 14px;
  color: #8b8b8b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.edit-months {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.edit-month {
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 10px;
  background: #fafafa;
}

.edit-month-name {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 800;
}

.edit-month .q-field + .q-field {
  margin-top: 8px;
}

.apply-price-button {
  margin-top: 12px;
}

/*
 * «Дополнительные данные» повторяют сетку «Основных данных»: те же две
 * равные колонки и тот же gap, чтобы столбцы совпадали по вертикали.
 */
.extra-section-title {
  margin-top: 28px;
}

.extra-edit-grid {
  display: grid;
  gap: 12px;
}

.extra-edit-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.edit-dialog-actions {
  padding: 14px 16px;
}

.construction-grid {
  max-height: 70vh;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 6px;

  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;
  align-content: start;
  align-items: stretch;
}

.construction-grid--compact {
  grid-template-columns: repeat(
    var(--construction-compact-columns, 6),
    minmax(0, 1fr)
  );
}

.construction-grid--compact .construction-id,
.construction-grid--compact .construction-meta,
.construction-grid--compact .months-title,
.construction-grid--compact .months-grid,
.construction-grid--compact .extra-fields {
  display: none;
}

.construction-grid--compact .construction-card-content {
  padding: 8px 12px 10px;
  justify-content: flex-end;
  min-height: 0;
}

.construction-grid--compact .construction-city {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.construction-grid--compact .construction-address {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.construction-grid--compact .construction-photo {
  aspect-ratio: 16 / 9;
  width: 100%;
  overflow: hidden;
  background: #f3f5f6;
}

.construction-grid--compact .construction-photo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.construction-grid--compact .photo-placeholder {
  min-height: 90px;
  height: auto;
  aspect-ratio: 16 / 9;
  font-size: 14px;
}

.construction-grid--compact .construction-topline {
  gap: 6px;
}

.construction-grid--compact .construction-type {
  font-size: 12px;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.construction-grid--compact .construction-type span {
  margin-left: 4px;
  font-weight: 500;
}

.construction-grid--compact .edit-button {
  width: 100%;
  margin-top: 8px;
  min-height: 30px;
  font-size: 11px;
}

.construction-grid--full {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.construction-grid--full .construction-card,
.construction-grid--compact .construction-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.construction-grid--full .construction-card-content,
.construction-grid--compact .construction-card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.construction-grid--full .edit-button,
.construction-grid--compact .edit-button {
  margin-top: auto;
}

.construction-grid--compact .edit-button {
  margin-top: 10px;
}

.construction-grid--list {
  grid-template-columns: 1fr;
  gap: 8px;
  max-height: none;
  overflow-y: visible;
  padding-right: 0;
}

.construction-grid--list .construction-card {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  align-items: stretch;
}

.construction-grid--list .construction-photo {
  aspect-ratio: 16 / 9;
  min-height: 110px;
  height: 100%;
}

.construction-grid--list .construction-photo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.construction-grid--list .construction-card-content {
  min-width: 0;
  display: grid;
  grid-template-columns:
    minmax(110px, 0.7fr)
    minmax(120px, 0.9fr)
    minmax(180px, 2fr)
    minmax(180px, 250px)
    140px;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
}

.construction-grid--list .construction-topline {
  display: contents;
}

.construction-grid--list .construction-type {
  grid-column: 1;
  font-size: 13px;
  white-space: nowrap;
}

.construction-grid--list .construction-id {
  display: none;
}

.construction-grid--list .construction-city {
  grid-column: 2;
  margin-top: 0;
  font-size: 12px;
  white-space: nowrap;
}

.construction-grid--list .construction-address {
  grid-column: 3;
  margin-top: 0;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.construction-grid--list .construction-meta,
.construction-grid--list .months-title,
.construction-grid--list .extra-fields {
  display: none;
}

.construction-grid--list .months-grid {
  display: grid;
  grid-column: 4;
  grid-template-columns: repeat(var(--months-count, 5), minmax(28px, 1fr));
  gap: 4px;
  margin: 0;
}

.construction-grid--list .month-cell {
  width: auto;
  height: 28px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 5px;
}

.construction-grid--list .month-name {
  font-size: 9px;
  font-weight: 800;
}

.construction-grid--list .month-price,
.construction-grid--list .month-status {
  display: none;
}

.construction-grid--list .month-cell.free {
  background: #dff3e4;
  color: #16803a;
}

.construction-grid--list .month-cell.reserved,
.construction-grid--list .month-cell.pending {
  background: #fff0d2;
  color: #b96b00;
}

.construction-grid--list .month-cell.busy {
  background: #f9dede;
  color: #c62828;
}

.construction-grid--list .edit-button {
  grid-column: 5;
  margin-top: 0;
  white-space: nowrap;
}

.construction-card {
  overflow: hidden;
  border-radius: 14px;
  background: #fff;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.construction-photo {
  position: relative;
  aspect-ratio: 16 / 9;
  background: #f0f0f0;
  overflow: hidden;
}

.construction-photo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  min-height: 0;
}

.photo-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aaa;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.12em;
  background: linear-gradient(
    135deg,
    #eeeeee 25%,
    #e6e6e6 25%,
    #e6e6e6 50%,
    #eeeeee 50%,
    #eeeeee 75%,
    #e6e6e6 75%
  );
  background-size: 28px 28px;
}

.construction-card-content {
  padding: 18px;
  text-align: left;

  display: flex;
  flex-direction: column;
}

/*
 * Низ карточки (доп. данные + кнопка) прижат к нижнему краю: у карточек с
 * меньшим числом строк он всё равно стоит на одной высоте с соседями.
 * Свободную высоту забирает .card-spacer (перед «ЦЕНА ПО МЕСЯЦАМ»), поэтому
 * блоки от цены по месяцам и ниже выровнены по низу карточки.
 */
.card-spacer {
  flex: 1 1 auto;
  min-height: 0;
}

.card-footer {
  display: flex;
  flex-direction: column;
}

.construction-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 22px;
}

.construction-type {
  font-size: 15px;
  font-weight: 800;
}

.construction-type span {
  margin-left: 8px;
  color: #777;
  font-weight: 500;
}

.construction-id {
  color: #999;
  font-size: 12px;
}

.construction-city {
  margin-top: 14px;
  color: #222;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.construction-address {
  margin-top: 4px;
  color: #555;
  font-size: 14px;
  line-height: 1.4;
}

.construction-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 12px;
  color: #888;
  font-size: 12px;
}

.months-title {
  margin-top: 20px;
  margin-bottom: 8px;
  color: #8b8b8b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.months-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 5px;
}

.month-cell {
  min-width: 0;
  padding: 7px 4px;
  border-radius: 7px;
  background: #f5f5f5;
  text-align: center;
}

.month-cell.free {
  background: #dff3e4;
  color: #16803a;
}

.month-cell.reserved {
  background: #fff0d2;
  color: #b96b00;
}

.month-cell.busy {
  background: #f9dede;
  color: #c62828;
}

.month-cell.pending {
  background: #fff0d2;
  color: #b96b00;
}

.month-name {
  color: #888;
  font-size: 9px;
  font-weight: 800;
}

.month-price {
  margin-top: 4px;
  color: #222;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.15;
}

.month-status {
  margin-top: 3px;
  overflow: hidden;
  color: #999;
  font-size: 8px;
  line-height: 1.1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.extra-fields {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #eee;
}

.extra-title {
  margin-bottom: 8px;
  color: #8b8b8b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.extra-field {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 0;
  font-size: 12px;
}

.extra-field span {
  color: #999;
}

.extra-field strong {
  color: #444;
  text-align: right;
  font-weight: 600;
}

.edit-button {
  width: 100%;
  margin-top: 18px;
}

@media (max-width: 800px) {
  .administration-constructions {
    padding: 20px;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
  }

  .upload-area {
    align-items: flex-start;
    flex-direction: column;
  }

  .section-title-row,
  .catalog-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
