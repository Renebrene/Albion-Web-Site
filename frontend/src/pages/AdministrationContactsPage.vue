<template>
  <q-page class="administration-contacts">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Контакты</h1>
        <p>Офисы, разделы и сотрудники раздела «Контакты»</p>
      </div>

      <div class="header-actions">
        <q-btn
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <div v-if="loading" class="loading-block">
      <q-spinner size="28px" />
    </div>

    <div v-else-if="error" class="error-text">{{ error }}</div>

    <div v-else>
      <!-- ============ ОБЩИЕ НАСТРОЙКИ ============ -->
      <section class="section-card">
        <div class="section-title">
          Общие настройки
          <q-btn
            flat
            dense
            no-caps
            class="action-secondary"
            label="Сохранить"
            :loading="saving"
            @click="saveSettings"
          />
        </div>

        <div class="form-grid">
          <div class="field">
            <label>Телефон</label>
            <q-input v-model="form.phone" outlined dense />
          </div>

          <div class="field">
            <label>Основная почта</label>
            <q-input v-model="form.email" outlined dense />
          </div>
        </div>

        <div class="field">
          <label>Дополнительные почты (general)</label>
          <q-input
            v-model="newGeneralEmail"
            outlined
            dense
            placeholder="Email…"
            @keyup.enter="addGeneralEmail"
          >
            <template #append>
              <q-btn
                flat
                dense
                no-caps
                label="Добавить"
                @click="addGeneralEmail"
              />
            </template>
          </q-input>
        </div>

        <div class="chips-list">
          <span
            v-for="(email, index) in form.additionalEmails"
            :key="email + index"
            class="chip"
          >
            {{ email }}
            <button
              type="button"
              @click="form.additionalEmails.splice(index, 1)"
              >×</button
            >
          </span>
        </div>
      </section>

      <!-- ============ ОФИСЫ ============ -->
      <section class="section-card">
        <div class="section-title">
          Офисы

          <div class="inline-actions">
            <q-btn
              flat
              no-caps
              color="primary"
              label="Добавить офис"
              @click="newOffice"
            />
          </div>
        </div>

        <div v-if="!data.offices.length" class="empty-text">
          Офисов пока нет.
        </div>

        <article
          v-for="(office, index) in data.offices"
          :key="office.id"
          class="mini-card"
        >
          <div class="mini-card-body">
            <div class="mini-card-thumb">
              <img v-if="office.media_url" :src="office.media_url" alt="" />
              <span v-else>🗺</span>
            </div>
            <div class="mini-card-info">
              <div class="mini-card-title">{{ office.name }}</div>
              <div class="mini-card-meta">
                {{ office.address }} · {{ office.emails.join(', ') }}
              </div>
            </div>
          </div>

          <div class="mini-card-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="index === 0"
              @click="moveOffice(index, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="index === data.offices.length - 1"
              @click="moveOffice(index, 1)"
            />
            <q-btn flat dense no-caps icon="edit" @click="editOffice(office)" />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="deleteOffice(office)"
            />
          </div>
        </article>
      </section>

      <!-- ============ РАЗДЕЛЫ И СОТРУДНИКИ ============ -->
      <section
        v-for="(department, dIndex) in data.departments"
        :key="department.id"
        class="section-card department-card"
      >
        <div class="section-title">
          <div class="department-title">{{ department.name }}</div>

          <div class="inline-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="dIndex === 0"
              @click="moveDepartment(dIndex, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="dIndex === data.departments.length - 1"
              @click="moveDepartment(dIndex, 1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="edit"
              @click="editDepartment(department)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="deleteDepartment(department)"
            />
            <q-btn
              flat
              no-caps
              color="primary"
              label="+ Сотрудник"
              @click="newEmployee(department)"
            />
          </div>
        </div>

        <div v-if="!department.employees.length" class="empty-text">
          В разделе нет сотрудников.
        </div>

        <article
          v-for="(employee, eIndex) in department.employees"
          :key="employee.id"
          class="mini-card"
        >
          <div class="mini-card-body">
            <div class="mini-card-thumb">
              <img v-if="employee.media_url" :src="employee.media_url" alt="" />
              <span v-else>👤</span>
            </div>
            <div class="mini-card-info">
              <div class="mini-card-title">
                {{ employee.name || employee.position }}
              </div>
              <div class="mini-card-meta">
                {{ employee.position }}
                <template v-if="employee.subdivision">
                  · {{ employee.subdivision }}</template
                >
                <template v-if="employee.phone">
                  · {{ employee.phone }}</template
                >
                <template v-if="employee.personal_phone">
                  · личн. {{ employee.personal_phone }}</template
                >
                <template v-if="employee.email">
                  · {{ employee.email }}</template
                >
              </div>
            </div>
          </div>

          <div class="mini-card-actions">
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_upward"
              :disable="eIndex === 0"
              @click="moveEmployee(dIndex, eIndex, -1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="arrow_downward"
              :disable="eIndex === department.employees.length - 1"
              @click="moveEmployee(dIndex, eIndex, 1)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="edit"
              @click="editEmployee(employee)"
            />
            <q-btn
              flat
              dense
              no-caps
              icon="delete"
              color="negative"
              @click="deleteEmployee(employee)"
            />
          </div>
        </article>
      </section>

      <div class="add-department-row">
        <q-btn
          outline
          no-caps
          color="primary"
          label="+ Раздел"
          @click="newDepartment"
        />
      </div>
    </div>

    <!-- ============ ДИАЛОГ РЕДАКТИРОВАНИЯ ============ -->
    <q-dialog v-model="editOpen" persistent>
      <q-card class="editor-dialog">
        <q-card-section>
          <div class="dialog-title">
            {{
              editingType === 'office'
                ? 'Офис'
                : editingType === 'department'
                  ? 'Раздел'
                  : 'Сотрудник'
            }}
          </div>
        </q-card-section>

        <q-card-section>
          <template v-if="editingType === 'department'">
            <div class="field">
              <label>Название раздела</label>
              <q-input v-model="editing.name" outlined dense />
            </div>
          </template>

          <template v-else-if="editingType === 'office'">
            <div class="field">
              <label>Название</label>
              <q-input v-model="editing.name" outlined dense />
            </div>
            <div class="field">
              <label>Адрес</label>
              <q-input
                v-model="editing.address"
                outlined
                dense
                type="textarea"
                autogrow
              />
            </div>
            <div class="field">
              <label>Телефон</label>
              <q-input v-model="editing.phone" outlined dense />
            </div>
            <div class="field">
              <label>Режим работы</label>
              <q-input v-model="editing.schedule" outlined dense />
            </div>
            <div class="field">
              <label>Почты</label>
              <div class="chips-list">
                <span
                  v-for="(email, i) in editing.emails"
                  :key="i"
                  class="chip"
                >
                  {{ email }}
                  <button type="button" @click="editing.emails.splice(i, 1)"
                    >×</button
                  >
                </span>
              </div>
              <q-input
                v-model="newOfficeEmail"
                outlined
                dense
                placeholder="Email…"
                @keyup.enter="addOfficeEmail"
              >
                <template #append>
                  <q-btn
                    flat
                    dense
                    no-caps
                    label="Добавить"
                    @click="addOfficeEmail"
                  />
                </template>
              </q-input>
            </div>
            <div class="field">
              <label>Картинка карты</label>
              <div class="media-control">
                <span v-if="editing.media_url" class="chip">
                  Установлено
                  <button type="button" @click="clearOfficeMedia">×</button>
                </span>
                <q-btn
                  flat
                  no-caps
                  color="primary"
                  icon="photo_library"
                  label="Медиатека"
                  @click="openPicker('office')"
                />
                <q-btn
                  flat
                  no-caps
                  color="primary"
                  icon="upload"
                  label="Загрузить"
                  :loading="uploadingMedia"
                  @click="uploadMediaFile('office')"
                />
              </div>
              <div class="media-hint">
                Необходимые фото нужно загрузить в медиахранилище в раздел
                «Сотрудники» или «Офис».
              </div>
            </div>
          </template>

          <template v-else>
            <div class="field">
              <label>Раздел</label>
              <q-select
                v-model="editing.department_id"
                :options="departmentOptions"
                option-value="id"
                option-label="name"
                emit-value
                map-options
                outlined
                dense
              />
            </div>
            <div class="field">
              <label>ФИО</label>
              <q-input
                v-model="editing.name"
                outlined
                dense
                placeholder="ФИО"
              />
            </div>
            <div class="field">
              <label>Должность</label>
              <q-input v-model="editing.position" outlined dense />
            </div>
            <div class="field">
              <label>Телефон рабочий</label>
              <q-input v-model="editing.phone" outlined dense />
            </div>
            <div class="field">
              <label>Телефон личный</label>
              <q-input v-model="editing.personal_phone" outlined dense />
            </div>
            <div class="field">
              <label>Добавочный</label>
              <q-input v-model="editing.extension" outlined dense />
            </div>
            <div class="field">
              <label>Почта</label>
              <q-input v-model="editing.email" outlined dense />
            </div>
            <div class="field">
              <label>Дополнительная информация</label>
              <q-input v-model="editing.subdivision" outlined dense />
            </div>
            <div class="field">
              <label>Фото</label>
              <div class="media-control">
                <span v-if="editing.media_url" class="chip">
                  Установлено
                  <button type="button" @click="clearEmployeeMedia">×</button>
                </span>
                <q-btn
                  flat
                  no-caps
                  color="primary"
                  icon="photo_library"
                  label="Медиатека"
                  @click="openPicker('employee')"
                />
                <q-btn
                  flat
                  no-caps
                  color="primary"
                  icon="upload"
                  label="Загрузить"
                  :loading="uploadingMedia"
                  @click="uploadMediaFile('employee')"
                />
              </div>
              <div class="media-hint">
                Необходимые фото нужно загрузить в медиахранилище в раздел
                «Сотрудники» или «Офис».
              </div>
            </div>
          </template>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            color="primary"
            no-caps
            label="Сохранить"
            :loading="saving"
            @click="saveEditing"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ============ ДИАЛОГ ВЫБОРА ИЗОБРАЖЕНИЯ ============ -->
    <q-dialog v-model="pickerOpen" class="media-picker-dialog">
      <q-card style="min-width: 720px; max-width: 96vw">
        <q-card-section>
          <div class="dialog-title">Выберите изображение</div>
          <div class="picker-filter-hint" v-if="pickerFilterName">
            Фильтр: {{ pickerFilterName }}
          </div>
        </q-card-section>

        <q-card-section v-if="pickerLoading">
          <q-spinner size="24px" />
        </q-card-section>
        <q-card-section v-else-if="pickerError" class="error-text">
          {{ pickerError }}
        </q-card-section>
        <q-card-section v-else>
          <div class="media-grid">
            <button
              v-for="item in mediaList"
              :key="item.id"
              type="button"
              class="media-cell"
              @click="selectMedia(item)"
            >
              <img v-if="isImage(item)" :src="mediaUrl(item)" alt="" />
              <span v-else>🎞</span>
            </button>
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { mediaUrl, uploadAdminMedia } from '../services/adminMedia'
import { adminRequest as request } from '../services/adminApi'

