<template>
  <q-page class="administration-settings">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>Настройки</h1>
        <p
          >Карта, внешний вид сайта (шрифты, цвета, скругления). Наборы
          настроек.</p
        >
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

    <div v-else>
      <div v-if="error" class="error-text">{{ error }}</div>

      <!--
        ============ ФОРМА НАСТРОЕК ============
        Поля рисуются по группам из схемы (field.group), чтобы «Карта»
        была отдельным видимым блоком, а не последним полем внизу.
      -->
      <section
        v-for="group in fieldGroups"
        :key="group.key"
        class="section-card"
      >
        <div class="section-title">
          <div>{{ group.title }}</div>
        </div>

        <div class="form-grid">
          <div v-for="field in group.fields" :key="field.key" class="field">
            <label>{{ field.label }}</label>

            <!-- Текстовое поле -->
            <q-input
              v-if="field.type === 'text'"
              v-model="values[field.key]"
              outlined
              dense
            />

            <!-- Числовое поле -->
            <q-input
              v-else-if="field.type === 'number'"
              v-model="values[field.key]"
              type="number"
              outlined
              dense
            />

            <!-- Список -->
            <q-select
              v-else-if="field.type === 'select'"
              v-model="values[field.key]"
              :options="field.options || []"
              option-value="value"
              option-label="label"
              emit-value
              map-options
              outlined
              dense
              @update:model-value="value => onFieldChange(field.key, value)"
            />

            <!-- Цвет -->
            <div v-else-if="field.type === 'color'" class="color-control">
              <input
                type="color"
                class="color-swatch"
                :value="values[field.key]"
                @input="values[field.key] = $event.target.value"
              />
              <q-input
                v-model="values[field.key]"
                outlined
                dense
                class="color-hex"
              />
            </div>

            <!-- Переключатель -->
            <q-toggle
              v-else-if="field.type === 'toggle'"
              :model-value="values[field.key] === 'true'"
              @update:model-value="
                value => onFieldChange(field.key, value ? 'true' : 'false')
              "
            />
          </div>
        </div>
      </section>

      <section class="section-card">
        <div class="section-title">
          <div>Проверка ссылок на каталог</div>
        </div>

        <div class="field">
          <label>Состояние (JSON)</label>
          <q-input
            v-model="linkTestInput"
            type="textarea"
            outlined
            dense
            autogrow
            class="link-test-input"
          />
        </div>

        <div class="save-row">
          <q-btn
            outline
            no-caps
            dense
            color="primary"
            label="Проверить кодирование"
            @click="testUrlState"
          />
        </div>

        <div v-if="linkTestError" class="error-text">{{ linkTestError }}</div>

        <div v-else-if="linkTestResult" class="link-test-result">
          <div>
            <b>Читаемая:</b>
            <code>{{ linkTestResult.readable }}</code>
          </div>
          <div>
            <b>Компактная:</b>
            <code>{{ linkTestResult.compact }}</code>
          </div>
          <div><b>Длина токена:</b> {{ linkTestResult.length }} символов</div>
          <pre>{{ linkTestResult.decoded }}</pre>
        </div>
      </section>

      <section class="section-card">
        <div class="save-row">
          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Сохранить"
            :loading="saving"
            @click="save"
          />
        </div>
      </section>

      <!-- ============ СЛОВАРИ СИНОНИМОВ ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Словари синонимов</div>
        </div>

        <p class="section-hint">
          Используются парсером запросов и умным чатом: какие слова считать
          форматом конструкции, городом и ключевым словом.
        </p>

        <div v-if="synonymsError" class="error-text">{{ synonymsError }}</div>

        <div v-if="synonymsLoading" class="synonyms-loading">
          <q-spinner size="22px" />
        </div>

        <template v-else>
          <q-tabs
            v-model="synonymsTab"
            dense
            no-caps
            align="left"
            class="synonyms-tabs"
          >
            <q-tab name="types" label="Форматы" />
            <q-tab name="cities" label="Города" />
            <q-tab name="keywords" label="Ключевые слова" />
          </q-tabs>

          <q-tab-panels v-model="synonymsTab" animated class="synonyms-panels">
            <q-tab-panel name="types">
              <div
                v-for="entry in activeSynonyms"
                :key="entry.uid"
                class="synonym-entry"
              >
                <div class="synonym-entry-head">
                  <q-input
                    v-model="entry.name"
                    outlined
                    dense
                    label="Название формата"
                  />
                  <q-btn
                    flat
                    dense
                    no-caps
                    color="negative"
                    icon="delete"
                    label="Удалить"
                    @click="removeSynonymEntry(entry)"
                  />
                </div>

                <div class="synonym-aliases">
                  <q-chip
                    v-for="(alias, index) in entry.aliases"
                    :key="`${entry.uid}-${index}`"
                    removable
                    dense
                    @remove="entry.aliases.splice(index, 1)"
                  >
                    {{ alias }}
                  </q-chip>
                  <span v-if="!entry.aliases.length" class="field-hint">
                    Синонимов пока нет
                  </span>
                </div>

                <div class="synonym-add">
                  <q-input
                    v-model="entry.newAlias"
                    outlined
                    dense
                    placeholder="Добавить синоним"
                    @keyup.enter="addAlias(entry)"
                  />
                  <q-btn
                    outline
                    no-caps
                    dense
                    color="primary"
                    label="Добавить"
                    @click="addAlias(entry)"
                  />
                </div>
              </div>

              <q-btn
                outline
                no-caps
                dense
                color="primary"
                icon="add"
                label="Добавить формат"
                @click="addSynonymEntry('types')"
              />
            </q-tab-panel>

            <q-tab-panel name="cities">
              <div
                v-for="entry in activeSynonyms"
                :key="entry.uid"
                class="synonym-entry"
              >
                <div class="synonym-entry-head">
                  <q-input
                    v-model="entry.name"
                    outlined
                    dense
                    label="Название города / района"
                  />
                  <q-btn
                    flat
                    dense
                    no-caps
                    color="negative"
                    icon="delete"
                    label="Удалить"
                    @click="removeSynonymEntry(entry)"
                  />
                </div>

                <div class="synonym-aliases">
                  <q-chip
                    v-for="(alias, index) in entry.aliases"
                    :key="`${entry.uid}-${index}`"
                    removable
                    dense
                    @remove="entry.aliases.splice(index, 1)"
                  >
                    {{ alias }}
                  </q-chip>
                  <span v-if="!entry.aliases.length" class="field-hint">
                    Синонимов пока нет
                  </span>
                </div>

                <div class="synonym-add">
                  <q-input
                    v-model="entry.newAlias"
                    outlined
                    dense
                    placeholder="Добавить синоним"
                    @keyup.enter="addAlias(entry)"
                  />
                  <q-btn
                    outline
                    no-caps
                    dense
                    color="primary"
                    label="Добавить"
                    @click="addAlias(entry)"
                  />
                </div>
              </div>

              <q-btn
                outline
                no-caps
                dense
                color="primary"
                icon="add"
                label="Добавить город"
                @click="addSynonymEntry('cities')"
              />
            </q-tab-panel>

            <q-tab-panel name="keywords">
              <p class="field-hint">
                Слово из запроса → каноническое название формата. Например,
                «статика» → «Щит».
              </p>

              <div
                v-for="(row, index) in synonymKeywords"
                :key="row.uid"
                class="keyword-row"
              >
                <q-input
                  v-model="row.alias"
                  outlined
                  dense
                  label="Слово или фраза"
                />
                <q-select
                  v-model="row.canonical"
                  :options="synonymTypeNames"
                  outlined
                  dense
                  label="Формат"
                  use-input
                  new-value-mode="add-unique"
                />
                <q-btn
                  flat
                  dense
                  color="negative"
                  icon="delete"
                  @click="synonymKeywords.splice(index, 1)"
                />
              </div>

              <q-btn
                outline
                no-caps
                dense
                color="primary"
                icon="add"
                label="Добавить ключевое слово"
                @click="addKeywordRow"
              />
            </q-tab-panel>
          </q-tab-panels>

          <div class="save-row">
            <q-btn
              unelevated
              no-caps
              color="primary"
              label="Сохранить словари"
              :loading="synonymsSaving"
              @click="saveSynonyms"
            />
            <q-btn
              outline
              no-caps
              color="negative"
              label="Вернуть стандартные"
              :disable="!synonymsCustom"
              @click="resetSynonyms"
            />
            <span v-if="synonymsUpdatedAt" class="field-hint">
              Изменено: {{ formatDate(synonymsUpdatedAt) }}
            </span>
          </div>
        </template>
      </section>

      <!-- ============ ФАЙЛОХРАНИЛИЩЕ ALBION ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Файлохранилище Albion</div>
        </div>

        <div v-if="albionError" class="error-text">{{ albionError }}</div>

        <div class="form-grid">
          <div class="field">
            <label>Режим хранения</label>
            <q-select
              v-model="albion.mode"
              :options="albionModeOptions"
              option-value="value"
              option-label="label"
              emit-value
              map-options
              outlined
              dense
            />
          </div>

          <div class="field">
            <label>URL хранилища</label>
            <q-input
              v-model="albion.url"
              outlined
              dense
              placeholder="https://files.example.ru"
            />
          </div>

          <div class="field">
            <label>ID папки</label>
            <q-input
              v-model="albion.folder_id"
              outlined
              dense
              placeholder="Необязательно, если папка привязана к токену"
            />
          </div>

          <div class="field">
            <label>TTL, дней</label>
            <q-input
              v-model.number="albion.ttl_days"
              type="number"
              outlined
              dense
            />
          </div>

          <div class="field">
            <label>Токен</label>
            <q-input
              v-model="albionToken"
              type="password"
              outlined
              dense
              autocomplete="new-password"
              :placeholder="
                albion.token_set
                  ? 'Токен сохранён — оставьте поле пустым'
                  : 'Вставьте токен Albion'
              "
            />
            <div v-if="albion.token_set" class="field-hint">
              Сохранённый токен: {{ albion.token_hint }}
            </div>
          </div>
        </div>

        <div class="albion-warning">
          В режиме «albion» каждый новый файл сохраняется локально и дублируется
          в Albion; публичные ссылки ведут на Albion. Уже загруженные файлы не
          переносятся.
        </div>

        <div class="albion-actions">
          <q-btn
            unelevated
            no-caps
            color="primary"
            label="Сохранить"
            :loading="albionSaving"
            @click="saveAlbion()"
          />
          <q-btn
            outline
            no-caps
            color="primary"
            label="Проверить связь"
            :loading="albionVerifying"
            @click="verifyAlbion"
          />
          <q-btn
            flat
            no-caps
            color="negative"
            label="Очистить токен"
            :disable="!albion.token_set"
            :loading="albionSaving"
            @click="clearAlbionToken"
          />
        </div>

        <div
          v-if="albionVerifyResult"
          class="albion-verify"
          :class="albionVerifyResult.ok ? 'ok' : 'error'"
        >
          <template v-if="albionVerifyResult.ok">
            Связь установлена<template v-if="albionVerifyResult.name">
              : {{ albionVerifyResult.name }}</template
            >. Права: {{ (albionVerifyResult.scopes || []).join(', ') || '—' }}.
          </template>
          <template v-else>{{ albionVerifyResult.error }}</template>
        </div>
      </section>

      <!-- ============ НАБОРЫ ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Наборы настроек</div>
        </div>

        <div class="preset-create">
          <q-input
            v-model="newPresetName"
            outlined
            dense
            placeholder="Название набора"
            @keyup.enter="createPreset"
          />
          <q-btn
            outline
            no-caps
            color="primary"
            label="Создать набор"
            :loading="presetBusy"
            @click="createPreset"
          />
        </div>

        <div v-if="!presets.length" class="empty-text"> Наборов пока нет. </div>

        <article v-for="preset in presets" :key="preset.id" class="preset-row">
          <div class="preset-info">
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-date">{{ formatDate(preset.created_at) }}</div>
          </div>

          <div class="preset-actions">
            <q-btn
              flat
              dense
              no-caps
              color="primary"
              icon="play_arrow"
              label="Применить"
              :disable="presetBusy"
              @click="applyPreset(preset)"
            />
            <q-btn
              flat
              dense
              no-caps
              color="negative"
              icon="delete"
              label="Удалить"
              :disable="presetBusy"
              @click="deletePreset(preset)"
            />
          </div>
        </article>
      </section>

      <!-- ============ СБРОС ============ -->
      <section class="section-card">
        <div class="section-title">
          <div>Сброс</div>
        </div>

        <div class="reset-row">
          <div class="reset-hint">
            Вернуть все параметры к значениям по умолчанию.
          </div>
          <q-btn
            outline
            no-caps
            color="negative"
            label="Сбросить к значениям по умолчанию"
            :loading="saving"
            @click="resetToDefaults"
          />
        </div>
      </section>
    </div>

    <!-- ============ УВЕДОМЛЕНИЯ ============ -->
    <transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">
        {{ toast.text }}
      </div>
    </transition>

    <!-- Подтверждение (опасные действия и уход с несохранёнными правками). -->
    <q-dialog v-model="confirmOpen" persistent>
      <q-card class="confirm-dialog">
        <q-card-section>
          <div class="confirm-text">{{ confirmText }}</div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" @click="resolveConfirm(false)" />
          <q-btn
            unelevated
            no-caps
            color="negative"
            :label="confirmAction"
            @click="resolveConfirm(true)"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { applyAppearanceSettings } from '../boot/settings'
