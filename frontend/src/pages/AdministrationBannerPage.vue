<template>
  <component :is="embedded ? 'div' : 'q-page'" class="admin-banner">
    <div class="page-header">
      <div>
        <div class="eyebrow">АДМИНИСТРАЦИЯ</div>
        <h1>БАННЕР-ДОРОГА</h1>
        <p>
          Код поведения 3D-баннера и настройки, которые он читает из своего
          блока <code>#banner-settings</code>.
        </p>
      </div>

      <div class="header-actions">
        <q-btn
          color="primary"
          no-caps
          label="Сохранить"
          :loading="saving"
          :disable="!slide || !dirty"
          @click="save"
        />
        <q-btn
          outline
          no-caps
          label="Запустить"
          :disable="!slide || dirty"
          @click="restartPreview"
        />
        <q-btn
          flat
          no-caps
          label="PDF"
          @click="downloadPdf"
        />
        <q-btn
          flat
          no-caps
          icon="tune"
          label="Настройки"
          @click="router.push('/administration/roadrunner?tab=ai-settings')"
        />
        <q-btn
          flat
          no-caps
          icon="movie"
          label="Генератор"
          @click="router.push('/administration/roadrunner?tab=scenarios')"
        />
        <q-btn
          v-if="!embedded"
          flat
          no-caps
          icon="arrow_back"
          label="Назад"
          @click="router.push('/administration/dashboard')"
        />
      </div>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>

    <p v-if="!loading && !slide" class="empty-text">
      Слайд «Светофорные объекты» не найден. Создайте его в разделе «Главная
      страница» с типом «Светофорные объекты (код баннера)».
    </p>

    <template v-if="slide">
      <div v-if="view === 'banner'" class="toolbar">
        <label class="file-btn">
          <input
            type="file"
            accept=".html,.htm,.txt,text/html,text/plain"
            @change="onFile"
          />
          Заменить файлом
        </label>
        <q-btn
          flat
          dense
          no-caps
          label="Скачать код"
          :disable="!code"
          @click="download"
        />
        <q-btn
          flat
          dense
          no-caps
          label="Сбросить к стандартному"
          @click="resetCode"
        />
        <span class="hint"
          >{{ codeSize }} · {{ settingsStatus }}. Код сохраняется в базе
          данных.</span
        >
        <span v-if="dirty" class="dirty">есть несохранённые изменения</span>
      </div>

      <!-- Панель проекции: те же пресеты, что и в демо-сцене. -->
      <section v-if="view === 'projection'" class="projection-console">
        <div class="pc-topbar">
          <div class="pc-mode">
            <span class="pc-mode-label">РЕЖИМ</span>
            <q-btn-toggle
              :model-value="isCustom ? 'custom' : 'default'"
              :options="[
                { label: 'По умолчанию', value: 'default' },
                { label: 'Произвольный', value: 'custom' }
              ]"
              dense
              no-caps
              unelevated
              toggle-color="primary"
              color="grey-3"
              text-color="grey-8"
              @update:model-value="setMode"
            />
          </div>

          <div class="pc-topbar-controls">
          <q-btn
            class="pc-play"
            no-caps
            :label="settingValue('paused') ? 'Пуск' : 'Пауза'"
            :icon="settingValue('paused') ? 'play_arrow' : 'pause'"
            @click="togglePaused"
          />

          <SettingKnob
            label="Скорость"
            :value="settingValue('speedFactor')"
            :min="0.2"
            :max="2"
            :step="0.05"
            unit="×"
            @update:value="v => setSetting('speedFactor', v)"
          />
          <SettingKnob
            label="Поток"
            :value="settingValue('flowDensity')"
            :min="0.5"
            :max="3"
            :step="0.05"
            unit="×"
            @update:value="v => setSetting('flowDensity', v)"
          />

          <q-select
            class="pc-select"
            dense
            outlined
            emit-value
            map-options
            :model-value="settingValue('cameraPreset')"
            :options="cameraPresetOptions"
            @update:model-value="applyCameraPreset"
          />
          <div class="pc-mode-scoped" :class="{ 'pc-disabled': !isCustom }">
          <q-select
            class="pc-select"
            dense
            outlined
            emit-value
            map-options
            :model-value="settingValue('weatherPreset')"
            :options="weatherPresetOptions"
            @update:model-value="applyWeatherPreset"
          />
          <q-select
            class="pc-select"
            dense
            outlined
            emit-value
            map-options
            :model-value="settingValue('holidayPreset')"
            :options="holidayPresetOptions"
            @update:model-value="applyHolidayPreset"
          />
          </div>

          <q-btn class="pc-action" no-caps icon="shuffle" label="Случайно" @click="randomize" />
          <q-btn class="pc-action" no-caps icon="restart_alt" label="Сброс" @click="resetProjection" />
          </div>
        </div>

        <div v-if="!isCustom" class="pc-mode-hint">
          Погода и праздники синхронизируются с реальными данными, сценарии не
          применяются. Камера и сцена доступны в любом режиме. Переключитесь на
          «Произвольный», чтобы задать свою погоду, праздники и сценарий.
        </div>

        <q-tabs
          v-if="!activeProjectionTab"
          v-model="projectionTab"
          dark
          dense
          no-caps
          align="left"
          active-color="amber"
          indicator-color="amber"
          class="pc-tabs"
          :class="{ 'pc-disabled': !isCustom }"
        >
          <q-tab name="scenarios" icon="movie" label="Сценарии" />
          <q-tab name="holidays" icon="park" label="Праздники" />
          <q-tab name="weather" icon="cloud" label="Погода" />
          <q-tab name="camera" icon="videocam" label="Камера и сцена" />
          <q-tab name="docs" icon="description" label="API для агентов" />
        </q-tabs>

        <div
          class="pc-body"
          :class="{
            'pc-disabled': !isCustom && ['weather', 'holidays'].includes(projectionTab)
          }"
        >
          <div v-if="projectionTab === 'scenarios'" class="pc-section">
            <h3>Генератор сценариев</h3>
            <p>
              Готовые сценарии и AI-генератор находятся на вкладке «Сценарии».
              Таймлайн событий и журнал воспроизведения — там же.
            </p>
            <q-btn
              no-caps
              color="amber"
              text-color="dark"
              label="Открыть сценарии"
              @click="router.push('/administration/roadrunner?tab=scenarios')"
            />
          </div>

          <div v-else-if="projectionTab === 'holidays'" class="pc-section">
            <h3>Генератор праздников</h3>
            <p>
              Пресет включает набор атрибутов, палитру гирлянд и оформление.
              Любой из элементов можно включить вручную — пресет станет
              «Своим набором».
            </p>
            <div class="pc-cards">
              <button
                v-for="preset in holidayCards"
                :key="preset.value"
                type="button"
                class="pc-card"
                :class="{ 'is-active': settingValue('holidayPreset') === preset.value }"
                @click="applyHolidayPreset(preset.value)"
              >
                <span class="pc-card-icon">{{ preset.emoji }}</span>
                <b>{{ preset.label }}</b>
                <small>{{ preset.hint }}</small>
              </button>
            </div>
            <h4 class="pc-group-title">Оформление</h4>
            <div class="pc-knobs">
              <SettingKnob
                v-for="key in ['decorDensity','decorSize','decorGlow','precipitation']"
                :key="key"
                :label="settingLabel(key)"
                :value="settingValue(key)"
                :min="settingsByKey[key]?.min"
                :max="settingsByKey[key]?.max"
                :step="settingsByKey[key]?.step"
                :unit="settingsByKey[key]?.unit || ''"
                @update:value="v => setSetting(key, v)"
              />
            </div>
            <div class="pc-toggles">
              <button
                v-for="key in decorKeys"
                :key="key"
                type="button"
                class="pc-toggle-card"
                :class="{ 'is-on': settingValue(key) }"
                @click="setSetting(key, !settingValue(key))"
              >
                <span>{{ settingLabel(key) }}</span>
                <small>{{ settingValue(key) ? 'включено' : 'выключено' }}</small>
              </button>
            </div>
          </div>

          <div v-else-if="projectionTab === 'weather'" class="pc-section">
            <h3>Генератор погоды</h3>
            <p>
              Реальная погода либо атмосферный пресет. Гроза добавляет вспышки
              молний с подсветкой сцены, дождь и снег — частицы с ветром.
            </p>
            <div class="pc-cards">
              <button
                v-for="preset in weatherCards"
                :key="preset.value"
                type="button"
                class="pc-card"
                :class="{ 'is-active': settingValue('weatherPreset') === preset.value }"
                @click="applyWeatherPreset(preset.value)"
              >
                <span class="pc-card-icon">{{ preset.emoji }}</span>
                <b>{{ preset.label }}</b>
                <small>{{ preset.hint }}</small>
              </button>
            </div>
            <h4 class="pc-group-title">Атмосфера</h4>
            <div class="pc-knobs">
              <SettingKnob
                v-for="key in ['precipitation','wind','lightning','fog','brightness']"
                :key="key"
                :label="settingLabel(key)"
                :value="settingValue(key)"
                :min="settingsByKey[key]?.min"
                :max="settingsByKey[key]?.max"
                :step="settingsByKey[key]?.step"
                :unit="settingsByKey[key]?.unit || ''"
                @update:value="v => setSetting(key, v)"
              />
            </div>
          </div>

          <div v-else-if="projectionTab === 'camera'" class="pc-section">
            <h3>Камера и сцена</h3>
            <p>
              Ракурс задаётся пресетом; азимут, наклон и зум можно подкрутить
              вручную. Все изменения сразу видны в предпросмотре.
            </p>
            <div class="pc-cards">
              <button
                v-for="preset in cameraCards"
                :key="preset.value"
                type="button"
                class="pc-card"
                :class="{ 'is-active': settingValue('cameraPreset') === preset.value }"
                @click="applyCameraPreset(preset.value)"
              >
                <span class="pc-card-icon">{{ preset.emoji }}</span>
                <b>{{ preset.label }}</b>
                <small>{{ preset.hint }}</small>
              </button>
            </div>
            <div class="pc-split">
              <section class="pc-group">
                <h4 class="pc-group-title">Ракурс</h4>
                <div class="pc-knobs">
                  <SettingKnob
                    v-for="key in ['tilt','rotation','scale']"
                    :key="key"
                    :label="settingLabel(key)"
                    :value="settingValue(key)"
                    :min="settingsByKey[key]?.min"
                    :max="settingsByKey[key]?.max"
                    :step="settingsByKey[key]?.step"
                    :unit="settingsByKey[key]?.unit || ''"
                    @update:value="v => setSetting(key, v)"
                  />
                </div>
              </section>

              <div class="pc-divider" aria-hidden="true"></div>

              <section class="pc-group">
                <h4 class="pc-group-title">Движение</h4>
                <div class="pc-knobs">
                  <SettingKnob
                    v-for="key in ['speedFactor','speedWave','speedWavePeriod','dayNightPeriod']"
                    :key="key"
                    :label="settingLabel(key)"
                    :value="settingValue(key)"
                    :min="settingsByKey[key]?.min"
                    :max="settingsByKey[key]?.max"
                    :step="settingsByKey[key]?.step"
                    :unit="settingsByKey[key]?.unit || ''"
                    @update:value="v => setSetting(key, v)"
                  />
                </div>
              </section>
            </div>

            <h4 class="pc-group-title">Трафик</h4>
            <div class="pc-knobs">
              <SettingKnob
                v-for="key in trafficKnobKeys"
                :key="key"
                :label="settingLabel(key)"
                :value="settingValue(key)"
                :min="settingsByKey[key]?.min"
                :max="settingsByKey[key]?.max"
                :step="settingsByKey[key]?.step"
                :unit="settingsByKey[key]?.unit || ''"
                @update:value="v => setSetting(key, v)"
              />
            </div>
            <div class="pc-toggles">
              <button
                v-for="key in ['shadows','grid','buses']"
                :key="key"
                type="button"
                class="pc-toggle-card"
                :class="{ 'is-on': settingValue(key) }"
                @click="setSetting(key, !settingValue(key))"
              >
                <span>{{ settingLabel(key) }}</span>
                <small>{{ settingValue(key) ? 'включено' : 'выключено' }}</small>
              </button>
            </div>

            <h4 class="pc-group-title">Предустановки</h4>
            <div class="pc-presets">
              <q-input
                v-model="presetName"
                dense
                outlined
                class="pc-preset-name"
                placeholder="Имя пресета"
              />
              <q-select
                v-model="selectedPreset"
                :options="presetOptions"
                emit-value
                map-options
                dense
                outlined
                class="pc-select"
                placeholder="Выберите пресет"
              />
              <q-btn
                no-caps
                icon="save"
                label="Сохранить текущий"
                @click="saveCameraPreset"
              />
              <q-btn
                no-caps
                icon="check"
                label="Применить"
                :disable="!selectedPreset"
                @click="applyCameraPresetSaved"
              />
              <q-btn
                no-caps
                flat
                icon="delete"
                label="Удалить"
                :disable="!selectedPreset"
                @click="deleteCameraPreset"
              />
            </div>
          </div>

          <div v-else class="pc-section">
            <h3>Справочник API для ИИ-агентов</h3>
            <p>
              Формат сценария, словарь событий, справка по камере, погоде и
              праздникам, готовые примеры.
            </p>
            <q-btn
              no-caps
              color="amber"
              text-color="dark"
              label="Открыть документацию"
              @click="router.push('/administration/roadrunner?tab=docs')"
            />
          </div>
        </div>
      </section>

      <!-- Настройки AI и источников: собраны здесь, отдельный модуль удалён. -->
      <section v-if="view === 'ai'" class="panel ai-settings">
        <div class="panel-head">
          <h2>Настройки AI и источников</h2>
          <q-btn
            color="primary"
            no-caps
            dense
            label="Сохранить настройки"
            :loading="aiSaving"
            @click="saveAiSettings"
          />
        </div>

        <p v-if="aiError" class="error-text">{{ aiError }}</p>

        <div class="ai-grid">
          <div class="setting-item">
            <label>Провайдер погоды</label>
            <q-select
              v-model="aiSettings.weather_provider"
              :options="weatherProviderOptions"
              emit-value
              map-options
              dense
              outlined
            />
          </div>
          <div v-if="aiSettings.weather_provider !== 'open-meteo'" class="setting-item">
            <label>
              Ключ {{ aiSettings.weather_provider === 'gismeteo' ? 'Gismeteo' : 'Я.Погоды' }}
            </label>
            <q-input
              v-model="aiSettings[aiSettings.weather_provider === 'gismeteo' ? 'gismeteo_key' : 'yandex_weather_key']"
              type="password"
              dense
              outlined
              placeholder="GISMETEO_KEY / YANDEX_WEATHER_KEY"
            />
            <small class="hint">Без ключа используется Open-Meteo.</small>
          </div>
          <div class="setting-item">
            <label>Провайдер пробок</label>
            <q-select
              v-model="aiSettings.traffic_provider"
              :options="trafficProviderOptions"
              emit-value
              map-options
              dense
              outlined
            />
          </div>

          <div class="setting-item">
            <label>LLM-провайдер</label>
            <q-select
              v-model="aiSettings.llm_provider"
              :options="llmProviderOptions"
              emit-value
              map-options
              dense
              outlined
              @update:model-value="onLlmProviderChange"
            />
          </div>

          <template v-if="isOllama">
            <div class="setting-item">
              <label>Модель Ollama (установленная)</label>
              <q-select
                v-model="aiSettings.llm_model"
                :options="ollamaModels"
                dense
                outlined
                use-input
                hide-selected
                fill-input
                input-debounce="0"
                :loading="ollamaLoading"
                placeholder="выберите или введите модель"
                @filter="filterOllama"
              >
                <template #no-option>
                  <q-item><q-item-section>Моделей нет</q-item-section></q-item>
                </template>
              </q-select>
            </div>
          </template>

          <template v-else-if="isApiProvider">
            <div class="setting-item">
              <label>URL API</label>
              <q-input
                v-model="aiSettings.llm_url"
                dense
                outlined
                :placeholder="llmUrlPlaceholder"
              />
            </div>
            <div class="setting-item">
              <label>API Key</label>
              <q-input
                v-model="aiSettings.llm_api_key"
                type="password"
                dense
                outlined
              />
            </div>
          </template>

          <div class="setting-item">
            <label>Температура</label>
            <q-slider
              v-model.number="aiSettings.temperature"
              :min="0"
              :max="1"
              :step="0.05"
              dense
              color="primary"
            />
          </div>
          <div class="setting-item">
            <label>Максимум токенов</label>
            <q-input
              v-model.number="aiSettings.max_tokens"
              type="number"
              dense
              outlined
            />
          </div>
          <div class="setting-item">
            <label>Качество рендеринга</label>
            <q-select
              v-model="aiQuality"
              :options="settingsByKey.quality?.options || []"
              emit-value
              map-options
              dense
              outlined
              @update:model-value="v => setSetting('quality', v)"
            />
          </div>
          <div class="setting-item">
            <label>Сценарий по умолчанию</label>
            <q-select
              v-model="aiSettings.default_scenario"
              :options="scenarioOptions"
              emit-value
              map-options
              dense
              outlined
            />
          </div>
          <div class="setting-item">
            <label>
              Погода на баннере
              <q-toggle v-model="aiSettings.weather_enabled" color="primary" />
            </label>
            <label>
              Пробки на баннере
              <q-toggle v-model="aiSettings.traffic_enabled" color="primary" />
            </label>
          </div>
        </div>
      </section>

      <div class="banner-grid">
        <section v-if="view === 'banner'" class="panel settings-panel">
          <div class="panel-head">
            <h2>Настройки из кода</h2>
            <div class="panel-head-actions">
              <q-btn
                flat
                dense
                no-caps
                :icon="showAllSettings ? 'expand_less' : 'expand_more'"
                :label="showAllSettings ? 'Свернуть' : `Все параметры (${settings.length})`"
                @click="showAllSettings = !showAllSettings"
              />
              <q-btn
                flat
                dense
                no-caps
                icon="refresh"
                label="Перечитать"
                @click="parseSettings(code)"
              />
            </div>
          </div>

          <p v-if="settingsError" class="settings-error">
            {{ settingsError }}
          </p>

          <p v-else-if="!settings.length" class="hint">
            В коде нет блока настроек. Добавьте
            <code
              >&lt;script type="application/json" id="banner-settings"&gt;</code
            >
            — поля появятся здесь автоматически.
          </p>

          <div v-if="showAllSettings" class="all-settings-knobs">
            <SettingKnob
              v-for="item in settings.filter(s => s.type === 'number' && s.min !== undefined && s.max !== undefined)"
              :key="item.key"
              :label="item.label"
              :value="item.value"
              :min="item.min"
              :max="item.max"
              :step="item.step"
              :unit="item.unit || ''"
              @update:value="value => updateSetting(item, value)"
            />
          </div>

          <div v-if="showAllSettings" v-for="item in settings" :key="item.key" class="setting-row">
            <div class="setting-head">
              <span>
                {{ item.label }}
                <code class="setting-key">{{ item.key }}</code>
              </span>
              <b>{{ displayValue(item) }}{{ item.unit || '' }}</b>
            </div>

            <q-toggle
              v-if="item.type === 'boolean'"
              :model-value="Boolean(item.value)"
              color="primary"
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-select
              v-else-if="item.type === 'select'"
              :model-value="item.value"
              :options="item.options || []"
              emit-value
              map-options
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-input
              v-else-if="item.type === 'number'"
              :model-value="Number(item.value)"
              type="number"
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />

            <q-input
              v-else
              :model-value="String(item.value ?? '')"
              dense
              outlined
              @update:model-value="value => updateSetting(item, value)"
            />
          </div>
        </section>

        <section class="panel preview-panel">
          <div class="panel-head">
            <h2>Предпросмотр</h2>
            <span class="hint">изменения применяются сразу</span>
          </div>

          <div v-if="slide.has_code" class="preview-stage">
            <iframe
              :key="previewKey"
              :src="previewUrl"
              class="preview-frame"
              sandbox="allow-scripts"
              referrerpolicy="no-referrer"
              title="Предпросмотр баннера-дороги"
            ></iframe>
          </div>
          <p v-else class="hint">Код баннера пуст.</p>
        </section>
      </div>

      <section class="panel code-panel">
        <div class="panel-head">
          <h2>HTML-код баннера</h2>
          <span class="hint">
            настройки читаются из
            <code
              >&lt;script type="application/json" id="banner-settings"&gt;</code
            >
          </span>
        </div>

        <q-input
          v-model="code"
          type="textarea"
          outlined
          class="code-area"
          :input-style="{ fontFamily: 'monospace', fontSize: '12px' }"
        />
      </section>
    </template>
  </component>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'