const router = useRouter()

const data = ref({ settings: {}, offices: [], departments: [] })
const form = ref({ phone: '', email: '', additionalEmails: [] })
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const newGeneralEmail = ref('')

const editOpen = ref(false)
const editing = ref(null)
const editingType = ref('')
const newOfficeEmail = ref('')
const departmentOptions = ref([])

const pickerOpen = ref(false)
const pickerLoading = ref(false)
const pickerError = ref('')
const pickerTarget = ref('') // 'office' | 'employee'
const pickerFilterName = ref('')
const editingBackup = ref(null)
const mediaList = ref([])

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const result = await request('/api/admin/contacts')
    data.value = result
    form.value = {
      phone: result.settings.phone || '',
      email: result.settings.email || '',
      additionalEmails: [...(result.settings.additionalEmails || [])]
    }
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

/* ============================================================
   НАСТРОЙКИ
   ============================================================ */

function addGeneralEmail() {
  const value = newGeneralEmail.value.trim()
  if (!value) return
  form.value.additionalEmails.push(value)
  newGeneralEmail.value = ''
}

async function saveSettings() {
  saving.value = true
  try {
    await request('/api/admin/contacts/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone: form.value.phone,
        email: form.value.email,
        additionalEmails: form.value.additionalEmails
      })
    })
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