import { setAvailableMode } from '../config/availableMode'
import { setShowDynCount } from '../config/dynCount'
import {
  decodeUrlState,
  describeUrlState,
  encodeUrlState
} from '../utils/urlState'
import { adminRequest as request } from '../services/adminApi'

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const presetBusy = ref(false)
const error = ref('')

/*
 * Окно подтверждения вместо нативных confirm: спрашиваем и об опасных
 * действиях (сброс, удаление набора, очистка токена), и при уходе
 * страницы с несохранёнными настройками.
 */
const confirmOpen = ref(false)
const confirmText = ref('')
const confirmAction = ref('Подтвердить')
let confirmResolve = null

function askConfirm(text, action = 'Подтвердить') {
  return new Promise(resolve => {
    confirmText.value = String(text || '')
    confirmAction.value = action
    confirmResolve = resolve
    confirmOpen.value = true
  })
}

function resolveConfirm(ok) {
  confirmOpen.value = false

  if (confirmResolve) {
    const resolve = confirmResolve

    confirmResolve = null
    resolve(ok)
  }
}

/*
 * Снимок формы: берём после загрузки и после полного сохранения.
 * По нему понимаем, остались ли несохранённые правки — раньше уход со
 * страницы терял их молча.
 */
const savedSnapshot = ref(null)

