<template>
  <q-page class="administration-statistics">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Статистика</h1>
        <p>Посещаемость страниц и география</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="refresh"
          label="Обновить"
          :loading="loading"
          @click="reload"
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

    <div v-if="error" class="error-text">{{ error }}</div>

    <!-- ФИЛЬТР ПО ДАТАМ -->
    <section class="section-card">
      <div class="filter-row">
        <div class="filter-field">
          <label>С</label>
          <q-input v-model="dateFrom" outlined dense type="date" />
        </div>

        <div class="filter-field">
          <label>По</label>
          <q-input v-model="dateTo" outlined dense type="date" />
        </div>

        <div class="presets">
          <q-btn
            v-for="preset in presets"
            :key="preset.label"
            flat
            dense
            no-caps
            class="preset-btn"
            :class="{ 'is-active': activePreset === preset.label }"
            :disable="loading"
            :label="preset.label"
            @click="applyPreset(preset)"
          />
        </div>
      </div>
    </section>

    <div v-if="loading && !summary" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <template v-else>
      <!-- КПЭ -->
      <section class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Сегодня</div>
          <div class="kpi-value">{{ summary?.today?.visits ?? 0 }}</div>
          <div class="kpi-note">
            {{ summary?.today?.unique ?? 0 }} уникальных
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">7 дней</div>
          <div class="kpi-value">{{ summary?.week?.visits ?? 0 }}</div>
          <div class="kpi-note">
            {{ summary?.week?.unique ?? 0 }} уникальных
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">30 дней</div>
          <div class="kpi-value">{{ summary?.month?.visits ?? 0 }}</div>
          <div class="kpi-note">
            {{ summary?.month?.unique ?? 0 }} уникальных
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">За период</div>
          <div class="kpi-value">{{ summary?.period?.visits ?? 0 }}</div>
          <div class="kpi-note">
            {{ summary?.period?.unique ?? 0 }} уникальных
          </div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">Стран</div>
          <div class="kpi-value">{{ summary?.period?.countries ?? 0 }}</div>
          <div class="kpi-note">за период</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-label">Боты</div>
          <div class="kpi-value">
            {{ Math.round((summary?.period?.bot_share ?? 0) * 100) }}%
          </div>
          <div class="kpi-note"> {{ summary?.period?.bots ?? 0 }} визитов </div>
        </div>
      </section>

      <!-- ГРАФИК -->
      <section class="section-card">
        <div class="section-title">Визиты по дням</div>

        <div v-if="!daily.length" class="empty-text">
          За выбранный период визитов нет.
        </div>

        <VisitChart v-else :items="daily" />
      </section>

      <div class="two-columns">
        <!-- СТРАНЫ -->
        <section class="section-card">
          <div class="section-title">
            Страны
            <span class="counter">{{ countries.length }}</span>
          </div>

          <div v-if="!countries.length" class="empty-text">
            Нет данных о странах за период.
          </div>

          <table v-else class="stats-table">
            <thead>
              <tr>
                <th>Страна</th>
                <th class="num">Визиты</th>
                <th class="num">Уникальные</th>
                <th class="num">Доля</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in countries" :key="row.code || 'none'">
                <td>
                  <span class="flag">{{ flagOf(row.code) }}</span>
                  {{ countryLabel(row) }}
                </td>
                <td class="num">{{ row.visits }}</td>
                <td class="num">{{ row.unique }}</td>
                <td class="num">{{ Math.round(row.share * 100) }}%</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- СТРАНИЦЫ -->
        <section class="section-card">
          <div class="section-title">
            Топ страниц
            <span class="counter">{{ pages.length }}</span>
          </div>

          <div v-if="!pages.length" class="empty-text">
            Нет данных за период.
          </div>

          <table v-else class="stats-table">
            <thead>
              <tr>
                <th>Страница</th>
                <th class="num">Визиты</th>
                <th class="num">Уникальные</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in pages" :key="row.path">
                <td class="path-cell" :title="row.path">{{ row.path }}</td>
                <td class="num">{{ row.visits }}</td>
                <td class="num">{{ row.unique }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <!-- ЖУРНАЛ ВИЗИТОВ -->
      <section class="section-card">
        <div class="section-title">
          Журнал визитов
          <span class="counter">{{ visitsTotal }}</span>
        </div>

        <div v-if="visitsLoading" class="loading-row">
          <q-spinner size="24px" />
        </div>

        <div v-else-if="!visits.length" class="empty-text">
          Визитов пока нет.
        </div>

        <template v-else>
          <div class="table-wrap">
            <table class="stats-table">
              <thead>
                <tr>
                  <th>Время</th>
                  <th>Страница</th>
                  <th>Страна</th>
                  <th>Устройство</th>
                  <th>Посетитель</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, index) in visits" :key="index">
                  <td class="date-cell">{{ formatDate(row.created_at) }}</td>
                  <td class="path-cell" :title="row.path">{{ row.path }}</td>
                  <td>
                    <span class="flag">{{ flagOf(row.country_code) }}</span>
                    {{ countryLabel(row) }}
                  </td>
                  <td class="date-cell">
                    <span v-if="row.is_bot" class="bot-badge">бот</span>
                    <template v-else>
                      {{ deviceLabel(row.device) }} · {{ row.browser }}
                    </template>
                  </td>
                  <td class="hash-cell">{{ row.visitor }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="totalPages > 1" class="pagination-row">
            <q-pagination
              v-model="page"
              :max="totalPages"
              :max-pages="7"
              boundary-numbers
              direction-links
              @update:model-value="loadVisits"
            />
          </div>
        </template>
      </section>

      <p class="attribution">
        IP Geolocation by
        <a href="https://db-ip.com" target="_blank" rel="noopener">DB-IP</a>
        (CC BY 4.0). IP-адреса посетителей не хранятся.
      </p>
    </template>
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import VisitChart from '../components/admin/VisitChart.vue'
import { adminRequest as request } from '../services/adminApi'

const router = useRouter()

const PAGE_SIZE = 50

// ------------------------------------------------ состояние

const loading = ref(true)
const visitsLoading = ref(false)
const error = ref('')

const summary = ref(null)
const daily = ref([])
const countries = ref([])
const pages = ref([])
const visits = ref([])
const visitsTotal = ref(0)
const page = ref(1)

const dateFrom = ref('')
const dateTo = ref('')
const activePreset = ref('Всё время')

// ------------------------------------------------ даты

function isoDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')

  return `${y}-${m}-${d}`
}

