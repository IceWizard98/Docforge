import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Suggestion } from '@/types/document'
import apiClient from '@/api/client'

export const useSuggestionStore = defineStore('suggestion', () => {
  const suggestions = ref<Suggestion[]>([])
  const activeIndex = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

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

  function clampIndex() {
    const len = pendingSuggestions.value.length
    if (len === 0) {
      activeIndex.value = 0
    } else if (activeIndex.value >= len) {
      activeIndex.value = len - 1
    }
  }

  function acceptSuggestion(suggestionId: string) {
    suggestions.value = suggestions.value.map((s) =>
      s.suggestionId === suggestionId && s.status === 'pending'
        ? { ...s, status: 'accepted' as const }
        : s,
    )
    clampIndex()
  }

  function rejectSuggestion(suggestionId: string) {
    suggestions.value = suggestions.value.map((s) =>
      s.suggestionId === suggestionId && s.status === 'pending'
        ? { ...s, status: 'rejected' as const }
        : s,
    )
    clampIndex()
  }

  function acceptAll() {
    suggestions.value = suggestions.value.map((s) =>
      s.status === 'pending' ? { ...s, status: 'accepted' as const } : s,
    )
    clampIndex()
  }

  function rejectAll() {
    suggestions.value = suggestions.value.map((s) =>
      s.status === 'pending' ? { ...s, status: 'rejected' as const } : s,
    )
    clampIndex()
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

  async function fetchSuggestions(documentId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await apiClient.get(`/patches/${documentId}`)
      setSuggestions(response.data as Suggestion[])
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || 'Failed to fetch suggestions'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    suggestions.value = []
    activeIndex.value = 0
    error.value = null
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
    loading,
    error,
    fetchSuggestions,
    reset,
  }
})