function snapshotState() {
  return JSON.stringify(values.value)
}

function markSaved() {
  savedSnapshot.value = snapshotState()
}

/* Live-сохранение одного ключа: отмечаем сохранённым только его. */
function markKeySaved(key) {
  if (savedSnapshot.value === null) {
    return
  }

  try {
    const parsed = JSON.parse(savedSnapshot.value)

    parsed[key] = values.value[key]
    savedSnapshot.value = JSON.stringify(parsed)
  } catch {
    markSaved()
  }
}

/* ---------- Словари синонимов ---------- */
const synonymsTab = ref('types')
const synonymsLoading = ref(true)
const synonymsSaving = ref(false)
const synonymsError = ref('')
const synonymsCustom = ref(false)
const synonymsUpdatedAt = ref(null)
const synonymTypes = ref([])
const synonymCities = ref([])
const synonymKeywords = ref([])
const synonymsSnapshot = ref(null)

function synonymsState() {
  return JSON.stringify({
    types: synonymTypes.value,
    cities: synonymCities.value,
    keywords: synonymKeywords.value
  })
}

const synonymsDirty = computed(
  () =>
    synonymsSnapshot.value !== null &&
    synonymsState() !== synonymsSnapshot.value
)

const dirty = computed(
  () =>
    (savedSnapshot.value !== null && snapshotState() !== savedSnapshot.value) ||
    synonymsDirty.value
)

