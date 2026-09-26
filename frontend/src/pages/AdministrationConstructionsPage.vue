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

    <div class="status-grid">
      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">СОСТОЯНИЕ БАЗЫ</div>

          <div class="status-row">
            <span class="status-dot status-gray"></span>
            <strong>Ожидание обновления</strong>
          </div>

          <div class="card-meta">
            Последнее обновление: —
          </div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">КОНСТРУКЦИИ</div>

          <div class="stat-value">—</div>

          <div class="card-meta">
            записей в базе
          </div>
        </q-card-section>
      </q-card>

      <q-card flat bordered class="status-card">
        <q-card-section>
          <div class="card-label">МЕДИА</div>

          <div class="stat-value">—</div>

          <div class="card-meta">
            фотографий конструкций
          </div>
        </q-card-section>
      </q-card>
    </div>

    <q-card flat bordered class="section-card">
      <q-card-section>
        <div class="section-title">ОБНОВЛЕНИЕ БАЗЫ</div>

        <div class="upload-area">
          <q-icon name="upload_file" size="42px" />

          <div class="upload-content">
            <div class="upload-title">Загрузить базу конструкций</div>
            <div class="upload-text">
              Файл Excel в формате XLS или XLSX
            </div>
          </div>

          <q-btn
            outline
            no-caps
            label="Выбрать файл"
            icon="folder_open"
          />
        </div>

        <div class="progress-placeholder">
          <div class="progress-header">
            <span>СТАТУС ОБНОВЛЕНИЯ</span>
            <span>Ожидание</span>
          </div>

          <q-linear-progress
            :value="0"
            size="6px"
            rounded
          />
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="section-card">
      <q-card-section>
        <div class="section-title-row">
          <div class="section-title">ИСТОРИЯ ОБНОВЛЕНИЙ</div>

          <q-select
            v-model="selectedUpdate"
            dense
            outlined
            emit-value
            map-options
            :options="[]"
            label="Предыдущие обновления"
            style="min-width: 280px"
            disable
          />
        </div>

        <div class="empty-state">
          <q-icon name="history" size="40px" />
          <div>История обновлений пока пуста</div>
        </div>
      </q-card-section>
    </q-card>

    <q-card flat bordered class="section-card">
      <q-card-section>
        <div class="section-title">КАТАЛОГ КОНСТРУКЦИЙ</div>

        <div class="catalog-toolbar">
          <q-input
            dense
            outlined
            placeholder="Поиск по адресу..."
            style="max-width: 360px"
            disable
          >
            <template #prepend>
              <q-icon name="search" />
            </template>
          </q-input>

          <q-space />

          <div class="construction-count">
      Тестовых конструкций: {{ visibleConstructions.length }}
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
          :style="viewMode === 'compact'
            ? { '--construction-compact-columns': compactColumns }
            : undefined"
        >
          <q-card
            v-for="item in visibleConstructions"
            :key="item.id"
            flat
            bordered
            class="construction-card"
          >
            <div class="construction-photo">
              <div class="photo-placeholder">
                ALBION
              </div>
            </div>

            <q-card-section class="construction-card-content">
              <div class="construction-topline">
                <div class="construction-type">
                  {{ item.type }}
                  <span>{{ item.size }}</span>
                </div>

                <div class="construction-id">
                  #{{ item.id }}
                </div>
              </div>

              <div class="construction-city">
                {{ item.city }}
              </div>

              <div class="construction-address">
                {{ item.address }} · СТОРОНА {{ item.side }}
              </div>

              <div class="construction-meta">
                <span>Освещение: {{ item.light }}</span>
                <span>Материал: {{ item.material }}</span>
              </div>

              <div class="months-title">
                ЦЕНА ПО МЕСЯЦАМ
              </div>

              <div
                class="months-grid"
                :style="{ '--months-count': months.length }"
              >
                <div
                  v-for="month in months"
                  :key="month.key"
                  class="month-cell"
                  :class="item.months[month.key].status"
                >
                  <div class="month-name">{{ month.short }}</div>
                  <div class="month-price">
                    {{ formatPrice(item.months[month.key].price) }}
                  </div>
                  <div class="month-status">
                    {{ item.months[month.key].statusLabel }}
                  </div>
                </div>
              </div>

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

          <q-btn
            flat
            round
            dense
            icon="close"
            @click="editDialog = false"
          />
        </q-card-section>

        <q-separator />

        <q-card-section v-if="editingItem">
          <div class="edit-section-title">ФОТО КОНСТРУКЦИИ</div>

          <div class="edit-photo">
            <div class="edit-photo-preview">
              <img
                v-if="editingItem.photo"
                :src="editingItem.photo"
                alt=""
              >
              <div v-else class="edit-photo-placeholder">
                ALBION
              </div>
            </div>

            <div class="edit-photo-actions">
              <q-btn
                outline
                no-caps
                icon="photo_library"
                label="Выбрать из медиатеки"
                @click="openMediaPicker"
              />

              <q-btn
                outline
                no-caps
                icon="upload"
                label="Загрузить с ПК"
                @click="triggerPhotoUpload"
              />

              <q-btn
                v-if="editingItem.photo"
                flat
                no-caps
                color="negative"
                icon="delete_outline"
                label="Удалить фото"
                @click="editingItem.photo = ''"
              />

              <input
                ref="photoInput"
                type="file"
                accept="image/*"
                class="hidden-photo-input"
                @change="handlePhotoUpload"
              >
            </div>
          </div>

          <div class="edit-section-title edit-main-section">
            ОСНОВНЫЕ ДАННЫЕ
          </div>

          <div class="edit-main-grid">
            <q-select
              v-model="editingItem.city"
              dense
              outlined
              label="Город"
              :options="cityOptions(editingItem.city)"
            />

            <q-input
              v-model="editingItem.address"
              dense
              outlined
              label="Адрес"
            />

            <q-select
              v-model="editingItem.side"
              dense
              outlined
              label="Сторона"
              :options="sideOptions"
            />

            <q-select
              v-model="editingItem.type"
              dense
              outlined
              label="Тип конструкции"
              :options="typeOptions"
            />

            <q-input
              v-model="editingItem.size"
              dense
              outlined
              label="Размер"
            />

            <q-select
              v-model="editingItem.material"
              dense
              outlined
              label="Материал"
              :options="materialOptions"
            />

            <div class="edit-checkbox">
              <q-checkbox
                v-model="editingItem.lightEnabled"
                label="Освещение"
              />
            </div>
          </div>

          <div class="edit-section-title months-edit-section">
            ЦЕНЫ И СТАТУСЫ ПО МЕСЯЦАМ
          </div>

          <div class="edit-months">
            <div
              v-for="month in months"
              :key="month.key"
              class="edit-month"
            >
              <div class="edit-month-name">
                {{ month.short }}
              </div>

              <q-input
                v-model.number="editingItem.months[month.key].price"
                dense
                outlined
                type="number"
                label="Цена, ₽"
              />

              <q-select
                v-model="editingItem.months[month.key].status"
                dense
                outlined
                emit-value
                map-options
                label="Статус"
                :options="statusOptions"
                @update:model-value="updateStatusLabel(month.key)"
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
              <q-input
                v-model="field.name"
                dense
                outlined
                label="Название"
              />

              <q-input
                v-model="field.value"
                dense
                outlined
                label="Значение"
              />
            </div>
          </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right" class="edit-dialog-actions">
          <q-btn
            flat
            no-caps
            label="Отмена"
            @click="editDialog = false"
          />

          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Сохранить"
            @click="saveEdit"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const months = [
  { key: 'august', short: 'АВГ' },
  { key: 'september', short: 'СЕН' },
  { key: 'october', short: 'ОКТ' },
  { key: 'november', short: 'НОЯ' },
  { key: 'december', short: 'ДЕК' }
]