import { adminRequest as request } from '../services/adminApi'
import SettingKnob from '../components/admin/SettingKnob.vue'
import { roadrunnerMode, modeFromCode } from '../composables/useRoadrunnerMode'

const props = defineProps({
  embedded: { type: Boolean, default: false },
  // 'banner' — редактор кода, 'projection' — вкладки настроек сцены,
  // 'ai' — настройки AI и источников.
  view: { type: String, default: 'banner' },
  activeProjectionTab: { type: String, default: 'camera' }
})

const router = useRouter()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const slide = ref(null)
const code = ref('')
const savedCode = ref('')
const settings = ref([])
const settingsError = ref('')
const previewKey = ref(0)

/* Панель проекции */
const projectionTab = ref(props.activeProjectionTab || 'camera')
watch(
  () => props.activeProjectionTab,
  value => {
    if (value) projectionTab.value = value
  }
)

const showAllSettings = ref(false)
const defaultValues = ref({})

const cameraPresetOptions = [
  { value: 'iso', label: 'Изометрия' },
  { value: 'platformer', label: 'Платформер' },
  { value: 'top', label: 'Сверху' },
  { value: 'front', label: 'Фронт' },
  { value: 'street', label: 'Угол улицы' },
  { value: 'stop', label: 'Остановка' }
]