/* ============================================================
   ПОРЯДОК (обидная пересборка по sortOrder)
   ============================================================ */

async function saveOrder() {
  saving.value = true
  try {
    await request('/api/admin/contacts/reorder', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        offices: data.value.offices.map((o, i) => ({
          id: o.id,
          sort_order: (i + 1) * 10
        })),
        departments: data.value.departments.map((d, di) => ({
          id: d.id,
          sort_order: (di + 1) * 10,
          employees: d.employees.map((e, ei) => ({
            id: e.id,
            sort_order: (ei + 1) * 10,
            department_id: e.department_id || d.id
          }))
        }))
      })
    })
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

function moveOffice(index, delta) {
  const arr = data.value.offices
  const target = index + delta
  if (target < 0 || target >= arr.length) return
  const tmp = arr[index]
  arr[index] = arr[target]
  arr[target] = tmp
  saveOrder()
}

function moveDepartment(index, delta) {
  const arr = data.value.departments
  const target = index + delta
  if (target < 0 || target >= arr.length) return
  const tmp = arr[index]
  arr[index] = arr[target]
  arr[target] = tmp
  saveOrder()
}

function moveEmployee(dIndex, eIndex, delta) {
  const arr = data.value.departments[dIndex].employees
  const target = eIndex + delta
  if (target < 0 || target >= arr.length) return
  const tmp = arr[eIndex]
  arr[eIndex] = arr[target]
  arr[target] = tmp
  saveOrder()
}

