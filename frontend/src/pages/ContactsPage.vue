<template>
  <q-page class="contacts-page">
    <ContactsHero :data="contacts.hero" />

    <ContactsOffices
      :offices="activeOffices"
      :phone="contacts.general?.phone"
      @show-map="showOffice"
    />

    <ContactsEmployees
      :departments="activeDepartments"
    />

    <ContactsCallback
      :data="contacts.callback"
      :phone="contacts.general?.phone"
    />
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { getContacts } from '@/services/api'

import ContactsHero from '@/components/contacts/ContactsHero.vue'
import ContactsOffices from '@/components/contacts/ContactsOffices.vue'
import ContactsEmployees from '@/components/contacts/ContactsEmployees.vue'
import ContactsCallback from '@/components/contacts/ContactsCallback.vue'

const contacts = ref({
  general: {},
  hero: {},
  offices: [],
  departments: [],
  callback: {}
})

onMounted(async () => {
  try {
    const data = await getContacts()

    if (data && typeof data === 'object') {
      contacts.value = data
    }
  } catch (error) {
    console.error('Не удалось загрузить контакты:', error)
  }
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

function showOffice(office) {
  if (!office?.address) {
    return
  }

  const query = encodeURIComponent(office.address)

  window.open(
    `https://www.google.com/maps/search/?api=1&query=${query}`,
    '_blank',
    'noopener'
  )
}
</script>

<style scoped>
.contacts-page {
  background: #f4f6f7;
  color: #17212b;
}
</style>
