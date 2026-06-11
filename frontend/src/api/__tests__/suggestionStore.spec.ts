import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSuggestionStore } from '../suggestionStore'
import type { Suggestion } from '@/types/document'
import apiClient from '@/api/client'

function makeSuggestion(id: string, status: Suggestion['status'], type: Suggestion['type'] = 'insert'): Suggestion {
  return { suggestionId: id, type, status }
}

describe('suggestionStore', () => {
  let spyPost: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    setActivePinia(createPinia())
    spyPost = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} })
  })

  afterEach(() => {
    spyPost.mockRestore()
  })

  it('initializes empty', () => {
    const store = useSuggestionStore()
    expect(store.totalCount).toBe(0)
    expect(store.pendingCount).toBe(0)
    expect(store.pendingSuggestions).toEqual([])
    expect(store.currentSuggestion).toBeNull()
  })

  it('adds suggestions and updates counts', () => {
    const store = useSuggestionStore()
    store.addSuggestion(makeSuggestion('1', 'pending'))
    store.addSuggestion(makeSuggestion('2', 'accepted'))

    expect(store.totalCount).toBe(2)
    expect(store.pendingCount).toBe(1)
    expect(store.pendingSuggestions).toHaveLength(1)
    expect(store.pendingSuggestions[0].suggestionId).toBe('1')
  })

  it('accepts a suggestion via store action', async () => {
    const store = useSuggestionStore()
    store.addSuggestion(makeSuggestion('1', 'pending'))
    await store.acceptSuggestion('1')

    expect(store.pendingCount).toBe(0)
    expect(store.completedSuggestions).toHaveLength(1)
    expect(store.completedSuggestions[0].status).toBe('accepted')
  })

  it('rejects a suggestion via store action', async () => {
    const store = useSuggestionStore()
    store.addSuggestion(makeSuggestion('1', 'pending'))
    await store.rejectSuggestion('1')

    expect(store.pendingCount).toBe(0)
    expect(store.completedSuggestions).toHaveLength(1)
    expect(store.completedSuggestions[0].status).toBe('rejected')
  })

  it('setSuggestions replaces all suggestions', () => {
    const store = useSuggestionStore()
    store.setSuggestions([
      makeSuggestion('1', 'pending'),
      makeSuggestion('2', 'pending'),
      makeSuggestion('3', 'accepted'),
    ])

    expect(store.totalCount).toBe(3)
    expect(store.pendingCount).toBe(2)
    expect(store.activeIndex).toBe(0)
  })

  it('navigates through pending suggestions', () => {
    const store = useSuggestionStore()
    store.setSuggestions([
      makeSuggestion('1', 'pending'),
      makeSuggestion('2', 'pending'),
      makeSuggestion('3', 'pending'),
    ])

    expect(store.currentSuggestion?.suggestionId).toBe('1')
    expect(store.canGoNext).toBe(true)
    expect(store.canGoPrev).toBe(false)

    store.goNext()
    expect(store.currentSuggestion?.suggestionId).toBe('2')
    expect(store.canGoPrev).toBe(true)

    store.goNext()
    expect(store.currentSuggestion?.suggestionId).toBe('3')
    expect(store.canGoNext).toBe(false)

    store.goPrev()
    expect(store.currentSuggestion?.suggestionId).toBe('2')
  })

  it('updates computed values reactively', () => {
    const store = useSuggestionStore()
    store.setSuggestions([makeSuggestion('1', 'pending')])
    expect(store.pendingCount).toBe(1)

    store.$patch((state) => {
      state.suggestions = state.suggestions.map((s) =>
        s.suggestionId === '1' ? { ...s, status: 'accepted' } : s,
      )
    })

    expect(store.pendingCount).toBe(0)
    expect(store.completedSuggestions).toHaveLength(1)
    expect(store.completedSuggestions[0].status).toBe('accepted')
  })

  it('handles acceptAll', () => {
    const store = useSuggestionStore()
    store.setSuggestions([
      makeSuggestion('1', 'pending'),
      makeSuggestion('2', 'pending'),
      makeSuggestion('3', 'rejected'),
    ])

    store.acceptAll()

    expect(store.pendingCount).toBe(0)
    expect(store.completedSuggestions).toHaveLength(3)
  })

  it('handles rejectAll', () => {
    const store = useSuggestionStore()
    store.setSuggestions([
      makeSuggestion('1', 'pending'),
      makeSuggestion('2', 'pending'),
    ])

    store.rejectAll()

    expect(store.pendingCount).toBe(0)
    expect(store.completedSuggestions.every((s) => s.status === 'rejected')).toBe(true)
  })

  it('resets to initial state', () => {
    const store = useSuggestionStore()
    store.setSuggestions([makeSuggestion('1', 'pending')])
    store.goNext()

    store.reset()

    expect(store.totalCount).toBe(0)
    expect(store.pendingCount).toBe(0)
    expect(store.activeIndex).toBe(0)
    expect(store.currentSuggestion).toBeNull()
  })

  it('returns null currentSuggestion when no pending', () => {
    const store = useSuggestionStore()
    store.setSuggestions([makeSuggestion('1', 'accepted')])

    expect(store.currentSuggestion).toBeNull()
  })

  it('provides correct canGoNext and canGoPrev at boundaries', () => {
    const store = useSuggestionStore()
    store.setSuggestions([makeSuggestion('1', 'pending')])

    expect(store.canGoNext).toBe(false)
    expect(store.canGoPrev).toBe(false)
  })
})
