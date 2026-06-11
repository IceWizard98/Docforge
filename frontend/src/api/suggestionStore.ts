import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Suggestion } from '@/types/document'

export const useSuggestionStore = defineStore('suggestion', () => {
  const suggestions = ref<Suggestion[]>([])
  const activeIndex = ref(0)

  const pendingSuggestions = computed(() =>
    suggestions.value.filter((s) => s.status === 'pending'),
  )

  const completedSuggestions = computed(() =>
    suggestions.value.filter((s) => s.status !== 'pending'),
  )

  const pendingCount = computed(() => pendingSuggestions.value.length)

  const totalCount = computed(() => suggestions.value.length)

  const currentSuggestion = computed(() => {
    const pending = pendingSuggestions.value
    if (pending.length === 0) return null
    const idx = Math.min(activeIndex.value, pending.length - 1)
    return pending[idx]
  })

  const canGoPrev = computed(() => activeIndex.value > 0)

  const canGoNext = computed(
    () => activeIndex.value < pendingSuggestions.value.length - 1,
  )

  function setSuggestions(items: Suggestion[]) {
    suggestions.value = items
    activeIndex.value = 0
  }

  function addSuggestion(s: Suggestion) {
    suggestions.value.push(s)
  }

  function acceptSuggestion(suggestionId: string) {
    const found = suggestions.value.find((s) => s.suggestionId === suggestionId)
    if (found) {
      found.status = 'accepted'
    }
  }

  function rejectSuggestion(suggestionId: string) {
    const found = suggestions.value.find((s) => s.suggestionId === suggestionId)
    if (found) {
      found.status = 'rejected'
    }
  }

  function acceptAll() {
    suggestions.value.forEach((s) => {
      if (s.status === 'pending') {
        s.status = 'accepted'
      }
    })
  }

  function rejectAll() {
    suggestions.value.forEach((s) => {
      if (s.status === 'pending') {
        s.status = 'rejected'
      }
    })
  }

  function goNext() {
    if (canGoNext.value) {
      activeIndex.value++
    }
  }

  function goPrev() {
    if (canGoPrev.value) {
      activeIndex.value--
    }
  }

  function reset() {
    suggestions.value = []
    activeIndex.value = 0
  }

  return {
    suggestions,
    activeIndex,
    pendingSuggestions,
    completedSuggestions,
    pendingCount,
    totalCount,
    currentSuggestion,
    canGoPrev,
    canGoNext,
    setSuggestions,
    addSuggestion,
    acceptSuggestion,
    rejectSuggestion,
    acceptAll,
    rejectAll,
    goNext,
    goPrev,
    reset,
  }
})
