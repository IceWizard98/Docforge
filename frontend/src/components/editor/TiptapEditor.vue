<script setup lang="ts">
import { onBeforeUnmount, watch, ref, onMounted } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Placeholder from '@tiptap/extension-placeholder'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'
import { useDebounceFn } from '@vueuse/core'
import { Section } from '@/extensions/Section'
import { Clause } from '@/extensions/Clause'
import { Provenance } from '@/extensions/marks/Provenance'
import { PlaceholderMark } from '@/extensions/marks/PlaceholderMark'
import { Comment } from '@/extensions/marks/Comment'
import { Suggestion } from '@/extensions/marks/Suggestion'
import { DocumentMetaPlugin } from '@/extensions/plugins/DocumentMetaPlugin'
import { DiffPlugin } from '@/plugins/DiffPlugin'
import { diffPluginKey } from '@/plugins/DiffPlugin'
import { TrackChangesPlugin } from '@/plugins/TrackChangesPlugin'
import type { DiffOperation } from '@/types/document'
import EditorToolbar from './EditorToolbar.vue'
import { useDocumentStore } from '@/stores/documentStore'

const props = defineProps<{
  diffMode?: boolean
  diffOperations?: DiffOperation[]
  content?: Record<string, unknown>
  documentId?: string
}>()

const emit = defineEmits<{
  save: [json: Record<string, unknown>]
}>()

const documentStore = useDocumentStore()
const saveStatus = ref<'saved' | 'saving' | 'unsaved'>('saved')
const hasUnsavedChanges = ref(false)

const debouncedSave = useDebounceFn(async (json: Record<string, unknown>) => {
  saveStatus.value = 'saving'
  emit('save', json)
  // Wait briefly for async save to settle, then check store
  await new Promise(resolve => setTimeout(resolve, 100))
  if (documentStore.error) {
    saveStatus.value = 'unsaved'
  } else {
    saveStatus.value = 'saved'
    hasUnsavedChanges.value = false
  }
}, 2000)

const extensions: any[] = [
  StarterKit.configure({
    heading: { levels: [1, 2, 3] },
  }),
  Underline,
  Placeholder.configure({
    placeholder: 'Inizia a scrivere o usa la chat per generare contenuti...',
  }),
  Section,
  Clause,
  Provenance,
  PlaceholderMark,
  Comment,
  Suggestion,
  DocumentMetaPlugin(),
  DiffPlugin(props.diffOperations || [], !!props.diffMode),
  TrackChangesPlugin(),
  Table.configure({ resizable: true }),
  TableRow,
  TableCell,
  TableHeader,
]

const defaultContent = {
  type: 'doc',
  content: [
    {
      type: 'section',
      attrs: { sectionId: 'sec_1', number: '1', status: 'draft' },
      content: [
        { type: 'paragraph', content: [{ type: 'text', text: 'Inizia a scrivere...' }] },
      ],
    },
  ],
}

const editor = useEditor({
  content: (props.content || defaultContent) as any,
  extensions,
  editorProps: {
    attributes: {
      class: 'prose prose-sm max-w-none focus:outline-none min-h-[500px] p-6',
    },
  },
  onUpdate: () => {
    if (!editor.value) return
    saveStatus.value = 'unsaved'
    hasUnsavedChanges.value = true
    debouncedSave(editor.value.getJSON() as Record<string, unknown>)
  },
})

watch(() => props.diffOperations, (ops) => {
  if (!editor.value) return
  const tr = editor.value.state.tr
  tr.setMeta(diffPluginKey, { operations: ops || [] })
  editor.value.view.dispatch(tr)
}, { deep: true })

watch(() => props.content, (newContent) => {
  if (!editor.value || !newContent) return
  // Apply external content changes (loaded document, agent edits) whenever the
  // incoming content differs from what the editor holds. Comparing JSON makes
  // this a no-op for the editor's OWN updates (which round-trip through the
  // store and come back identical), so user typing isn't clobbered. Pass
  // emitUpdate=false so setContent doesn't re-trigger onUpdate/save.
  const currentJson = JSON.stringify(editor.value.getJSON())
  if (JSON.stringify(newContent) !== currentJson) {
    editor.value.commands.setContent(newContent as any)
  }
}, { deep: true })

watch(() => props.diffMode, (show) => {
  if (!editor.value) return
  const tr = editor.value.state.tr
  tr.setMeta(diffPluginKey, { toggle: !!show })
  editor.value.view.dispatch(tr)
})

function beforeUnloadHandler(e: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnloadHandler)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler)
  editor.value?.destroy()
})

function applyPatchOperation(op: DiffOperation) {
  if (!editor.value) return
  const { type, fromPos, toPos, value, newText } = op
  const text = newText || value
  if (type === 'insert' && fromPos !== undefined && text) {
    editor.value.commands.insertContentAt(fromPos, text)
  } else if (type === 'delete' && fromPos !== undefined && toPos !== undefined) {
    editor.value.commands.deleteRange({ from: fromPos, to: toPos })
  } else if (type === 'replace' && fromPos !== undefined && toPos !== undefined && text) {
    editor.value.chain().deleteRange({ from: fromPos, to: toPos }).insertContentAt(fromPos, text).run()
  }
}

function scrollToSection(sectionId: string) {
  if (!editor.value) return
  const { doc } = editor.value.state
  let foundPos: number | null = null
  doc.descendants((node, pos) => {
    if (node.type.name === 'section' && node.attrs.sectionId === sectionId) {
      foundPos = pos
      return false
    }
  })
  if (foundPos !== null) {
    try {
      const domPos = editor.value.view.domAtPos(foundPos)
      const el = domPos.node.nodeType === Node.TEXT_NODE
        ? (domPos.node.parentElement as HTMLElement)
        : (domPos.node as HTMLElement)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    } catch (e) {
      console.error('Failed to scroll to section:', e)
    }
  }
}

function updateSectionAttrs(sectionId: string, attrs: Record<string, unknown>) {
  if (!editor.value) return
  const { doc, tr } = editor.value.state
  let foundPos: number | null = null
  doc.descendants((node, pos) => {
    if (node.type.name === 'section' && node.attrs.sectionId === sectionId) {
      foundPos = pos
      return false
    }
  })
  if (foundPos !== null) {
    const node = doc.nodeAt(foundPos)
    if (node) {
      tr.setNodeMarkup(foundPos, undefined, {
        ...node.attrs,
        ...attrs,
      })
      editor.value.view.dispatch(tr)
    }
  }
}

defineExpose({ editor, applyPatchOperation, scrollToSection, updateSectionAttrs })
</script>

<template>
  <div>
    <EditorToolbar :editor="editor" />
    <div class="relative">
      <EditorContent :editor="editor" class="editor-content" />
      <div class="absolute bottom-2 right-3 flex items-center gap-1.5">
        <span
          v-if="saveStatus === 'saving'"
          class="text-[11px] text-warning font-medium"
        >Saving...</span>
        <span
          v-else-if="saveStatus === 'saved'"
          class="text-[11px] text-cta font-medium"
        >Saved</span>
        <span
          v-else
          class="text-[11px] text-foreground/40 font-medium"
        >Unsaved</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-content :deep(.ProseMirror) {
  outline: none;
  min-height: 500px;
}
.editor-content :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  color: var(--color-primary-light);
  content: attr(data-placeholder);
  float: left;
  height: 0;
  pointer-events: none;
}
</style>
