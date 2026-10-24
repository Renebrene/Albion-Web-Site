<template>
  <div class="chat-save" :class="{ 'is-compact': compact }">
    <!--
      Сохранение чатов живёт в личном кабинете: пока он скрыт флагом
      ACCOUNT_UI_ENABLED, кнопка вела бы в тупик («Зайдите в личный
      кабинет», а вход недоступен). Портфель прячет свой блок так же.
    -->
    <q-btn
      v-if="ACCOUNT_UI_ENABLED"
      flat
      dense
      no-caps
      icon="save"
      :label="compact ? undefined : 'Сохранить'"
      :loading="saving"
      :disable="!chats.length"
      :title="compact ? 'Сохранить чаты' : undefined"
      @click="onClick"
    />

    <!-- Очистка чатов: после нажатия идёт таймер, повторное нажатие отменяет. -->
    <q-btn
      flat
      dense
      no-caps
      :icon="clearArmed ? 'delete_forever' : 'delete_outline'"
      :label="clearLabel"
      :color="clearArmed ? 'negative' : undefined"
      :disable="!chats.length && !clearArmed"
      :title="compact && !clearArmed ? 'Очистить чаты' : undefined"
      @click="toggleClear"
    />

    <!-- Тултип без авторизации: появляется по клику и гаснет сам. -->
    <transition name="chat-save-fade">
      <span v-if="ACCOUNT_UI_ENABLED && tip" class="chat-save-tip">
        Зайдите в личный кабинет
      </span>
    </transition>

    <span v-if="clearArmed" class="chat-save-hint is-warn">
      Нажмите ещё раз, чтобы отменить
    </span>

    <span
      v-else-if="ACCOUNT_UI_ENABLED && !tip && savedAt"
      class="chat-save-hint"
    >
      Сохранено в {{ savedAt }}
    </span>

    <span v-if="saveError" class="chat-save-error">{{ saveError }}</span>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

import { ACCOUNT_UI_ENABLED } from '../../config/features'
import { useChatWorkspace } from '../../composables/useChatWorkspace'

const props = defineProps({
  /* Компактный вид (маленькое окно): только иконка. */
  compact: {
    type: Boolean,
    default: false
  }
})

const {
  chats,
  isAuthenticated,
  saveChats,
  saving,
  savedAt,
  saveError,
  toggleClear,
  clearArmed,
  clearSeconds
} = useChatWorkspace()

const tip = ref(false)
let timer = null

/* Пока идёт таймер — подпись «Чаты будут удалены» с обратным отсчётом. */
const clearLabel = computed(() => {
  if (clearArmed.value) {
    return `Чаты будут удалены (${clearSeconds.value})`
  }

  return props.compact ? undefined : 'Очистить'
})

/*
 * Без авторизации кнопка не сохраняет, а показывает тултип
 * «Зайдите в личный кабинет».
 */
async function onClick() {
  if (!isAuthenticated.value) {
    tip.value = true
    clearTimeout(timer)
    timer = setTimeout(() => {
      tip.value = false
    }, 2600)
    return
  }

  tip.value = false
  await saveChats()
}

onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.chat-save {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.chat-save-tip {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 20;
  padding: 5px 9px;
  border-radius: 6px;
  background: #17212b;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
  box-shadow: 0 6px 18px rgba(23, 33, 43, 0.24);
}
/* В компактном окне тултип прижат вправо, чтобы не вылезать за меню. */
.chat-save.is-compact .chat-save-tip {
  left: auto;
  right: 0;
}
.chat-save-hint {
  color: #2e7d32;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
/* Подсказка во время отсчёта удаления. */
.chat-save-hint.is-warn {
  color: #c62828;
}
.chat-save-error {
  color: #c62828;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.chat-save-fade-enter-active,
.chat-save-fade-leave-active {
  transition: opacity 0.15s ease;
}
.chat-save-fade-enter-from,
.chat-save-fade-leave-to {
  opacity: 0;
}
</style>
