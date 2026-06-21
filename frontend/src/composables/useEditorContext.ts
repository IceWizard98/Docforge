import { computed } from 'vue'
import { useEditorStore } from '@/stores/editorStore'
import { useDocumentStore } from '@/stores/documentStore'
import type { EditorContext } from '@/types/document'
import type { Editor } from '@tiptap/core'

export function useEditorContext(editor: { value: Editor | null }) {
  const editorStore = useEditorStore()
  const documentStore = useDocumentStore()

  const context = computed<EditorContext>(() => {
    const ed = editor.value
    let cursorPosition: { from: number; to: number } | null = null
    let selectedText: string | null = editorStore.selectedText
    let activeClauseId: string | null = null

    if (ed && !ed.isDestroyed) {
      const { from, to, $from } = ed.state.selection
      if (from !== to) {
        cursorPosition = { from, to }
        if (!selectedText) {
          selectedText = ed.state.doc.textBetween(from, to, ' ')
        }
      } else {
        cursorPosition = { from, to }
      }
      // Find active clause by walking up from cursor position
      for (let depth = $from.depth; depth > 0; depth--) {
        const node = $from.node(depth)
        if (node.type.name === 'clause') {
          activeClauseId = node.attrs.clauseId || node.attrs.id || null
          break
        }
      }
    }

    return {
      activeSectionId: editorStore.activeSectionId,
      activeClauseId,
      selectedText,
      mode: 'compose',
      cursorPosition,
      visibleSections: documentStore.sections.map((s) => s.id),
      documentVersion: documentStore.version,
      documentTitle: documentStore.title,
    }
  })

  return { context }
}
