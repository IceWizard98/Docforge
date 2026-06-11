import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import ClauseNodeView from '@/components/editor/ClauseNodeView.vue'

export interface ClauseOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    clause: {
      insertClause: (attrs?: Record<string, unknown>) => ReturnType
    }
  }
}

export const Clause = Node.create<ClauseOptions>({
  name: 'clause',
  group: 'block',
  content: '(paragraph|bulletList|orderedList)+',
  defining: true,

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      clauseId: { default: null },
      number: { default: '' },
      status: { default: 'draft' },
      provenance: { default: [] },
    }
  },

  parseHTML() {
    return [{ tag: 'div[data-clause]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-clause': '' }), 0]
  },

  addCommands() {
    return {
      insertClause:
        (attrs?: Record<string, unknown>) =>
        ({ commands }: { commands: any }) => {
          return commands.insertContent({
            type: 'clause',
            attrs: attrs || {},
            content: [{ type: 'paragraph', content: [] }],
          })
        },
    }
  },

  addNodeView() {
    return VueNodeViewRenderer(ClauseNodeView)
  },
})
