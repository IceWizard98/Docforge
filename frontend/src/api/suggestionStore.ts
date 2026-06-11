import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'
import type { Suggestion } from '@/types/document'

export async function fetchSuggestions(documentId: string): Promise<Suggestion[]> {
  const response = await apiClient.get(`/patches/${documentId}`)
  const body = response.data as { data: { suggestions: Suggestion[] } }
  return body.data?.suggestions || []
}

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

  async function acceptSuggestion(suggestionId: string) {
    try {
      await apiClient.post(`/patches/${suggestionId}/accept`)
      suggestions.value = suggestions.value.map((s) =>
        s.suggestionId === suggestionId && s.status === 'pending'
          ? { ...s, status: 'accepted' as const }
          : s,
      )
    } catch (err) {
      error.value = (err as any)?.message || 'Failed to accept'
    }
    clampIndex()
  }

  async function rejectSuggestion(suggestionId: string) {
    try {
      await apiClient.post(`/patches/${suggestionId}/reject`)
      suggestions.value = suggestions.value.map((s) =>
        s.suggestionId === suggestionId && s.status === 'pending'
          ? { ...s, status: 'rejected' as const }
          : s,
      )
    } catch (err) {
      error.value = (err as any)?.message || 'Failed to reject'
    }
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

  async function loadSuggestions(documentId: string) {
    loading.value = true
    try {
      const items = await fetchSuggestions(documentId)
      suggestions.value = items
      activeIndex.value = 0
    } catch (err) {
      error.value = (err as any)?.message || 'Failed to load suggestions'
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
    loadSuggestions,
    reset,
  }
})
