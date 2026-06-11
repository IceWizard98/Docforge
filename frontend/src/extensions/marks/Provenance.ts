import { Mark, mergeAttributes } from '@tiptap/core'

export interface ProvenanceOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    provenance: {
      setProvenance: (attrs: { sourceDocId: string; chunkId?: string; confidence?: number }) => ReturnType
      unsetProvenance: () => ReturnType
    }
  }
}

export const Provenance = Mark.create<ProvenanceOptions>({
  name: 'provenance',
  group: 'annotation',

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      sourceDocId: { default: null },
      chunkId: { default: null },
      confidence: { default: 0 },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-provenance]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-provenance': '',
        style: 'border-bottom: 1.5px dotted var(--color-primary-light); cursor: help;',
      }),
      0,
    ]
  },

  addCommands() {
    return {
      setProvenance:
        (attrs) =>
        ({ commands }) => {
          return commands.setMark(this.name, attrs)
        },
      unsetProvenance:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
