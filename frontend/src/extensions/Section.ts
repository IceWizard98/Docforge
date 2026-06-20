import { Node, mergeAttributes } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-3'
import SectionNodeView from '@/components/editor/SectionNodeView.vue'

export interface SectionOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    section: {
      insertSection: (attrs?: Record<string, unknown>) => ReturnType
    }
  }
}

export const Section = Node.create<SectionOptions>({
  name: 'section',
  group: 'block',
  content: '(clause|paragraph)+',
  defining: true,

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      sectionId: { default: null },
      number: { default: '' },
      status: { default: 'draft' },
      title: { default: '' },
      provenance: { default: [] },
    }
  },

  parseHTML() {
    return [{ tag: 'div[data-section]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-section': '' }), 0]
  },

  addCommands() {
    return {
      insertSection: (attrs) => ({ commands }) => {
        return commands.insertContent({
          type: 'section',
          attrs: attrs || {},
          content: [
            { type: 'paragraph', content: [] },
          ],
        })
      },
    }
  },

  addNodeView() {
    return VueNodeViewRenderer(SectionNodeView)
  },
})