const testConstructions = [
  {
    id: 1001,
    city: 'РОСТОВ-НА-ДОНУ',
    address: '1-й Конной Армии ул. 32',
    side: 'A',
    type: 'ЩИТ',
    size: '6 × 3 м',
    light: 'Да',
    lightEnabled: true,
    lightEnabled: true,
    material: 'Металл',
    months: {
      august: { price: 15400, status: 'free', statusLabel: 'свободно' },
      september: { price: 15400, status: 'free', statusLabel: 'свободно' },
      october: { price: 16000, status: 'reserved', statusLabel: 'резерв' },
      november: { price: 16000, status: 'free', statusLabel: 'свободно' },
      december: { price: 17000, status: 'free', statusLabel: 'свободно' }
    },
    extra: [
      { name: 'Паспорт', value: 'АЛБ-2026-001' },
      { name: 'Владелец', value: 'ООО «Альбион»' },
      { name: '', value: '' }
    ]
  },
  {
    id: 1002,
    city: 'РОСТОВ-НА-ДОНУ',
    address: 'Будённовский проспект 80',
    side: 'B',
    type: 'СИТИБОРД',
    size: '3,7 × 2,7 м',
    light: 'Да',
    material: 'Алюминий',
    months: {
      august: { price: 22000, status: 'busy', statusLabel: 'занято' },
      september: { price: 22000, status: 'free', statusLabel: 'свободно' },
      october: { price: 23000, status: 'free', statusLabel: 'свободно' },
      november: { price: 23000, status: 'pending', statusLabel: 'утверждение' },
      december: { price: 24000, status: 'free', statusLabel: 'свободно' }
    },
    extra: [
      { name: 'Примечание', value: 'Въезд со стороны проспекта' },
      { name: '', value: '' },
      { name: '', value: '' }
    ]
  },
  {
    id: 1003,
    city: 'БАТАЙСК',
    address: 'ул. Кирова 156',
    side: 'A1',
    type: 'ПИЛЛАР',
    size: '1,2 × 3 м',
    light: 'Нет',
    lightEnabled: false,
    material: 'Композит',
    months: {
      august: { price: 12000, status: 'free', statusLabel: 'свободно' },
      september: { price: 12000, status: 'free', statusLabel: 'свободно' },
      october: { price: 12500, status: 'free', statusLabel: 'свободно' },
      november: { price: 12500, status: 'free', statusLabel: 'свободно' },
      december: { price: 13000, status: 'reserved', statusLabel: 'резерв' }
    },
    extra: [
      { name: 'Номер опоры', value: '156-А' },
      { name: 'Район', value: 'Центральный' },
      { name: 'Примечание', value: 'Тестовое поле' }
    ]
  }
]


