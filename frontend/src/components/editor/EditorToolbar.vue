<script setup lang="ts">
import type { Editor } from '@tiptap/core'
import {
  Bold, Italic, Underline, Strikethrough,
  Heading1, Heading2, Heading3,
  List, ListOrdered,
  Quote, Code,
  Undo2, Redo2,
  Table,
} from '@lucide/vue'

const props = defineProps<{
  editor: Editor | null | undefined
}>()

function isActive(name: string, attrs?: Record<string, unknown>) {
  return props.editor?.isActive(name, attrs) ?? false
}

function handleTable() {
  props.editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
}
</script>

<template>
  <div
    v-if="editor"
    class="flex items-center gap-0.5 px-2 py-1.5 border-b border-primary/10 bg-surface/60 flex-wrap"
  >
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('bold') }"
      title="Bold"
      @click="editor.chain().focus().toggleBold().run()"
    >
      <Bold class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('italic') }"
      title="Italic"
      @click="editor.chain().focus().toggleItalic().run()"
    >
      <Italic class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('underline') }"
      title="Underline"
      @click="editor.chain().focus().toggleUnderline().run()"
    >
      <Underline class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('strike') }"
      title="Strikethrough"
      @click="editor.chain().focus().toggleStrike().run()"
    >
      <Strikethrough class="w-4 h-4" />
    </button>

    <span class="w-px h-5 bg-primary/10 mx-0.5" />

    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('heading', { level: 1 }) }"
      title="Heading 1"
      @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
    >
      <Heading1 class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('heading', { level: 2 }) }"
      title="Heading 2"
      @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
    >
      <Heading2 class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('heading', { level: 3 }) }"
      title="Heading 3"
      @click="editor.chain().focus().toggleHeading({ level: 3 }).run()"
    >
      <Heading3 class="w-4 h-4" />
    </button>

    <span class="w-px h-5 bg-primary/10 mx-0.5" />

    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('bulletList') }"
      title="Bullet List"
      @click="editor.chain().focus().toggleBulletList().run()"
    >
      <List class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('orderedList') }"
      title="Ordered List"
      @click="editor.chain().focus().toggleOrderedList().run()"
    >
      <ListOrdered class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('blockquote') }"
      title="Blockquote"
      @click="editor.chain().focus().toggleBlockquote().run()"
    >
      <Quote class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :class="{ 'bg-primary/12 text-primary': isActive('codeBlock') }"
      title="Code Block"
      @click="editor.chain().focus().toggleCodeBlock().run()"
    >
      <Code class="w-4 h-4" />
    </button>

    <span class="w-px h-5 bg-primary/10 mx-0.5" />

    <button
      class="p-1.5 rounded text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      title="Insert Table"
      @click="handleTable"
    >
      <Table class="w-4 h-4" />
    </button>

    <span class="flex-1" />

    <button
      class="p-1.5 rounded text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      title="Undo"
      :disabled="!editor.can().chain().focus().undo().run()"
      @click="editor.chain().focus().undo().run()"
    >
      <Undo2 class="w-4 h-4" />
    </button>
    <button
      class="p-1.5 rounded text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      title="Redo"
      :disabled="!editor.can().chain().focus().redo().run()"
      @click="editor.chain().focus().redo().run()"
    >
      <Redo2 class="w-4 h-4" />
    </button>
  </div>
</template>
