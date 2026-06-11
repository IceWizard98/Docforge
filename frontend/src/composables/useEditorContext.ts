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

    if (ed && !ed.isDestroyed) {
      const { from, to } = ed.state.selection
      if (from !== to) {
        cursorPosition = { from, to }
        if (!selectedText) {
          selectedText = ed.state.doc.textBetween(from, to, ' ')
        }
      } else {
        cursorPosition = { from, to }
      }
    }

    return {
      activeSectionId: editorStore.activeSectionId,
      activeClauseId: null,
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