const weatherPresetOptions = [
  { value: 'auto', label: 'Реальная' },
  { value: 'clear', label: 'Ясно' },
  { value: 'snow', label: 'Снег' },
  { value: 'rain', label: 'Дождь' },
  { value: 'storm', label: 'Гроза' },
  { value: 'night', label: 'Ночь' }
]

const holidayPresetOptions = [
  { value: 'none', label: 'Без праздника' },
  { value: 'new-year', label: 'Новый год' },
  { value: 'women-day', label: '8 Марта' },
  { value: 'victory-day', label: '9 Мая' },
  { value: 'russia-day', label: 'День России' },
  { value: 'custom', label: 'Свой набор' }
]

const cameraCards = [
  { value: 'iso', label: 'Изометрия', emoji: '📐', hint: 'az 32° · el 38°' },
  { value: 'platformer', label: 'Платформер', emoji: '🎮', hint: 'az 14° · el 0°' },
  { value: 'top', label: 'Сверху', emoji: '🗺️', hint: 'az 86° · el 0°' },
  { value: 'front', label: 'Фронт', emoji: '🎯', hint: 'az 26° · el 0°' },
  { value: 'street', label: 'Угол улицы', emoji: '📍', hint: 'az 30° · el 38°' },
  { value: 'stop', label: 'Остановка', emoji: '🚏', hint: 'az 24° · el 30°' }
]

