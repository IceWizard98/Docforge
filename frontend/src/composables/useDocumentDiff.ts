import { ref, computed } from 'vue'
import { diffWords } from 'diff'
import type { DiffOperation, DiffSummary } from '@/types/document'
import type { Node as PMNode } from 'prosemirror-model'

export function useDocumentDiff() {
  const docA = ref<PMNode | null>(null)
  const docB = ref<PMNode | null>(null)
  const showDiff = ref(true)

  const operations = computed<DiffOperation[]>(() => {
    if (!docA.value || !docB.value) return []

    const textA = docA.value.textContent
    const textB = docB.value.textContent
    const changes = diffWords(textA, textB)

    return changes.map((part: { added?: boolean; removed?: boolean; value: string }) => {
      if (part.added) {
        return { type: 'insert', newText: part.value, value: part.value } as DiffOperation
      }
      if (part.removed) {
        return { type: 'delete', originalText: part.value, value: part.value } as DiffOperation
      }
      return { type: 'equal', value: part.value } as DiffOperation
    })
  })

  const summary = computed<DiffSummary>(() => {
    const ops = operations.value
    const inserts = ops.filter((o) => o.type === 'insert').length
    const deletes = ops.filter((o) => o.type === 'delete').length
    const replaces = ops.filter((o) => o.type === 'replace').length
    const wordsChanged = ops
      .filter((o) => o.type !== 'equal')
      .reduce((sum, o) => sum + (o.value?.split(/\s+/).filter(Boolean).length || 0), 0)

    return {
      sectionsAdded: inserts,
      sectionsRemoved: deletes,
      sectionsModified: replaces,
      wordsChanged,
      operations: ops,
    }
  })

  function setDocuments(a: PMNode, b: PMNode) {
    docA.value = a
    docB.value = b
  }

  function toggleDiff() {
    showDiff.value = !showDiff.value
  }

  function clear() {
    docA.value = null
    docB.value = null
    showDiff.value = true
  }

  return {
    docA,
    docB,
    showDiff,
    operations,
    summary,
    setDocuments,
    toggleDiff,
    clear,
  }
}