/* ============================================================
   ОФИСЫ
   ============================================================ */

function newOffice() {
  editingType.value = 'office'
  editing.value = {
    id: null,
    name: '',
    address: '',
    phone: '',
    emails: [],
    schedule: '',
    lat: null,
    lng: null,
    media_id: null,
    media_url: '',
    is_active: true
  }
  newOfficeEmail.value = ''
  editOpen.value = true
}

function editOffice(office) {
  editingType.value = 'office'
  editing.value = {
    ...office,
    emails: [...(office.emails || [])]
  }
  newOfficeEmail.value = ''
  editOpen.value = true
}

function addOfficeEmail() {
  const value = newOfficeEmail.value.trim()
  if (!value) return
  editing.value.emails.push(value)
  newOfficeEmail.value = ''
}

function clearOfficeMedia() {
  editing.value.media_id = null
  editing.value.media_url = ''
}

async function deleteOffice(office) {
  if (!confirm(`Удалить офис «${office.name}»?`)) return
  try {
    await request(`/api/admin/contacts/offices/${office.id}`, {
      method: 'DELETE'
    })
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  }
}

async function saveOffice() {
  saving.value = true
  try {
    const payload = {
      name: editing.value.name,
      address: editing.value.address,
      phone: editing.value.phone,
      emails: editing.value.emails,
      schedule: editing.value.schedule,
      media_id: editing.value.media_id,
      is_active: true
    }
    if (editing.value.id) {
      await request(`/api/admin/contacts/offices/${editing.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    } else {
      await request('/api/admin/contacts/offices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }
    editOpen.value = false
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

/* ============================================================
   РАЗДЕЛЫ
   ============================================================ */

function newDepartment() {
  editingType.value = 'department'
  editing.value = { id: null, name: '', is_active: true }
  editOpen.value = true
}

function editDepartment(department) {
  editingType.value = 'department'
  editing.value = { ...department }
  editOpen.value = true
}

async function saveDepartment() {
  saving.value = true
  try {
    const payload = { name: editing.value.name, is_active: true }
    if (editing.value.id) {
      await request(`/api/admin/contacts/departments/${editing.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    } else {
      await request('/api/admin/contacts/departments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }
    editOpen.value = false
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

async function deleteDepartment(department) {
  if (!confirm(`Удалить раздел «${department.name}» и его сотрудников?`)) return
  try {
    await request(`/api/admin/contacts/departments/${department.id}`, {
      method: 'DELETE'
    })
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  }
}

/* ============================================================
   СОТРУДНИКИ
   ============================================================ */

function buildDepartmentOptions() {
  departmentOptions.value = data.value.departments.map(d => ({
    id: d.id,
    name: d.name
  }))
}

function newEmployee(department) {
  buildDepartmentOptions()
  editingType.value = 'employee'
  editing.value = {
    id: null,
    department_id: department.id,
    name: '',
    position: '',
    subdivision: '',
    phone: '',
    personal_phone: '',
    extension: '',
    email: '',
    media_id: null,
    media_url: '',
    is_active: true
  }
  editOpen.value = true
}

function editEmployee(employee) {
  buildDepartmentOptions()
  editingType.value = 'employee'
  editing.value = { ...employee }
  editOpen.value = true
}

async function saveEmployee() {
  saving.value = true
  try {
    const payload = {
      department_id: editing.value.department_id,
      name: editing.value.name,
      position: editing.value.position,
      subdivision: editing.value.subdivision,
      phone: editing.value.phone,
      personal_phone: editing.value.personal_phone,
      extension: editing.value.extension,
      email: editing.value.email,
      media_id: editing.value.media_id,
      is_active: true
    }
    if (editing.value.id) {
      await request(`/api/admin/contacts/employees/${editing.value.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    } else {
      await request('/api/admin/contacts/employees', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
    }
    editOpen.value = false
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

function clearEmployeeMedia() {
  editing.value.media_id = null
  editing.value.media_url = ''
}

async function deleteEmployee(employee) {
  if (!confirm(`Удалить сотрудника?`)) return
  try {
    await request(`/api/admin/contacts/employees/${employee.id}`, {
      method: 'DELETE'
    })
    await loadData()
  } catch (exc) {
    error.value = String(exc)
  }
}

/* ============================================================
   ОТПРАВКА ФОРМЫ
   ============================================================ */

async function saveEditing() {
  if (editingType.value === 'office') return saveOffice()
  if (editingType.value === 'department') return saveDepartment()
  return saveEmployee()
}

/* ============================================================
   ВЫБОР ИЗОБРАЖЕНИЯ (медиа)
   ============================================================ */

function isImage(item) {
  return (item.mime_type || '').startsWith('image/')
}

const categoryIdCache = {}

/* Категория в медиа — находим или создаём. */
async function ensureCategory(name) {
  if (categoryIdCache[name]) return categoryIdCache[name]

  const list = await request('/api/admin/media/categories')
  const existing = (list.categories || []).find(c => c.name === name)

  if (existing) {
    categoryIdCache[name] = existing.id
    return existing.id
  }

  const body = new URLSearchParams()
  body.append('name', name)
  const created = await request('/api/admin/media/categories', {
    method: 'POST',
    body
  })
  categoryIdCache[name] = created.category.id
  return created.category.id
}

const PICKER_CATEGORY = {
  office: 'Офис',
  employee: 'Сотрудники'
}

/* Пикер открывается с фильтром по нужной категории. */
async function openPicker(target) {
  pickerTarget.value = target
  pickerError.value = ''
  mediaList.value = []
  pickerOpen.value = true
  pickerLoading.value = true
  pickerFilterName.value = ''
  try {
    const categoryName = PICKER_CATEGORY[target] || 'Сотрудники'
    const categoryId = await ensureCategory(categoryName)
    pickerFilterName.value = categoryName
    const result = await request(
      `/api/admin/media?limit=200&category_id=${categoryId}`
    )
    mediaList.value = result.media || []
  } catch (exc) {
    pickerError.value = String(exc)
  } finally {
    pickerLoading.value = false
  }
}

function selectMedia(item) {
  editing.value.media_id = item.id
  editing.value.media_url = mediaUrl(item)
  pickerOpen.value = false
}

/* Загрузка изображения с компьютера в медиатеку (в нужный раздел). */
const uploadingMedia = ref(false)

function uploadMediaFile(target) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'

  input.onchange = async () => {
    const file = input.files && input.files[0]
    if (!file) return

    uploadingMedia.value = true
    error.value = ''

    try {
      const categoryName = PICKER_CATEGORY[target] || 'Сотрудники'
      const categoryId = await ensureCategory(categoryName)
      const media = await uploadAdminMedia(file, { categoryId })

      editing.value.media_id = media.id
      editing.value.media_url = mediaUrl(media)
    } catch (exc) {
      error.value = String(exc.message || exc)
    } finally {
      uploadingMedia.value = false
    }
  }

  input.click()
}

onMounted(loadData)
</script>

<style scoped>
.administration-contacts {
  max-width: 1200px;
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

.loading-block {
  padding: 60px 0;
  display: flex;
  justify-content: center;
}

.error-text {
  color: #c62828;
  background: #fff0f0;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  margin-bottom: 14px;
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

.department-card {
  border-left-width: 2px;
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

.department-title {
  font-size: 18px;
  font-weight: 800;
}

.inline-actions {
  display: flex;
  gap: 6px;
}

/* формы */
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.field {
  margin-bottom: 12px;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #eef1f5;
  color: #37474f;
  border-radius: 8px;
  padding: 3px 10px;
  font-size: 12px;
}

.chip button {
  border: 0;
  background: transparent;
  color: #c62828;
  cursor: pointer;
  font-weight: 800;
}

/* карточки */
.mini-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  margin-bottom: 10px;
}

.mini-card-body {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.mini-card-thumb {
  flex: 0 0 46px;
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: #eef1f5;
  display: grid;
  place-items: center;
  font-size: 20px;
  overflow: hidden;
}

.mini-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mini-card-info {
  min-width: 0;
}

.mini-card-title {
  font-weight: 700;
  font-size: 15px;
}

.mini-card-meta {
  color: #8b8b8b;
  font-size: 12px;
  word-break: break-word;
}

.mini-card-actions {
  display: flex;
  gap: 4px;
}

.add-department-row {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

/* медиа-выбор */
.media-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.editor-dialog {
  min-width: 540px;
  max-width: 96vw;
}

.dialog-title {
  font-size: 18px;
  font-weight: 800;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 10px;
  max-height: 420px;
  overflow: auto;
}

.media-cell {
  aspect-ratio: 1;
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  background: #f6f7f9;
  overflow: hidden;
  cursor: pointer;
  display: grid;
  place-items: center;
}

.media-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.action-secondary {
  color: #546e7a;
}

.media-hint {
  margin-top: 6px;
  color: #8b8b8b;
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