const weatherCards = [
  { value: 'auto', label: 'Реальная', emoji: '🌐', hint: 'погода API' },
  { value: 'clear', label: 'Ясно', emoji: '☀️', hint: 'чистое небо' },
  { value: 'snow', label: 'Снег', emoji: '🌨️', hint: 'снег и мягкий свет' },
  { value: 'rain', label: 'Дождь', emoji: '🌧️', hint: 'ливень, мокрый асфальт' },
  { value: 'storm', label: 'Гроза', emoji: '⛈️', hint: 'дождь и молнии' },
  { value: 'night', label: 'Ночь', emoji: '🌙', hint: 'фонари и звёзды' }
]

const holidayCards = [
  { value: 'none', label: 'Без праздника', emoji: '✨', hint: 'чистый город' },
  { value: 'new-year', label: 'Новый год', emoji: '🎄', hint: 'ёлки, снег, гирлянды' },
  { value: 'women-day', label: '8 Марта', emoji: '🌷', hint: 'цветы и лепестки' },
  { value: 'victory-day', label: '9 Мая', emoji: '🎖️', hint: 'флаги и георгиевская лента' },
  { value: 'russia-day', label: 'День России', emoji: '🇷🇺', hint: 'триколор и гирлянды' },
  { value: 'custom', label: 'Свой набор', emoji: '🧰', hint: 'собрать вручную' }
]

const decorKeys = [
  'decoTrees', 'decoSnowfall', 'decoSnowman',
  'decoFlowers', 'decoFlags', 'decoGarlands', 'decoStars'
]

const trafficKnobKeys = [
  'flowDensity', 'trafficMin', 'trafficMax',
  'trafficChangeMin', 'trafficChangeMax',
  'carMin', 'carMax', 'pedMin', 'pedMax',
  'countChangeMin', 'countChangeMax'
]

