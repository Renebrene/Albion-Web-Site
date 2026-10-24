<template>
  <q-dialog v-model="open" @show="onShow">
    <q-card class="cmp-card">
      <q-card-section class="cmp-head">
        <div class="cmp-head-text">
          <div class="cmp-title">Каталог превью конструкций</div>
          <div class="cmp-note">
            Замена фото сохраняется во временный каталог и действует на всём
            сайте до следующего обновления базы.
          </div>
        </div>
        <q-btn
          flat
          round
          dense
          icon="close"
          aria-label="Закрыть"
          @click="open = false"
        />
      </q-card-section>

      <q-card-section class="cmp-filters">
        <q-input
          v-model="search"
          outlined
          dense
          clearable
          autofocus
          label="Поиск"
          placeholder="Адрес или город"
        >
          <template #prepend>
            <q-icon name="search" />
          </template>
        </q-input>
      </q-card-section>

      <q-separator />

      <q-card-section class="cmp-body">
        <div v-if="loading" class="cmp-state">
          <q-spinner size="24px" />
          <span>Загрузка…</span>
        </div>

        <div v-else-if="error" class="cmp-state cmp-state--error">
          {{ error }}
        </div>

        <div v-else-if="!filtered.length" class="cmp-state">
          Ничего не найдено.
        </div>

        <div v-else class="cmp-grid">
          <button
            v-for="item in filtered"
            :key="item.id"
            type="button"
            class="cmp-item"
            :class="{ 'is-selected': item.id === selectedId }"
            @click="selectedId = item.id"
            @dblclick="confirm(item)"
          >
            <div class="cmp-thumb">
              <img :src="item.thumb" :alt="item.label" loading="lazy" />
            </div>
            <div class="cmp-name" :title="item.label">{{ item.label }}</div>
          </button>
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn flat no-caps label="Отмена" @click="open = false" />
        <q-btn
          unelevated
          no-caps
          color="primary"
          label="Выбрать"
          :disable="!selected"
          @click="confirm(selected)"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { fetchConstructionPreviews } from '../../services/constructionMedia'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'select'])

const open = ref(props.modelValue)
const items = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const selectedId = ref(null)

/* Поколение загрузки: повторное открытие не должно гоняться со старым ответом. */
let loadSeq = 0

watch(
  () => props.modelValue,
  value => {
    open.value = value
  }
)

watch(open, value => {
  emit('update:modelValue', value)
})

const filtered = computed(() => {
  const query = search.value.trim().toLowerCase()

  if (!query) {
    return items.value
  }

  return items.value.filter(item => item.label.toLowerCase().includes(query))
})

const selected = computed(
  () => items.value.find(item => item.id === selectedId.value) || null
)

async function onShow() {
  const seq = ++loadSeq

  /* Каждый показ — с чистым выбором и свежим каталогом: фото могли
     переопределить с прошлого открытия. */
  selectedId.value = null
  loading.value = true
  error.value = ''

  try {
    const previews = await fetchConstructionPreviews()

    if (seq !== loadSeq) {
      return
    }

    items.value = previews
  } catch (exc) {
    if (seq !== loadSeq) {
      return
    }

    error.value = String(exc?.message || exc)
  } finally {
    if (seq === loadSeq) {
      loading.value = false
    }
  }
}

function confirm(item) {
  if (!item) return

  emit('select', { url: item.url, surface_hash: item.surface_hash })
  open.value = false
}
</script>

<style scoped>
.cmp-card {
  width: min(900px, 94vw);
  max-width: 900px;
}

.cmp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 4px;
}

.cmp-title {
  font-size: 18px;
  font-weight: 800;
}

.cmp-note {
  margin-top: 6px;
  max-width: 640px;
  color: #8a5a00;
  font-size: 12px;
  line-height: 1.45;
}

.cmp-filters {
  padding-top: 4px;
}

.cmp-body {
  max-height: 58vh;
  min-height: 220px;
  overflow-y: auto;
}

.cmp-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 48px 16px;
  color: #6b7280;
}

.cmp-state--error {
  color: #c62828;
}

.cmp-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.cmp-item {
  display: block;
  padding: 8px;
  border: 1px solid #e4e6ea;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.cmp-item:hover {
  border-color: #b9c0c8;
}

.cmp-item.is-selected {
  border-color: var(--q-primary);
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.06);
}

.cmp-thumb {
  width: 100%;
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border-radius: 7px;
  background: #f3f5f6;
}

.cmp-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.cmp-name {
  margin-top: 7px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: #37474f;
}

@media (max-width: 700px) {
  .cmp-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