onBeforeRouteLeave(() => {
  if (!dirty.value) {
    return true
  }

  return askConfirm(
    'Есть несохранённые настройки. Уйти со страницы без сохранения?',
    'Уйти без сохранения'
  )
})

/* Перезагрузка/закрытие вкладки: нативный диалог браузера. */
function onBeforeUnload(event) {
  if (!dirty.value) {
    return
  }

  event.preventDefault()
  event.returnValue = ''
}

const schema = ref([])

/* ---------- Проверка ссылок на каталог ---------- */
const linkTestInput = ref(
  JSON.stringify(
    {
      mode: 'list',
      cities: ['Ростов-на-Дону'],
      types: ['Щит'],
      months: ['Октябрь', 'Ноябрь'],
      monthLogic: 'OR',
      searchQuery: '',
      point: null,
      radius: null,
      address: ''
    },
    null,
    2
  )
)
const linkTestError = ref('')
const linkTestResult = ref(null)

/* ---------- Albion: отдельные настройки, секрет не возвращается ---------- */
const albion = ref({
  mode: 'local',
  url: '',
  folder_id: '',
  ttl_days: 90,
  token_set: false,
  token_hint: ''
})
const albionToken = ref('')
const albionSaving = ref(false)
const albionVerifying = ref(false)
const albionError = ref('')
const albionVerifyResult = ref(null)
const albionModeOptions = [
  { label: 'Локально (по умолчанию)', value: 'local' },
  { label: 'Локально + Albion', value: 'albion' }
]