/* Предустановки камеры и сцены. */
const cameraPresets = ref({})
const selectedPreset = ref('')
const presetName = ref('')
const presetOptions = computed(() =>
  Object.keys(cameraPresets.value).map(name => ({ label: name, value: name }))
)

const presetKeys = [
  'tilt', 'rotation', 'scale', 'quality', 'shadows', 'grid', 'buses',
  'speedFactor', 'flowDensity', 'speedWave', 'speedWavePeriod',
  'dayNightPeriod', 'trafficMin', 'trafficMax',
  'trafficChangeMin', 'trafficChangeMax', 'carMin', 'carMax',
  'pedMin', 'pedMax', 'countChangeMin', 'countChangeMax'
]

function currentPresetValues() {
  const values = {}
  presetKeys.forEach(key => {
    if (settingsByKey.value[key]) values[key] = settingValue(key)
  })
  return values
}

async function loadCameraPresets() {
  try {
    const data = await request('/api/roadrunner/camera-presets')
    cameraPresets.value = data.presets || {}
  } catch {
    cameraPresets.value = {}
  }
}

async function saveCameraPreset() {
  const name = String(presetName.value || '').trim()
  if (!name) {
    error.value = 'Введите имя предустановки'
    return
  }

  try {
    await request('/api/roadrunner/camera-presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name.trim(),
        settings: currentPresetValues()
      })
    })
    await loadCameraPresets()
    selectedPreset.value = name.trim()
  } catch (exc) {
    error.value = `Не удалось сохранить пресет: ${exc}`
  }
}

function applyCameraPresetSaved() {
  const values = cameraPresets.value[selectedPreset.value]
  if (!values) return
  Object.entries(values).forEach(([key, value]) => setSetting(key, value))
}

async function deleteCameraPreset() {
  if (!selectedPreset.value) return

  try {
    await request(
      `/api/roadrunner/camera-presets/${encodeURIComponent(selectedPreset.value)}`,
      { method: 'DELETE' }
    )
    selectedPreset.value = ''
    await loadCameraPresets()
  } catch (exc) {
    error.value = `Не удалось удалить пресет: ${exc}`
  }
}

/* Настройки AI и источников (бывший отдельный модуль «Настройки»). */
const aiSettings = ref({
  weather_provider: 'open-meteo',
  yandex_weather_key: '',
  gismeteo_key: '',
  traffic_provider: 'model',
  llm_provider: 'ollama',
  llm_model: 'qwen2.5:7b',
  llm_url: 'http://localhost:11434',
  llm_api_key: '',
  temperature: 0.35,
  max_tokens: 2048,
  default_scenario: 'rostov-evening-rain',
  weather_enabled: true,
  traffic_enabled: true
})

const weatherProviderOptions = [
  { label: 'Open-Meteo (без ключа)', value: 'open-meteo' },
  { label: 'Яндекс Погода', value: 'yandex' },
  { label: 'Gismeteo', value: 'gismeteo' }
]
const trafficProviderOptions = [
  { label: 'Модель (по часам пик)', value: 'model' },
  { label: 'Яндекс Пробки', value: 'yandex' }
]
const llmProviderOptions = [
  { label: 'Ollama (локальная)', value: 'ollama' },
  { label: 'YandexGPT Lite 8B', value: 'yandexgpt' },
  { label: 'OpenAI совместимый', value: 'openai' }
]
const scenarioOptions = [
  { label: 'Вечерний дождь (Ростов)', value: 'rostov-evening-rain' },
  { label: 'Новый год', value: 'new-year' },
  { label: 'День Победы', value: 'victory-day' },
  { label: 'День рождения Альбион', value: 'albion-birthday' }
]

const aiSaving = ref(false)
const aiError = ref('')
const ollamaLoading = ref(false)
const ollamaModels = ref([])

const isOllama = computed(() => aiSettings.value.llm_provider === 'ollama')
const isApiProvider = computed(() =>
  ['yandexgpt', 'openai'].includes(aiSettings.value.llm_provider)
)

const isCustom = computed(() => roadrunnerMode.value === 'custom')

function setMode(value) {
  setSetting('mode', value)
  roadrunnerMode.value = value

  if (value === 'default') {
    // Режим влияет только на погоду, праздники и сценарии. Камера, сцена,
    // скорость и поток не сбрасываются и остаются доступны в обоих режимах.
    const reset = {
      weatherPreset: 'auto',
      holidayPreset: 'none',
      precipitation: 0,
      lightning: 0,
      fog: 0,
      brightness: 1
    }

    decorKeys.forEach(key => { reset[key] = false })
    Object.entries(reset).forEach(([key, val]) => setSetting(key, val))
  }
}

const aiQuality = computed({
  get: () => settingValue('quality'),
  set: value => setSetting('quality', value)
})

const llmUrlPlaceholder = computed(() =>
  aiSettings.value.llm_provider === 'ollama'
    ? 'http://localhost:11434'
    : aiSettings.value.llm_provider === 'yandexgpt'
      ? 'https://llm.api.cloud.yandex.net/v1'
      : 'https://api.openai.com/v1'
)

async function loadAiSettings() {
  try {
    const data = await request('/api/roadrunner/settings')
    if (data.settings) {
      aiSettings.value = { ...aiSettings.value, ...data.settings }
    }
    if (isOllama.value && !aiSettings.value.llm_url) {
      aiSettings.value.llm_url = 'http://localhost:11434'
    }
    if (isOllama.value) await loadOllamaModels()
  } catch (exc) {
    aiError.value = `Не удалось загрузить настройки: ${exc}`
  }
}

async function loadOllamaModels() {
  ollamaLoading.value = true
  try {
    const data = await request('/api/roadrunner/ollama/models')
    ollamaModels.value = data.models || []
  } catch (exc) {
    aiError.value = `Ollama недоступен: ${exc}`
    ollamaModels.value = []
  } finally {
    ollamaLoading.value = false
  }
}

function filterOllama(value, done) {
  const list = ollamaModels.value
  done(() => {
    if (!value) return list
    const needle = String(value).toLowerCase()
    return list.filter(model => model.toLowerCase().includes(needle))
  })
}