function formatPrice(value) {
  if (!value) return '—'
  return new Intl.NumberFormat('ru-RU').format(value)
}

const editDialog = ref(false)
const editingItem = ref(null)

const viewMode = ref('full')
const compactColumns = ref(6)
const selectedUpdate = ref(null)

const compactColumnOptions = [
  { label: '4', value: 4 },
  { label: '5', value: 5 },
  { label: '6', value: 6 },
  { label: '7', value: 7 },
  { label: '8', value: 8 }
]

const displayConstructions = ref([])
const loadingConstructions = ref(false)
const constructionsError = ref("")

const monthMap = {
  Август: "august",
  Сентябрь: "september",
  Октябрь: "october",
  Ноябрь: "november",
  Декабрь: "december"
}

const statusMap = {
  "Свободно": "free",
  "В резерве": "reserved",
  "На утверждении": "pending",
  "Занято": "busy",
  "Доступность": "free"
}

function parsePrice(value) {
  if (value === null || value === undefined || value === "") return 0

  const normalized = String(value)
    .replace(/\s/g, "")
    .replace(",", ".")

  const number = Number(normalized)
  return Number.isFinite(number) ? number : 0
}

function mapConstruction(item) {
  const mappedMonths = {}

  months.forEach(month => {
    const apiMonth = Object.keys(monthMap).find(
      key => monthMap[key] === month.key
    )

    const monthName = apiMonth || ""
    const rawStatus = item.statuses?.[monthName] || "Свободно"
    const rawPrice = item.month_prices?.[monthName] || item.price || ""

    mappedMonths[month.key] = {
      price: parsePrice(rawPrice),
      status: statusMap[rawStatus] || "free",
      statusLabel: rawStatus.toLowerCase()
    }
  })

  return {
    id: item.id,
    city: item.city || "",
    address: item.address || "",
    side: item.side || "",
    type: item.type || "",
    size: item.size || "",
    light: item.light || "",
    material: item.material || "",
    photo: item.photo || "",
    lat: item.lat,
    lng: item.lng,
    map: item.map || "",
    name: item.name || "",
    number: item.number || "",
    district: item.district || "",
    months: mappedMonths,
    extra: [
      { name: "Номер", value: item.number || "" },
      { name: "Район", value: item.district || "" },
      { name: "", value: "" }
    ]
  }
}

