<script setup lang="ts">
import { onBeforeUnmount, computed, watch } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Placeholder from '@tiptap/extension-placeholder'
import { Section } from '@/extensions/Section'
import { Clause } from '@/extensions/Clause'
import { Provenance } from '@/extensions/marks/Provenance'
import { Comment } from '@/extensions/marks/Comment'
import { Suggestion } from '@/extensions/marks/Suggestion'
import { DocumentMetaPlugin } from '@/extensions/plugins/DocumentMetaPlugin'
import { DiffPlugin } from '@/plugins/DiffPlugin'
import { diffPluginKey } from '@/plugins/DiffPlugin'
import type { DiffOperation } from '@/types/document'

const props = defineProps<{
  diffMode?: boolean
  diffOperations?: DiffOperation[]
  content?: Record<string, unknown>
}>()

const extensions: any[] = [
  StarterKit.configure({ heading: false }),
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

onBeforeUnmount(() => {
  editor.value?.destroy()
})

defineExpose({ editor })
</script>

<template>
  <EditorContent :editor="editor" class="editor-content" />
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