function onLlmProviderChange(provider) {
  // URL API зависит от провайдера: у Ollama — локальный адрес, у облачных
  // провайдеров поле пустое и пользователь вписывает его сам.
  aiSettings.value.llm_url = provider === 'ollama'
    ? 'http://localhost:11434'
    : ''

  if (provider === 'ollama') loadOllamaModels()
}

async function saveAiSettings() {
  aiSaving.value = true
  aiError.value = ''
  try {
    await request('/api/roadrunner/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(aiSettings.value)
    })
  } catch (exc) {
    aiError.value = `Не удалось сохранить настройки: ${exc}`
  } finally {
    aiSaving.value = false
  }
}

const CAMERA_PRESETS = {
  iso: { tilt: 32, rotation: 38, scale: 1 },
  platformer: { tilt: 14, rotation: 0, scale: 1.05 },
  top: { tilt: 86, rotation: 0, scale: 0.85 },
  front: { tilt: 26, rotation: 0, scale: 1.15 },
  street: { tilt: 38, rotation: 62, scale: 1.05 },
  stop: { tilt: 30, rotation: -30, scale: 1.17 }
}

const WEATHER_PRESETS = {
  auto: {},
  clear: { precipitation: 0, wind: 0.25, lightning: 0, fog: 0, brightness: 1 },
  snow: { precipitation: 0.7, wind: 0.25, lightning: 0, fog: 0.1, brightness: 0.95 },
  rain: { precipitation: 0.65, wind: 0.4, lightning: 0, fog: 0.15, brightness: 0.9 },
  storm: { precipitation: 0.85, wind: 0.8, lightning: 1.2, fog: 0.3, brightness: 0.75 },
  night: { precipitation: 0, wind: 0.1, lightning: 0, fog: 0.1, brightness: 0.65 }
}

const HOLIDAY_PRESETS = {
  none: {},
  'new-year': { decoTrees: true, decoSnowfall: true, decoSnowman: true, decoGarlands: true, decoStars: true },
  'women-day': { decoFlowers: true, decoGarlands: true },
  'victory-day': { decoFlags: true },
  'russia-day': { decoFlags: true, decoGarlands: true },
  custom: {}
}

const SETTINGS_RE =
  /<script\b[^>]*\bid=["']banner-settings["'][^>]*>([\s\S]*?)<\/script>/i
const SETTINGS_BLOCK_RE =
  /(<script\b[^>]*\bid=["']banner-settings["'][^>]*>)([\s\S]*?)(<\/script>)/i

let syncing = false
let lastSyncedCode = ''
let parseTimer = null
let syncTimer = null

const dirty = computed(() => code.value !== savedCode.value)

const codeSize = computed(() => {
  const bytes = new TextEncoder().encode(code.value || '').length
  return `${(bytes / 1024).toFixed(1)} КБ`
})

const settingsStatus = computed(() => {
  if (settingsError.value) return 'настройки не прочитаны'
  return settings.value.length
    ? `${settings.value.length} настроек`
    : 'настроек нет'
})

const settingsByKey = computed(() =>
  Object.fromEntries(settings.value.map(item => [item.key, item]))
)

function settingValue(key) {
  return settingsByKey.value[key]?.value
}

function settingLabel(key) {
  return settingsByKey.value[key]?.label || key
}

function setSetting(key, value) {
  const item = settingsByKey.value[key]
  if (item) updateSetting(item, value)
}

function applyPreset(presetKey, values) {
  setSetting(presetKey, values.__preset)
  Object.entries(values).forEach(([key, value]) => {
    if (key !== '__preset' && settingsByKey.value[key]) setSetting(key, value)
  })
}

function applyCameraPreset(value) {
  applyPreset('cameraPreset', { __preset: value, ...CAMERA_PRESETS[value] })
}

function applyWeatherPreset(value) {
  applyPreset('weatherPreset', { __preset: value, ...WEATHER_PRESETS[value] })
}

function applyHolidayPreset(value) {
  const values = { __preset: value }
  decorKeys.forEach(key => { values[key] = false })
  Object.assign(values, HOLIDAY_PRESETS[value] || {})
  applyPreset('holidayPreset', values)
}

function togglePaused() {
  setSetting('paused', !settingValue('paused'))
}

function randomize() {
  settings.value.forEach(item => {
    if (item.type === 'boolean') {
      item.value = Math.random() > 0.5
    } else if (item.type === 'number' && item.min !== undefined) {
      const min = Number(item.min)
      const max = Number(item.max)
      const step = Number(item.step) || 1
      const raw = min + Math.random() * (max - min)
      item.value = Number((Math.round(raw / step) * step).toFixed(2))
    }
  })
  syncCodeFromSettings()
  schedulePreview()
}

function resetProjection() {
  settings.value.forEach(item => {
    // Режим «По умолчанию/Произвольный» не сбрасываем — он независим.
    if (item.key === 'mode') return
    if (Object.prototype.hasOwnProperty.call(defaultValues.value, item.key)) {
      item.value = defaultValues.value[item.key]
    }
  })
  syncCodeFromSettings()
  schedulePreview()
}

const previewUrl = computed(
  () => `/api/admin/home/slides/${slide.value.id}/code?v=${previewKey.value}`
)

/* Живой предпросмотр: несохранённый код уходит на сервер с задержкой,
   iframe перезагружается и показывает именно то, что редактируется.
   В БД слайда код попадает только по «Сохранить». */
let previewTimer = null

async function pushPreview() {
  if (!slide.value) return

  try {
    await request(`/api/admin/home/slides/${slide.value.id}/preview`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.value })
    })
  } catch {
    /* редактирование не должно блокироваться ошибкой предпросмотра */
  }

  previewKey.value += 1
}

function schedulePreview() {
  if (previewTimer) window.clearTimeout(previewTimer)
  previewTimer = window.setTimeout(pushPreview, 250)
}

watch(code, schedulePreview)

async function load() {
  loading.value = true
  error.value = ''

  try {
    const data = await request('/api/admin/home/slides')
    const found = (data.slides || []).find(s => s.kind === 'road-banner')

    if (!found) {
      slide.value = null
      return
    }

    slide.value = found
    code.value = found.code || ''
    savedCode.value = code.value
    parseSettings(code.value)
    roadrunnerMode.value = modeFromCode(code.value)
    defaultValues.value = Object.fromEntries(
      settings.value.map(item => [item.key, item.value])
    )
    schedulePreview()
  } catch (exc) {
    error.value = String(exc)
  } finally {
    loading.value = false
  }
}

