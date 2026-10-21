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

/*
 * Нормализация поиска: регистр, «ё», пунктуация и лишние пробелы.
 * Дефис в «Ростов-на-Дону» становится пробелом, поэтому запрос
 * «Ростов на Дону» находит город.
 */
function normalize(value) {
  return String(value ?? '')
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

function formatMonth(month, year) {
  return `${MONTH_SHORT[month] || month} ${year || new Date().getFullYear()}`
}

export function useConstructionsFilter(constructions) {
  const selectedMonths = ref([])
  const monthLogic = ref('OR')
  const selectedTypes = ref([])
  const selectedCities = ref([])
  const searchQuery = ref('')

  // Форматы выбираются все после загрузки данных.
  // Месяцы и города по умолчанию СНЯТЫ: пустой набор означает
  // «фильтр не применяется» (показаны все).
  let typesInitialized = false

  /*
   * Месяцы берём непосредственно из данных.
   * Никакого жёсткого списка месяцев для фильтрации.
   */
  const months = computed(() => {
    const found = new Set()
    const years = new Map()

    for (const item of constructions.value || []) {
      for (const month of Object.keys(item?.statuses || {})) {
        found.add(month)
      }

      for (const month of Object.keys(item?.months || {})) {
        found.add(month)
      }

      for (const [month, year] of Object.entries(item?.month_years || {})) {
        const value = Number(year)

        if (Number.isFinite(value) && value > (years.get(month) || 0)) {
          years.set(month, value)
        }
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
        label: formatMonth(month, years.get(month))
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

  // После загрузки данных один раз выбираем ВСЕ форматы. Города остаются
  // снятыми: пустой selectedCities означает «все города».
  watch(
    types,
    (values, previous) => {
      if (!values.length) {
        return
      }

      if (!typesInitialized) {
        selectedTypes.value = [...values]
        typesInitialized = true
        return
      }

      /*
       * Каталог перезагрузили. Если были выбраны все форматы — выбираем
       * все новые; если подмножество — оставляем только существующие.
       */
      const wasAll =
        !selectedTypes.value.length ||
        selectedTypes.value.length === (previous?.length || 0)

      if (wasAll) {
        selectedTypes.value = [...values]
        return
      }

      const available = new Set(values)
      selectedTypes.value = selectedTypes.value.filter(type =>
        available.has(type)
      )
    },
    { immediate: true }
  )

  /* Города: пустой набор = все, подмножество чистим от исчезнувших. */
  watch(cities, (values, previous) => {
    if (!values.length || !selectedCities.value.length) {
      return
    }

    if (selectedCities.value.length === (previous?.length || 0)) {
      selectedCities.value = [...values]
      return
    }

    const available = new Set(values)
    selectedCities.value = selectedCities.value.filter(city =>
      available.has(city)
    )
  })

  /* Месяцы: убираем выбранные, которых больше нет в каталоге. */
  watch(months, values => {
    if (!values.length) {
      return
    }

    const available = new Set(values.map(month => month.value))
    const next = selectedMonths.value.filter(month => available.has(month))

    if (next.length !== selectedMonths.value.length) {
      selectedMonths.value = next
    }
  })

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
        const monthsMatch =
          monthLogic.value === 'AND'
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

        /* Порядок слов не важен: «Курчатова Волгодонск» = «Волгодонск Курчатова». */
        const tokens = query.split(' ').filter(Boolean)

        if (!tokens.every(token => haystack.includes(token))) {
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
    /* Пустой набор городов = «выбраны все». */
    selectedCities.value = []
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
