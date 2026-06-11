<script setup lang="ts">
import { onBeforeUnmount, computed } from 'vue'
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
import type { DiffOperation } from '@/types/document'

const props = defineProps<{
  diffMode?: boolean
  diffOperations?: DiffOperation[]
}>()

const extensions = computed(() => {
  const exts: any[] = [
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
  ]

  if (props.diffMode && props.diffOperations) {
    exts.push(DiffPlugin(props.diffOperations, true))
  }

  return exts
})

const editor = useEditor({
  content: {
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
  },
  extensions: extensions.value,
  editorProps: {
    attributes: {
      class: 'prose prose-sm max-w-none focus:outline-none min-h-[500px] p-6',
    },
  },
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