function applyAlbion(data) {
  const config = data || {}

  albion.value = {
    mode: config.mode === 'albion' ? 'albion' : 'local',
    url: config.url || '',
    folder_id: config.folder_id || '',
    ttl_days: Number(config.ttl_days ?? 90),
    token_set: Boolean(config.token_set),
    token_hint: config.token_hint || ''
  }
}

async function loadAlbion() {
  try {
    const data = await request('/api/admin/integration/albion')
    applyAlbion(data)
  } catch (exc) {
    albionError.value = String(exc.message || exc)
  }
}

async function saveAlbion(extra = {}) {
  if (albionSaving.value) return

  albionSaving.value = true
  albionError.value = ''
  albionVerifyResult.value = null

  try {
    const payload = {
      mode: albion.value.mode,
      url: albion.value.url,
      folder_id: albion.value.folder_id,
      ttl_days: Number(albion.value.ttl_days) || 90
    }

    if (albionToken.value) {
      payload.token = albionToken.value
    }

    const data = await request('/api/admin/integration/albion', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, ...extra })
    })

    applyAlbion(data)
    albionToken.value = ''
    notify('Настройки Albion сохранены.')
  } catch (exc) {
    albionError.value = String(exc.message || exc)
    notify(albionError.value, 'error')
  } finally {
    albionSaving.value = false
  }
}

async function verifyAlbion() {
  if (albionVerifying.value) return

  albionVerifying.value = true
  albionError.value = ''
  albionVerifyResult.value = null

  try {
    const data = await request('/api/admin/integration/albion/verify', {
      method: 'POST'
    })
    albionVerifyResult.value = data
    notify('Связь с Albion установлена.')
  } catch (exc) {
    const message = String(exc.message || exc)
    albionError.value = message
    albionVerifyResult.value = { ok: false, error: message }
    notify(message, 'error')
  } finally {
    albionVerifying.value = false
  }
}

async function clearAlbionToken() {
  if (!(await askConfirm('Очистить сохранённый токен Albion?', 'Очистить'))) {
    return
  }

  await saveAlbion({ token: '' })
}

/*
 * Группы полей формы. Заголовки и порядок блоков; неизвестные группы
 * из схемы идут в конец, чтобы новое поле не потерялось.
 */
const GROUP_TITLES = {
  map: 'Карта',
  sides: 'Отображение сторон',
  links: 'Ссылки и QR',
  appearance: 'Параметры внешнего вида'
}

const GROUP_ORDER = ['map', 'sides', 'links', 'appearance']

const fieldGroups = computed(() => {
  const groups = new Map()

  for (const field of schema.value) {
    const key = field.group || 'appearance'

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        title: GROUP_TITLES[key] || key,
        fields: []
      })
    }

    groups.get(key).fields.push(field)
  }

  const rank = key => {
    const index = GROUP_ORDER.indexOf(key)

    return index === -1 ? GROUP_ORDER.length : index
  }

  return [...groups.values()].sort((a, b) => rank(a.key) - rank(b.key))
})
const values = ref({})
const presets = ref([])
const newPresetName = ref('')

const toast = ref({ show: false, type: 'ok', text: '' })
let toastTimer = null

