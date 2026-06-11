import { describe, it, expect } from 'vitest'

function mockNode(text: string) {
  return { textContent: text } as any
}

describe('useDocumentDiff', () => {
  it('computes diff between two text strings', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    diff.setDocuments(mockNode('Hello world'), mockNode('Hello there world'))

    expect(diff.summary.value.wordsAdded).toBeGreaterThan(0)
    expect(diff.operations.value.length).toBeGreaterThan(0)
  })

  it('shows no changes for identical texts', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    diff.setDocuments(mockNode('Same text'), mockNode('Same text'))

    expect(diff.summary.value.wordsAdded).toBe(0)
    expect(diff.summary.value.wordsRemoved).toBe(0)
  })

  it('detects both additions and removals', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    diff.setDocuments(mockNode('a b c'), mockNode('a x c'))

    expect(diff.summary.value.wordsAdded).toBeGreaterThan(0)
    expect(diff.summary.value.wordsRemoved).toBeGreaterThan(0)
  })

  it('clears diff on clear', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    diff.setDocuments(mockNode('a b c'), mockNode('a x c'))
    expect(diff.operations.value.length).toBeGreaterThan(1)

    diff.clear()

    expect(diff.operations.value.length).toBe(0)
  })

  it('toggles diff visibility', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    expect(diff.showDiff.value).toBe(true)
    diff.toggleDiff()
    expect(diff.showDiff.value).toBe(false)
    diff.toggleDiff()
    expect(diff.showDiff.value).toBe(true)
  })

  it('returns empty operations when no documents set', async () => {
    const { useDocumentDiff } = await import('@/composables/useDocumentDiff')
    const diff = useDocumentDiff()

    expect(diff.operations.value.length).toBe(0)
    expect(diff.summary.value.wordsChanged).toBe(0)
  })
})
