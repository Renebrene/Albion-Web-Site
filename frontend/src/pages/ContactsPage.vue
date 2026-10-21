<template>
  <q-page class="contacts-page">
    <h1 class="sr-only">Контакты</h1>

    <div v-if="loading" class="contacts-state" role="status">
      Загрузка контактов…
    </div>

    <div
      v-else-if="loadError"
      class="contacts-state contacts-state--error"
      role="alert"
    >
      <p>{{ loadError }}</p>
      <button type="button" class="contacts-retry" @click="reloadContacts">
        Повторить
      </button>
    </div>

    <div
      v-else-if="!activeOffices.length && !activeDepartments.length"
      class="contacts-state"
    >
      <p
        >Контакты временно недоступны. Позвоните нам по телефону из шапки
        сайта.</p
      >
    </div>

    <template v-else>
      <ContactsOffices :offices="activeOffices" />
      <ContactsEmployees :departments="activeDepartments" />
    </template>
  </q-page>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { getContacts } from '@/services/api'

import ContactsOffices from '@/components/contacts/ContactsOffices.vue'
import ContactsEmployees from '@/components/contacts/ContactsEmployees.vue'

const contacts = ref({
  offices: [],
  departments: []
})
const loading = ref(true)
const loadError = ref('')
let contactsRequest = 0
let isUnmounted = false

async function reloadContacts() {
  const request = ++contactsRequest
  loading.value = true
  loadError.value = ''

  try {
    const data = await getContacts()

    if (isUnmounted || request !== contactsRequest) {
      return
    }

    if (!data || typeof data !== 'object') {
      throw new Error('Некорректный ответ /api/contacts')
    }

    contacts.value = data
  } catch (error) {
    if (isUnmounted || request !== contactsRequest) {
      return
    }

    contacts.value = { offices: [], departments: [] }
    loadError.value =
      'Не удалось загрузить контакты. Проверьте соединение и повторите.'
    console.error('Не удалось загрузить контакты:', error)
  } finally {
    if (!isUnmounted && request === contactsRequest) {
      loading.value = false
    }
  }
}

onMounted(reloadContacts)

onBeforeUnmount(() => {
  isUnmounted = true
  contactsRequest += 1
})

const activeOffices = computed(() =>
  (contacts.value.offices || [])
    .filter(item => item.active !== false)
    .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0))
)

const activeDepartments = computed(() =>
  (contacts.value.departments || [])
    .filter(item => item.active !== false)
    .map(department => ({
      ...department,
      employees: (department.employees || [])
        .filter(employee => employee.active !== false)
        .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0))
    }))
    .sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0))
)
</script>

<style scoped>
.contacts-page {
  background: #f4f6f7;
  color: #17212b;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.contacts-state {
  max-width: 720px;
  margin: 0 auto;
  padding: 90px 24px;
  color: #52606a;
  font-size: 15px;
  text-align: center;
}

.contacts-state--error {
  color: #8f1d16;
}

.contacts-retry {
  margin-top: 14px;
  padding: 10px 18px;
  border: 1px solid var(--albion-accent, #e12a1f);
  border-radius: 8px;
  background: var(--albion-accent, #e12a1f);
  color: #fff;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}
</style>