function notify(text, type = 'ok') {
  toast.value = { show: true, type, text }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

/* Применяет ответ API к состоянию формы (без перезагрузки). */
function applyData(data) {
  schema.value = data.schema || []
  presets.value = data.presets || []

  const current = data.current || {}
  const next = {}

  for (const field of schema.value) {
    next[field.key] = String(current[field.key] ?? field.default ?? '')
  }

  values.value = next
}

async function load(showSpinner = true) {
  if (showSpinner) loading.value = true
  error.value = ''
  try {
    const data = await request('/api/admin/settings')
    applyData(data)

    /* Исходный снимок: с ним сравниваем правки формы. */
    markSaved()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

/*
 * Все записи настроек идут строго по очереди: live-сохранение и общий PUT
 * не должны выполняться одновременно — иначе ответы применяются в
 * произвольном порядке, и одна из правок затирает другую.
 *
 * Ошибка одной задачи не останавливает очередь.
 */
let settingsWriteQueue = Promise.resolve()

function enqueueSettingsWrite(task) {
  const result = settingsWriteQueue.then(task, task)

  settingsWriteQueue = result.then(
    () => undefined,
    () => undefined
  )

  return result
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    /* values.value читается в момент выполнения, а не постановки в очередь:
       live-правка, сделанная за это время, попадёт в общий PUT. */
    const data = await enqueueSettingsWrite(() =>
      request('/api/admin/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: values.value })
      })
    )
    applyData(data)

    /* Сохранено целиком — снимок обновляем, «грязных» правок нет. */
    markSaved()

    // Применяем новые значения сразу — без перезагрузки страницы
    // (в т.ч. режим доступности `available_mode` в списке/попапах/чате).
    applyAppearanceSettings(data.current)

    notify('Настройки сохранены.')
  } catch (exc) {
    error.value = String(exc)
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

/*
 * Панель проверки ссылок: показывает обе схемы для одного состояния
 * и декодирует компактный токен обратно. Нужна, чтобы переключать
 * формат и проверять совместимость без публикации.
 */
function testUrlState() {
  linkTestError.value = ''
  linkTestResult.value = null

  let state

  try {
    state = JSON.parse(linkTestInput.value)
  } catch {
    linkTestError.value = 'Некорректный JSON состояния.'
    return
  }

  try {
    const params = new URLSearchParams()
    const mode = String(state.mode || 'map')
    params.set('mode', mode)

    if (Array.isArray(state.cities) && state.cities.length) {
      params.set('city', state.cities.join(','))
    }

    if (Array.isArray(state.types) && state.types.length) {
      params.set('type', state.types.join(','))
    }

    if (Array.isArray(state.months) && state.months.length) {
      params.set('months', state.months.join(','))
    }

    if (state.monthLogic === 'AND') {
      params.set('monthLogic', 'AND')
    }

    if (state.searchQuery) {
      params.set('address', state.searchQuery)
    }

    if (state.point) {
      params.set('lat', String(state.point.lat))
      params.set('lng', String(state.point.lng))
    }

    if (state.radius) {
      params.set('radius', String(state.radius))
    }

    if (state.address) {
      params.set('addr', state.address)
    }

    const format =
      values.value.url_state_token_format === 'base32' ? 'base32' : 'base64url'
    const compact = encodeUrlState(state, format)
    const decoded = decodeUrlState(compact)

    linkTestResult.value = {
      readable: `/vozmozhnosti?${params.toString()}`,
      compact: `/vozmozhnosti?s=${compact}`,
      length: compact.length,
      decoded: decoded ? describeUrlState(decoded) : 'Не удалось декодировать'
    }
  } catch (exc) {
    linkTestError.value = String(exc?.message || exc)
  }
}

/*
 * Поля, которые применяются СРАЗУ при изменении (без кнопки «Сохранить»):
 * отображение сторон и показ количества динамики. Значение тут же уходит
 * на сервер (точечно, только этот ключ), поэтому обновление видно и на
 * публичных страницах, и в других вкладках после перезагрузки.
 */
const LIVE_KEYS = new Set(['available_mode', 'show_dyn_count'])

async function onFieldChange(key, value) {
  values.value[key] = value

  if (!LIVE_KEYS.has(key)) {
    return
  }

  // Мгновенно применяем на текущей странице (список/попапы/чат реактивны).
  if (key === 'available_mode') {
    setAvailableMode(value)
  } else if (key === 'show_dyn_count') {
    setShowDynCount(value)
  }

  try {
    await enqueueSettingsWrite(() =>
      request('/api/admin/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        // Точечно: сохраняем только изменённый ключ, не затирая прочие правки.
        body: JSON.stringify({ settings: { [key]: value } })
      })
    )

    /* Сервер принял только этот ключ — отмечаем сохранённым его. */
    markKeySaved(key)
    notify('Применено.')
  } catch (exc) {
    notify(String(exc), 'error')
  }
}

/* ---------- Словари синонимов: загрузка, правка, сохранение ---------- */
let synonymUid = 0

function toSynonymEntries(source) {
  return Object.entries(source || {}).map(([name, config]) => ({
    uid: ++synonymUid,
    name,
    aliases: Array.isArray(config?.aliases) ? [...config.aliases] : [],
    newAlias: ''
  }))
}

const activeSynonyms = computed(() =>
  synonymsTab.value === 'cities' ? synonymCities.value : synonymTypes.value
)

const synonymTypeNames = computed(() =>
  synonymTypes.value.map(entry => entry.name.trim()).filter(Boolean)
)

function applySynonyms(data) {
  const dictionary = data?.dictionary || {}

  synonymTypes.value = toSynonymEntries(dictionary.types)
  synonymCities.value = toSynonymEntries(dictionary.cities)
  synonymKeywords.value = Object.entries(dictionary.keywords || {}).map(
    ([alias, canonical]) => ({
      uid: ++synonymUid,
      alias,
      canonical: String(canonical || '')
    })
  )

  synonymsCustom.value = Boolean(data?.is_custom)
  synonymsUpdatedAt.value = data?.updated_at || null
  synonymsSnapshot.value = synonymsState()
}

async function loadSynonyms() {
  synonymsLoading.value = true
  synonymsError.value = ''

  try {
    const data = await request('/api/admin/settings/synonyms')
    applySynonyms(data)
  } catch (exc) {
    synonymsError.value = String(exc)
  } finally {
    synonymsLoading.value = false
  }
}

function addAlias(entry) {
  const alias = String(entry.newAlias || '').trim()

  if (!alias) {
    return
  }

  if (!entry.aliases.includes(alias)) {
    entry.aliases.push(alias)
  }

  entry.newAlias = ''
}

function addSynonymEntry(kind) {
  const target = kind === 'cities' ? synonymCities : synonymTypes

  target.value.push({
    uid: ++synonymUid,
    name: '',
    aliases: [],
    newAlias: ''
  })
}

function removeSynonymEntry(entry) {
  const target = synonymsTab.value === 'cities' ? synonymCities : synonymTypes

  target.value = target.value.filter(item => item.uid !== entry.uid)
}

function addKeywordRow() {
  synonymKeywords.value.push({
    uid: ++synonymUid,
    alias: '',
    canonical: synonymTypeNames.value[0] || ''
  })
}

function entriesToObject(entries, label) {
  const result = {}

  for (const entry of entries) {
    const name = String(entry.name || '').trim()

    if (!name) {
      throw new Error(`Укажите название в разделе «${label}»`)
    }

    if (Object.prototype.hasOwnProperty.call(result, name)) {
      throw new Error(`«${name}» повторяется в разделе «${label}»`)
    }

    result[name] = {
      aliases: [
        ...new Set(
          entry.aliases.map(alias => String(alias).trim()).filter(Boolean)
        )
      ]
    }
  }

  return result
}

function buildSynonymsPayload() {
  const keywords = {}

  for (const row of synonymKeywords.value) {
    const alias = String(row.alias || '').trim()
    const canonical = String(row.canonical || '').trim()

    if (!alias && !canonical) {
      continue
    }

    if (!alias || !canonical) {
      throw new Error(
        'У ключевого слова должны быть заполнены и фраза, и формат'
      )
    }

    if (Object.prototype.hasOwnProperty.call(keywords, alias)) {
      throw new Error(`Ключевое слово «${alias}» повторяется`)
    }

    keywords[alias] = canonical
  }

  return {
    types: entriesToObject(synonymTypes.value, 'Форматы'),
    cities: entriesToObject(synonymCities.value, 'Города'),
    keywords
  }
}

async function saveSynonyms() {
  if (synonymsSaving.value) {
    return
  }

  synonymsSaving.value = true
  synonymsError.value = ''

  try {
    const data = await request('/api/admin/settings/synonyms', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dictionary: buildSynonymsPayload() })
    })

    applySynonyms(data)
    notify('Словари синонимов сохранены.')
  } catch (exc) {
    const message = String(exc?.message || exc)

    synonymsError.value = message
    notify(message, 'error')
  } finally {
    synonymsSaving.value = false
  }
}