function normalizeSetting(key, rawItem) {
  const descriptor =
    rawItem && typeof rawItem === 'object' && !Array.isArray(rawItem)
      ? { ...rawItem }
      : { value: rawItem }

  const value = descriptor.value
  const type =
    descriptor.type ||
    (typeof value === 'boolean'
      ? 'boolean'
      : Array.isArray(descriptor.options)
        ? 'select'
        : typeof value === 'number'
          ? 'number'
          : 'string')

  return {
    ...descriptor,
    key,
    label: descriptor.label || key,
    type,
    value
  }
}

function parseSettings(text) {
  settingsError.value = ''

  const match = String(text || '').match(SETTINGS_RE)

  if (!match) {
    settings.value = []
    settingsError.value =
      'Блок настроек не найден: нужен ' +
      '<script type="application/json" id="banner-settings">…' +
      '</' +
      'script>.'
    return
  }

  try {
    const raw = JSON.parse(match[1])
    settings.value = Object.entries(raw).map(([key, item]) =>
      normalizeSetting(key, item)
    )
  } catch (exc) {
    settings.value = []
    settingsError.value = `JSON настроек не разбирается: ${exc.message}`
  }
}

function settingsPayload() {
  const raw = {}

  settings.value.forEach(item => {
    const descriptor = { ...item }
    delete descriptor.key
    raw[item.key] = descriptor
  })

  return raw
}

function syncCodeFromSettings() {
  if (!settings.value.length) return
  if (!SETTINGS_BLOCK_RE.test(code.value)) return

  const json = JSON.stringify(settingsPayload(), null, 2)

  syncing = true

  try {
    code.value = code.value.replace(
      SETTINGS_BLOCK_RE,
      (match, open, body, close) => `${open}\n${json}\n${close}`
    )
    lastSyncedCode = code.value
  } finally {
    syncing = false
  }
}

function updateSetting(item, value) {
  if (item.type === 'number') {
    const number = Number(value)
    if (Number.isFinite(number)) value = number
  }

  item.value = value

  if (syncTimer) window.clearTimeout(syncTimer)
  syncTimer = window.setTimeout(syncCodeFromSettings, 120)
}

watch(code, value => {
  roadrunnerMode.value = modeFromCode(value)

  if (syncing || value === lastSyncedCode) return

  if (parseTimer) window.clearTimeout(parseTimer)
  parseTimer = window.setTimeout(() => parseSettings(value), 350)
})

function displayValue(item) {
  if (item.type === 'number') {
    const number = Number(item.value)
    return Number.isFinite(number)
      ? String(Math.round(number * 100) / 100)
      : '—'
  }

  if (item.type === 'boolean') return item.value ? 'вкл' : 'выкл'

  if (item.type === 'select') {
    const option = (item.options || []).find(candidate =>
      candidate && typeof candidate === 'object'
        ? candidate.value === item.value
        : candidate === item.value
    )

    if (option && typeof option === 'object') return option.label
  }

  return String(item.value ?? '')
}

async function downloadPdf() {
  try {
    const response = await fetch('/api/roadrunner/api-documentation.pdf')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'roadrunner-api.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (exc) {
    error.value = `Не удалось скачать PDF: ${exc}`
  }
}

