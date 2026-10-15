<template>
  <q-page class="contacts-page">
    <ContactsOffices :offices="activeOffices" />

    <ContactsEmployees :departments="activeDepartments" />

    <!-- Заявка без личного кабинета (см. doc/account-cabinet.md). -->
    <ContactsRequestForm />
  </q-page>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { getContacts } from '@/services/api'

import ContactsOffices from '@/components/contacts/ContactsOffices.vue'
import ContactsEmployees from '@/components/contacts/ContactsEmployees.vue'
import ContactsRequestForm from '@/components/contacts/ContactsRequestForm.vue'

const contacts = ref({
  offices: [],
  departments: []
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
</script>

<style scoped>
.contacts-page {
  background: #f4f6f7;
  color: #17212b;
}
</style>
