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
import { Comment } from '@/extensions/marks/Comment'
import { Suggestion } from '@/extensions/marks/Suggestion'
import { DocumentMetaPlugin } from '@/extensions/plugins/DocumentMetaPlugin'
import { DiffPlugin } from '@/plugins/DiffPlugin'
import { diffPluginKey } from '@/plugins/DiffPlugin'
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

const debouncedSave = useDebounceFn((json: Record<string, unknown>) => {
  saveStatus.value = 'saving'
  emit('save', json)
  saveStatus.value = 'saved'
  hasUnsavedChanges.value = false
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
  Comment,
  Suggestion,
  DocumentMetaPlugin(),
  DiffPlugin(props.diffOperations || [], !!props.diffMode),
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

defineExpose({ editor })
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