async function loadConstructions() {
  loadingConstructions.value = true
  constructionsError.value = ""

  try {
    const response = await fetch("/api/constructions")

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    if (!Array.isArray(data)) {
      throw new Error("Некорректный формат данных")
    }

    displayConstructions.value = data.map(mapConstruction)
  } catch (error) {
    console.error("Ошибка загрузки конструкций:", error)
    constructionsError.value = "Не удалось загрузить конструкции"
    displayConstructions.value = []
  } finally {
    loadingConstructions.value = false
  }
}

const visibleConstructions = computed(() => displayConstructions.value)

loadConstructions()

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

const materialOptions = [
  'Металл',
  'Алюминий',
  'Композит',
  'Пластик',
  'Другое'
]

const photoInput = ref(null)

function cityOptions(currentCity) {
  return [
    currentCity,
    ...cities.filter(city => city !== currentCity)
  ]
}

function triggerPhotoUpload() {
  photoInput.value?.click()
}

function handlePhotoUpload(event) {
  const file = event.target.files?.[0]

  if (!file || !editingItem.value) return

  editingItem.value.photo = URL.createObjectURL(file)
  event.target.value = ''
}

function openMediaPicker() {
  console.log('Медиатека конструкций')
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

function openEdit(item) {
  editingItem.value = cloneConstruction(item)
  editDialog.value = true
}

function updateStatusLabel(monthKey) {
  const month = editingItem.value?.months?.[monthKey]
  if (!month) return

  const option = statusOptions.find(
    item => item.value === month.status
  )

  month.statusLabel = option?.label?.toLowerCase() || ''
}

function applyPriceToAll() {
  if (!editingItem.value) return

  const firstMonth = months[0].key
  const price = editingItem.value.months[firstMonth].price

  months.forEach(month => {
    editingItem.value.months[month.key].price = price
  })
}

function saveEdit() {
  if (!editingItem.value) return

  editingItem.value.light = editingItem.value.lightEnabled
    ? 'Да'
    : 'Нет'

  const index = testConstructions.findIndex(
    item => item.id === editingItem.value.id
  )

  if (index !== -1) {
    testConstructions[index] = cloneConstruction(editingItem.value)
  }

  editDialog.value = false
}
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
  background:
    linear-gradient(
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

.hidden-photo-input {
  display: none;
}

.edit-main-section {
  margin-top: 28px;
}

.edit-main-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
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

.extra-section-title {
  margin-top: 28px;
}

.extra-edit-grid {
  display: grid;
  gap: 10px;
}

.extra-edit-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(220px, 1.2fr);
  gap: 10px;
}

.edit-dialog-actions {
  padding: 14px 18px;
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

.extra-section-title {
  margin-top: 26px;
}

.extra-edit-grid {
  display: grid;
  gap: 10px;
}

.extra-edit-row {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 10px;
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
  padding: 10px 12px 12px;
}

.construction-grid--compact .construction-city {
  margin-top: 8px;
  font-size: 11px;
  line-height: 1.25;
}

.construction-grid--compact .construction-address {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.3;
}

.construction-grid--compact .construction-photo {
  aspect-ratio: auto;
  width: 100%;
  overflow: hidden;
  background: #f3f5f6;
}

.construction-grid--compact .construction-photo img {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  object-fit: contain;
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
  aspect-ratio: auto;
  min-height: 110px;
  height: 100%;
}

.construction-grid--list .construction-photo img {
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  object-fit: contain;
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
}

.construction-photo {
  aspect-ratio: 16 / 9;
  background: #f0f0f0;
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
  background:
    linear-gradient(135deg, #eeeeee 25%, #e6e6e6 25%, #e6e6e6 50%, #eeeeee 50%, #eeeeee 75%, #e6e6e6 75%);
  background-size: 28px 28px;
}

.construction-card-content {
  padding: 18px;
}

.construction-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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
