<template>
  <div class="media-source-buttons">
    <q-btn
      outline
      no-caps
      icon="photo_library"
      label="Медиатека"
      :dense="dense"
      :disable="disabled || uploading"
      @click="pickerOpen = true"
    />

    <!-- label[for] открывает системное окно выбора файла без programmatic click() -->
    <label
      class="msb-upload-btn"
      :class="{ 'msb-upload-btn--disabled': disabled || uploading }"
      :for="fileInputId"
    >
      <q-icon name="upload" size="18px" class="q-mr-xs" />
      {{ uploading ? 'Загрузка…' : 'Загрузить' }}
    </label>

    <input
      :id="fileInputId"
      ref="fileInput"
      type="file"
      :accept="accept"
      class="msb-file-input"
      :disabled="disabled || uploading"
      @change="onFilesPicked"
    />

    <MediaPicker v-model="pickerOpen" @select="onPicked" />
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { uploadAdminMedia } from '../../services/adminMedia'
import MediaPicker from './MediaPicker.vue'

const props = defineProps({
  /* Формат файла для системного окна (image/*, документы и т.п.). */
  accept: { type: String, default: 'image/*' },
  /* Категория(и) медиатеки для загружаемого файла. */
  categoryId: { type: [Number, String, Array], default: null },
  disabled: { type: Boolean, default: false },
  dense: { type: Boolean, default: false }
})

const emit = defineEmits(['pick', 'notify'])

const pickerOpen = ref(false)
const uploading = ref(false)

const fileInputId = `media-source-upload-${Date.now()}-${Math.floor(
  Math.random() * 1e6
)}`

/* Выбор из медиатеки (одиночный режим). */
function onPicked(media) {
  const storagePath = media?.storage_path || ''

  emit('pick', {
    id: media?.id ?? null,
    url: media?.url || (storagePath ? `/storage/${storagePath}` : ''),
    storage_path: storagePath,
    original_name: media?.name || media?.original_name || '',
    media
  })
}

/* Загрузка с компьютера: файл уходит в медиатеку, затем подставляется. */
function onFilesPicked(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''

  const file = files.find(item => item instanceof File)

  if (file) uploadFile(file)
}

async function uploadFile(file) {
  uploading.value = true

  try {
    const media = await uploadAdminMedia(file, { categoryId: props.categoryId })

    emit('pick', {
      id: media.id,
      url: media.url,
      storage_path: media.storage_path,
      original_name: media.original_name,
      media
    })

    emit('notify', 'Файл загружен')
  } catch (exc) {
    emit('notify', String(exc?.message || exc), 'error')
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.media-source-buttons {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.msb-upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 6px;
  border: 1px solid var(--q-primary);
  color: var(--q-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
}

.msb-upload-btn:hover {
  background: rgba(0, 0, 0, 0.03);
}

.msb-upload-btn--disabled {
  opacity: 0.5;
  pointer-events: none;
}

.msb-file-input {
  position: absolute;
  left: -9999px;
  top: -9999px;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
}
</style>
