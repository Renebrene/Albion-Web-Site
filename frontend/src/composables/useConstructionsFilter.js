import { computed, ref, watch } from 'vue'
import { isFree } from '../utils/availability'

const MONTH_ORDER = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь'
]

const MONTH_SHORT = {
  Январь: 'янв.',
  Февраль: 'февр.',
  Март: 'март',
  Апрель: 'апр.',
  Май: 'май',
  Июнь: 'июнь',
  Июль: 'июль',
  Август: 'авг.',
  Сентябрь: 'сент.',
  Октябрь: 'окт.',
  Ноябрь: 'нояб.',
  Декабрь: 'дек.'
}

function normalize(value) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
}

function formatMonth(month) {
  const year = new Date().getFullYear()
  return `${MONTH_SHORT[month] || month} ${year}`
}

export function useConstructionsFilter(constructions) {
  const selectedMonths = ref([])
  const monthLogic = ref('OR')
  const selectedTypes = ref([])
  const selectedCities = ref([])
  const searchQuery = ref('')

  // Фильтры должны автоматически выбрать всё
  // только после фактической загрузки данных.
  // Месяцы по умолчанию СНЯТЫ (без фильтра по свободности).
  let typesInitialized = false
  let citiesInitialized = false

  /*
   * Месяцы берём непосредственно из данных.
   * Никакого жёсткого списка месяцев для фильтрации.
   */
  const months = computed(() => {
    const found = new Set()

    for (const item of constructions.value || []) {
      for (const month of Object.keys(item?.statuses || {})) {
        found.add(month)
      }

      for (const month of Object.keys(item?.months || {})) {
        found.add(month)
      }
    }

    return [...found]
      .sort((a, b) => {
        const ia = MONTH_ORDER.indexOf(a)
        const ib = MONTH_ORDER.indexOf(b)

        if (ia === -1 && ib === -1) return a.localeCompare(b)
        if (ia === -1) return 1
        if (ib === -1) return -1

        return ia - ib
      })
      .map(month => ({
        value: month,
        label: formatMonth(month)
      }))
  })

  const types = computed(() => {
    const values = new Set()

    for (const item of constructions.value || []) {
      if (item?.type) {
        values.add(String(item.type).trim())
      }
    }

    return [...values].sort((a, b) => a.localeCompare(b, 'ru'))
  })

  const cities = computed(() => {
    const values = new Set()

    for (const item of constructions.value || []) {
      const city = String(item?.city || '').trim()

      if (city) {
        values.add(city)
      }
    }

    return [...values].sort((a, b) => {
      const rostov = 'Ростов-на-Дону'

      if (a === rostov && b !== rostov) return -1
      if (b === rostov && a !== rostov) return 1

      return a.localeCompare(b, 'ru')
    })
  })

  // После загрузки данных один раз выбираем ВСЕ значения форматов и
  // городов; месяцы остаются снятыми (фильтр по свободности не активен).

  watch(
    types,
    values => {
      if (!typesInitialized && values.length) {
        selectedTypes.value = [...values]
        typesInitialized = true
      }
    },
    { immediate: true }
  )

  watch(
    cities,
    values => {
      if (!citiesInitialized && values.length) {
        selectedCities.value = [...values]
        citiesInitialized = true
      }
    },
    { immediate: true }
  )

  const filteredConstructions = computed(() => {
    const query = normalize(searchQuery.value)

    const result = (constructions.value || []).filter(item => {
      /*
       * МЕСЯЦЫ
       *
       * Внутри группы месяцев работает переключатель:
       *
       * AND / И  → свободно во ВСЕ выбранные месяцы
       * OR  / ИЛИ → свободно хотя бы в ОДНОМ выбранном месяце
       *
       * Все остальные группы фильтров работают через И.
       */
      if (selectedMonths.value.length) {
        const monthsMatch = monthLogic.value === 'AND'
          ? selectedMonths.value.every(month => isFree(item, month))
          : selectedMonths.value.some(month => isFree(item, month))

        if (!monthsMatch) {
          return false
        }
      }

      /*
       * ФОРМАТ
       */
      if (
        selectedTypes.value.length &&
        !selectedTypes.value.includes(String(item?.type || '').trim())
      ) {
        return false
      }

      /*
       * ГОРОД
       */
      if (
        selectedCities.value.length &&
        !selectedCities.value.includes(String(item?.city || '').trim())
      ) {
        return false
      }

      /*
       * ПОИСК
       */
      if (query) {
        const haystack = [
          item?.city,
          item?.district,
          item?.name,
          item?.address,
          item?.side,
          item?.type,
          item?.number
        ]
          .map(normalize)
          .join(' ')

        if (!haystack.includes(query)) {
          return false
        }
      }

      return true
    })

    return result
  })

  function resetFilters() {
    selectedMonths.value = []
    monthLogic.value = 'OR'
    selectedTypes.value = [...types.value]
    selectedCities.value = [...cities.value]
    searchQuery.value = ''
  }

  return {
    months,
    types,
    cities,

    selectedMonths,
    monthLogic,
    selectedTypes,
    selectedCities,
    searchQuery,

    filteredConstructions,

    resetFilters
  }
}