async function resetSynonyms() {
  if (
    !(await askConfirm(
      'Вернуть стандартные словари синонимов? Пользовательские правки будут удалены.',
      'Вернуть стандартные'
    ))
  ) {
    return
  }

  synonymsSaving.value = true
  synonymsError.value = ''

  try {
    const data = await request('/api/admin/settings/synonyms/reset', {
      method: 'POST'
    })

    applySynonyms(data)
    notify('Возвращены стандартные словари.')
  } catch (exc) {
    const message = String(exc?.message || exc)

    synonymsError.value = message
    notify(message, 'error')
  } finally {
    synonymsSaving.value = false
  }
}

async function createPreset() {
  const name = newPresetName.value.trim()
  if (!name) {
    notify('Укажите название набора', 'error')
    return
  }

  presetBusy.value = true
  try {
    const data = await request('/api/admin/settings/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    applyData(data)
    newPresetName.value = ''
    notify(`Набор «${name}» создан.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function applyPreset(preset) {
  presetBusy.value = true
  try {
    const data = await enqueueSettingsWrite(() =>
      request(`/api/admin/settings/presets/${preset.id}/apply`, {
        method: 'POST'
      })
    )
    applyData(data)
    markSaved()
    notify(`Набор «${preset.name}» применён.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function deletePreset(preset) {
  if (!(await askConfirm(`Удалить набор «${preset.name}»?`, 'Удалить'))) {
    return
  }

  presetBusy.value = true
  try {
    const data = await request(`/api/admin/settings/presets/${preset.id}`, {
      method: 'DELETE'
    })
    applyData(data)
    notify(`Набор «${preset.name}» удалён.`)
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    presetBusy.value = false
  }
}

async function resetToDefaults() {
  if (
    !(await askConfirm(
      'Сбросить настройки к значениям по умолчанию?',
      'Сбросить'
    ))
  ) {
    return
  }

  saving.value = true
  try {
    const data = await enqueueSettingsWrite(() =>
      request('/api/admin/settings/reset', { method: 'POST' })
    )
    applyData(data)
    markSaved()
    notify('Настройки сброшены к значениям по умолчанию.')
  } catch (exc) {
    notify(String(exc), 'error')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', onBeforeUnload)
  load()
  loadAlbion()
  loadSynonyms()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
})
</script>

<style scoped>
/* Окно подтверждения. */
.confirm-dialog {
  width: min(440px, 92vw);
  border-radius: 14px;
}

.confirm-text {
  color: #17212b;
  font-size: 14px;
  line-height: 1.45;
}

.administration-settings {
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

.section-title {
  font-size: 17px;
  font-weight: 800;
  margin-bottom: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px 18px;
}

.field label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #66727c;
}

.color-control {
  display: flex;
  align-items: center;
  gap: 10px;
}

.color-swatch {
  width: 42px;
  height: 40px;
  padding: 0;
  border: 1px solid #e4e6ea;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}

.color-hex {
  flex: 1;
}

.save-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.preset-create {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.preset-create .q-input {
  flex: 1;
}

.preset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid #e4e6ea;
  border-radius: 12px;
  margin-bottom: 10px;
}

.preset-name {
  font-weight: 700;
  font-size: 15px;
}

.preset-date {
  color: #8b8b8b;
  font-size: 12px;
}

.preset-actions {
  display: flex;
  gap: 4px;
}

.reset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.reset-hint {
  color: #777;
  font-size: 14px;
}

.field-hint {
  margin-top: 4px;
  color: #8b8b8b;
  font-size: 12px;
}

.albion-warning {
  margin-top: 14px;
  padding: 10px 12px;
  background: #fff8e1;
  border: 1px solid #f2d98a;
  border-radius: 10px;
  color: #7a5b00;
  font-size: 13px;
}

.albion-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.albion-verify {
  margin-top: 12px;
  font-size: 13px;
}

.albion-verify.ok {
  color: #2e7d32;
}

.albion-verify.error {
  color: #c62828;
}

/* всплывающее уведомление */
.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 5000;
  padding: 12px 18px;
  border-radius: 10px;
  font-size: 14px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
}

.toast.ok {
  background: #2e7d32;
  color: #fff;
}

.toast.error {
  background: #c62828;
  color: #fff;
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.link-test-result {
  display: flex;
  flex-direction: column;
  gap: 8px;

  margin-top: 14px;

  font-size: 12px;
}

.link-test-result code {
  display: inline-block;

  max-width: 100%;
  padding: 3px 6px;

  overflow-wrap: anywhere;

  border-radius: 5px;
  background: #f1f3f4;
}

.link-test-result pre {
  max-height: 260px;
  margin: 0;
  padding: 10px;

  overflow: auto;

  border-radius: 8px;
  background: #f7f8f9;

  font-size: 11px;
  line-height: 1.45;
}

/* ---------- словари синонимов ---------- */
.section-hint {
  margin: 0 0 14px;
  color: #6f7a82;
  font-size: 13px;
}

.synonyms-loading {
  padding: 16px 0;
}

.synonyms-tabs {
  margin-bottom: 8px;
  border-bottom: 1px solid #eceff1;
}

.synonyms-panels {
  background: transparent;
}

.synonyms-panels :deep(.q-tab-panel) {
  padding: 12px 0 0;
}

.synonym-entry {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e6eaec;
  border-radius: 10px;
  background: #fafbfb;
}

.synonym-entry-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.synonym-entry-head .q-input {
  flex: 1;
  min-width: 0;
}

.synonym-aliases {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  min-height: 28px;
}

.synonym-add {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.synonym-add .q-input {
  flex: 1;
  min-width: 0;
}

.keyword-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 220px) 36px;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.save-row {
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

@media (max-width: 700px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .preset-create {
    flex-direction: column;
    align-items: stretch;
  }

  .keyword-row {
    grid-template-columns: 1fr;
  }
}
</style>
