import { ref } from 'vue'

const resultIds = ref([])

export function useChatWorkspace() {
  function setResults(items) {
    resultIds.value = Array.isArray(items)
      ? items.map(item => Number(item?.id)).filter(Number.isFinite)
      : []
  }

  function clear() {
    resultIds.value = []
  }

  return { resultIds, setResults, clear }
}