function daysAgo(days) {
  const date = new Date()
  date.setDate(date.getDate() - days)

  return isoDate(date)
}

const presets = [
  {
    label: 'Сегодня',
    from: () => isoDate(new Date()),
    to: () => isoDate(new Date())
  },
  { label: '7 дней', from: () => daysAgo(6), to: () => isoDate(new Date()) },
  { label: '30 дней', from: () => daysAgo(29), to: () => isoDate(new Date()) },
  { label: 'Всё время', from: () => '', to: () => '' }
]

function applyPreset(preset) {
  dateFrom.value = preset.from()
  dateTo.value = preset.to()
  activePreset.value = preset.label
  reload()
}

function rangeQuery() {
  const params = new URLSearchParams()

  if (dateFrom.value) params.set('from', dateFrom.value)
  if (dateTo.value) params.set('to', dateTo.value)

  return params.toString()
}

// ------------------------------------------------ загрузка

async function loadStats() {
  loading.value = true
  error.value = ''

  try {
    const query = rangeQuery()
    const suffix = query ? `?${query}` : ''

    const [summaryData, dailyData, countriesData, pagesData] =
      await Promise.all([
        request(`/api/admin/statistics/summary${suffix}`),
        request(`/api/admin/statistics/daily${suffix}`),
        request(`/api/admin/statistics/countries${suffix}`),
        request(`/api/admin/statistics/pages${suffix}`)
      ])

    summary.value = summaryData
    daily.value = dailyData.items || []
    countries.value = countriesData.items || []
    pages.value = pagesData.items || []
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

async function loadVisits() {
  visitsLoading.value = true

  try {
    const params = new URLSearchParams(rangeQuery())

    params.set('limit', String(PAGE_SIZE))
    params.set('offset', String((page.value - 1) * PAGE_SIZE))

    const data = await request(
      `/api/admin/statistics/visits?${params.toString()}`
    )

    visits.value = data.items || []
    visitsTotal.value = data.total || 0
  } catch (exc) {
    error.value = String(exc)
  } finally {
    visitsLoading.value = false
  }
}

function reload() {
  page.value = 1
  loadStats()
  loadVisits()
}

// ------------------------------------------------ представление

const totalPages = computed(() =>
  Math.max(1, Math.ceil(visitsTotal.value / PAGE_SIZE))
)

const RU_COUNTRIES = {
  RU: 'Россия',
  UA: 'Украина',
  BY: 'Беларусь',
  KZ: 'Казахстан',
  US: 'США',
  DE: 'Германия',
  FR: 'Франция',
  GB: 'Великобритания',
  CN: 'Китай',
  TR: 'Турция',
  IN: 'Индия',
  JP: 'Япония',
  KR: 'Южная Корея',
  IT: 'Италия',
  ES: 'Испания',
  PL: 'Польша',
  NL: 'Нидерланды',
  BR: 'Бразилия',
  CA: 'Канада',
  AU: 'Австралия',
  SE: 'Швеция',
  CH: 'Швейцария',
  CZ: 'Чехия',
  AT: 'Австрия',
  BE: 'Бельгия',
  FI: 'Финляндия',
  NO: 'Норвегия',
  DK: 'Дания',
  GR: 'Греция',
  PT: 'Португалия',
  RO: 'Румыния',
  BG: 'Болгария',
  RS: 'Сербия',
  MD: 'Молдова',
  AM: 'Армения',
  AZ: 'Азербайджан',
  GE: 'Грузия',
  UZ: 'Узбекистан',
  KG: 'Киргизия',
  TJ: 'Таджикистан',
  TM: 'Туркмения',
  IL: 'Израиль',
  AE: 'ОАЭ',
  EG: 'Египет',
  TH: 'Таиланд',
  VN: 'Вьетнам',
  ID: 'Индонезия',
  SG: 'Сингапур',
  IE: 'Ирландия',
  HU: 'Венгрия',
  SK: 'Словакия',
  LT: 'Литва',
  LV: 'Латвия',
  EE: 'Эстония'
}

/* Флаг из ISO-кода: региональные индикаторы. */
function flagOf(code) {
  const value = String(code || '').toUpperCase()

  if (!/^[A-Z]{2}$/.test(value)) {
    return '🏳️'
  }

  return String.fromCodePoint(
    ...[...value].map(char => 0x1f1e6 + char.charCodeAt(0) - 65)
  )
}

function countryLabel(row) {
  if (!row || !row.code) {
    return 'Неизвестно'
  }

  return RU_COUNTRIES[row.code] || row.name || row.code
}

const DEVICE_LABELS = {
  desktop: 'Компьютер',
  mobile: 'Телефон',
  tablet: 'Планшет'
}

function deviceLabel(device) {
  return DEVICE_LABELS[device] || device || '—'
}

function formatDate(value) {
  if (!value) return '—'

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(reload)
</script>

<style scoped>
.administration-statistics {
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.eyebrow {
  color: #8b8b8b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.page-header h1 {
  margin: 4px 0;
  font-size: 30px;
  line-height: 1.1;
  font-weight: 800;
}

.page-header p {
  margin: 0;
  color: #777;
}

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
}

.loading-block,
.loading-row {
  padding: 40px 0;
  display: flex;
  justify-content: center;
}

.empty-text {
  color: #777;
  padding: 18px;
}

.section-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 20px 22px;
  margin-bottom: 18px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

.counter {
  background: #eef1f5;
  color: #546e7a;
  border-radius: 20px;
  padding: 1px 10px;
  font-size: 12px;
  font-weight: 700;
}

/* Фильтр */
.filter-row {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 16px;
}

.filter-field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.filter-field {
  width: 170px;
}

.presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.preset-btn {
  color: #546e7a;
  font-size: 13px;
}

.preset-btn.is-active {
  background: #eef1f5;
  color: #17212b;
  font-weight: 700;
}

/* КПЭ */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.kpi-card {
  background: #fff;
  border: 1px solid #e4e6ea;
  border-radius: 14px;
  padding: 16px 18px;
}

.kpi-label {
  color: #8b8b8b;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.kpi-value {
  margin: 6px 0 2px;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
}

.kpi-note {
  color: #8b8b8b;
  font-size: 12px;
}

/* Таблицы */
.two-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.stats-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.stats-table th {
  text-align: left;
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #8b8b8b;
  border-bottom: 1px solid #e4e6ea;
  white-space: nowrap;
}

.stats-table td {
  padding: 9px 10px;
  border-bottom: 1px solid #f0f1f3;
  vertical-align: middle;
}

.stats-table tr:last-child td {
  border-bottom: 0;
}

.stats-table .num {
  text-align: right;
  white-space: nowrap;
}

.flag {
  margin-right: 4px;
}

.path-cell {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12.5px;
}

.date-cell {
  color: #777;
  font-size: 12px;
  white-space: nowrap;
}

.hash-cell {
  color: #9aa6ae;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.bot-badge {
  display: inline-block;
  background: #f5eef0;
  color: #a12b3c;
  border-radius: 6px;
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 700;
}

.table-wrap {
  overflow-x: auto;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

.attribution {
  margin: 8px 0 0;
  color: #9aa6ae;
  font-size: 12px;
  text-align: center;
}

.attribution a {
  color: #546e7a;
}

@media (max-width: 900px) {
  .two-columns {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .administration-statistics {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
  }
}
</style>