async function save() {
  if (!slide.value) return

  saving.value = true
  error.value = ''

  try {
    const data = await request(`/api/admin/home/slides/${slide.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code.value })
    })

    const updated = (data.slides || []).find(s => s.id === slide.value.id)

    if (updated) slide.value = updated

    savedCode.value = code.value
    previewKey.value += 1
  } catch (exc) {
    error.value = String(exc)
  } finally {
    saving.value = false
  }
}

function restartPreview() {
  pushPreview()
}

function onFile(event) {
  const file = event.target.files && event.target.files[0]
  if (!file) return

  if (file.size > 512 * 1024) {
    error.value = `Файл больше 512 КБ: ${file.name}`
    event.target.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    code.value = String(reader.result || '')
    lastSyncedCode = ''
    parseSettings(code.value)
    error.value = ''
  }
  reader.onerror = () => {
    error.value = `Не удалось прочитать файл: ${file.name}`
  }
  reader.readAsText(file)
  event.target.value = ''
}

function download() {
  const blob = new Blob([code.value], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'road-banner.html'
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function resetCode() {
  if (!window.confirm('Заменить текущий код стандартным баннером?')) return

  try {
    const data = await request('/api/admin/home/banner-default')
    code.value = data.code || ''
    lastSyncedCode = ''
    parseSettings(code.value)
    error.value = ''
  } catch (exc) {
    error.value = String(exc)
  }
}

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return window.confirm('Есть несохранённые изменения. Уйти без сохранения?')
})

onMounted(() => {
  load()
  loadAiSettings()
  loadCameraPresets()
})

onBeforeUnmount(() => {
  if (parseTimer) window.clearTimeout(parseTimer)
  if (syncTimer) window.clearTimeout(syncTimer)
  if (previewTimer) window.clearTimeout(previewTimer)
})
</script>

<style scoped>
.admin-banner {
  max-width: 1500px;
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
  margin-bottom: 6px;
  color: #94a3b8;
  font-size: 12px;
  letter-spacing: 0.12em;
}

h1 {
  margin: 0 0 6px;
  font-size: 26px;
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
  padding: 10px 14px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
}

.empty-text {
  padding: 24px;
  color: #64748b;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.hint {
  color: #64748b;
  font-size: 13px;
}

.dirty {
  color: #b45309;
  font-size: 12px;
}

.file-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 7px 14px;
  overflow: hidden;
  border-radius: 6px;
  background: #1d4ed8;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.file-btn input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.banner-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) 1.1fr;
  gap: 16px;
}

.panel {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.settings-panel {
  max-height: 520px;
  overflow-y: auto;
}

.settings-error {
  margin: 0;
  color: #b91c1c;
  font-size: 13px;
}

.setting-row {
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
}

.setting-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
  color: #334155;
  font-size: 13px;
}

.setting-head b {
  color: #0f172a;
  white-space: nowrap;
}

.setting-key {
  display: inline-block;
  margin-left: 6px;
  color: #94a3b8;
  font-size: 11px;
}

.preview-frame {
  display: block;
  width: 100%;
  /* Та же доля экрана, что и у баннера на главной. */
  height: 50vh;
  min-height: 200px;
  border: 0;
  border-radius: 0;
  background: #9fd4ec;
  pointer-events: none;
}

/* Такой же верхний градиент, как у баннера на слайде. */
.preview-stage {
  position: relative;
  overflow: hidden;
}

.preview-stage::after {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  z-index: 1;
  height: clamp(20px, 3.5vh, 38px);
  background: linear-gradient(
    180deg,
    rgba(20, 24, 29, 0.58),
    rgba(20, 24, 29, 0)
  );
  pointer-events: none;
}

.code-panel {
  margin-top: 16px;
}

.code-area :deep(textarea) {
  min-height: 360px;
  max-height: 70vh;
  white-space: pre;
  overflow: auto;
}

/* --- Панель проекции (стиль демо-сцены) --- */
.projection-console {
  margin-bottom: 16px;
  overflow: hidden;
  border: 1px solid #1e293b;
  border-radius: 12px;
  background: #0d1420;
  color: #e2e8f0;
}

.pc-topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #1e293b;
  background: #111b2b;
}

.pc-mode {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 0 0 auto;
  margin-right: 6px;
  padding-right: 12px;
  border-right: 1px solid #e2e8f0;
}

.pc-mode-label {
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.pc-mode-scoped {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pc-topbar-controls {
  display: flex;
  flex: 1 1 auto;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.pc-disabled {
  opacity: 0.5;
  pointer-events: none;
  filter: grayscale(0.4);
}

.pc-mode-hint {
  padding: 9px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: #fffbeb;
  color: #92400e;
  font-size: 12.5px;
}

.pc-play {
  min-width: 96px;
  background: linear-gradient(90deg, #f5b301, #38bdf8);
  color: #0b1220;
  font-weight: 800;
}

.pc-slider {
  flex: 1 1 190px;
  min-width: 150px;
}

.pc-label {
  display: block;
  margin-bottom: 4px;
  color: #8fa3bd;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.pc-label b {
  color: #f5b301;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
}

.pc-select {
  width: 170px;
  flex: 0 0 170px;
}

.pc-action {
  border: 1px solid #334155;
  background: #162337;
  color: #e2e8f0;
}

.pc-tabs {
  background: #0d1420;
  color: #94a3b8;
  border-bottom: 1px solid #1e293b;
}

.pc-body {
  padding: 18px 20px 22px;
}

.pc-section h3 {
  margin: 0 0 6px;
  color: #f8fafc;
  font-size: 22px;
  font-weight: 800;
}

.pc-section h3::after {
  content: '';
  display: block;
  width: 44px;
  height: 3px;
  margin-top: 8px;
  border-radius: 3px;
  background: linear-gradient(90deg, #f5b301, #38bdf8);
}

.pc-section p {
  margin: 12px 0 18px;
  max-width: 900px;
  color: #8fa3bd;
  font-size: 13px;
  line-height: 1.6;
}

.pc-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.pc-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-height: 96px;
  padding: 12px 8px;
  border: 1px solid #334155;
  border-radius: 10px;
  background: #111d2e;
  color: #e2e8f0;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.pc-card:hover {
  border-color: #64748b;
}

.pc-card.is-active {
  border-color: #f5b301;
  background: #17253a;
  box-shadow: inset 0 0 0 1px rgba(245, 179, 1, 0.35);
}

.pc-card-icon {
  font-size: 26px;
  line-height: 1;
}

.pc-card b {
  font-size: 13px;
}

.pc-card small {
  color: #8fa3bd;
  font-size: 11px;
  text-align: center;
}

.pc-sliders {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 12px 20px;
  padding: 14px 16px;
  border: 1px solid #1e293b;
  border-radius: 10px;
  background: #101a29;
}

.pc-preset-name {
  width: 180px;
}

.pc-presets {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.pc-toggles {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.pc-toggle-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid #334155;
  border-radius: 9px;
  background: #111d2e;
  color: #e2e8f0;
  text-align: left;
  cursor: pointer;
}

.pc-toggle-card.is-on {
  border-color: #f5b301;
  background: #1b2a40;
}

.pc-toggle-card span {
  font-size: 13px;
  font-weight: 600;
}

.pc-toggle-card small {
  color: #8fa3bd;
  font-size: 11px;
}

/* Панель проекции на обычном светлом фоне, как остальная админка. */
.projection-console {
  border-color: #e2e8f0;
  background: #fff;
  color: #0f172a;
}

.pc-topbar {
  border-color: #e2e8f0;
  background: #f8fafc;
}

.pc-label,
.pc-card small,
.pc-toggle-card small,
.pc-section p {
  color: #64748b;
}

.pc-section h3 {
  color: #0f172a;
}

.pc-card,
.pc-toggle-card {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #0f172a;
}

.pc-card.is-active,
.pc-toggle-card.is-on {
  border-color: #f5b301;
  background: #fffbeb;
  box-shadow: none;
}

.pc-tabs,
.pc-sliders {
  border-color: #e2e8f0;
  background: #fff;
}

.pc-select :deep(.q-field__control),
.pc-action {
  border-color: #cbd5e1;
  background: #fff;
  color: #0f172a;
}

.pc-action {
  border: 1px solid #cbd5e1;
}

.pc-group-title {
  margin: 16px 0 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.pc-split {
  display: flex;
  align-items: flex-start;
  gap: 18px;
}

.pc-group {
  flex: 1 1 0;
  min-width: 0;
}

.pc-divider {
  flex: 0 0 1px;
  align-self: stretch;
  background: #e2e8f0;
}

.pc-knobs,
.all-settings-knobs {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px 6px;
}

.all-settings-knobs {
  padding: 8px 0 14px;
  border-bottom: 1px solid #f1f5f9;
}

.panel-head-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.ai-settings {
  margin-bottom: 16px;
}

.ai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px 20px;
}

.ai-grid .setting-item label {
  display: block;
  margin-bottom: 6px;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

/* Предпросмотр — от края до края страницы. */
.banner-grid {
  display: block;
}

.preview-panel {
  width: 100vw;
  max-width: none;
  margin: 16px calc(50% - 50vw) 0;
  border-radius: 0;
  border-left: 0;
  border-right: 0;
}

@media (max-width: 900px) {
  .admin-banner {
    padding: 20px 16px;
  }

  .page-header {
    flex-direction: column;
  }

  .banner-grid {
    grid-template-columns: 1fr;
  }

  .settings-panel {
    max-height: none;
  }
}
</style>
