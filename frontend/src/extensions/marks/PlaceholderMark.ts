import { Mark, mergeAttributes } from '@tiptap/core'

export interface PlaceholderMarkOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    placeholderMark: {
      setPlaceholderMark: (attrs: { slotId?: string; reason?: string }) => ReturnType
      unsetPlaceholderMark: () => ReturnType
    }
  }
}

// Marks generated text that is NOT backed by a source — explicit placeholder the
// user must fill, visually distinct from sourced (provenance) text so a
// hallucinated clause can never masquerade as grounded.
export const PlaceholderMark = Mark.create<PlaceholderMarkOptions>({
  name: 'placeholderMark',
  group: 'annotation',

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      slotId: { default: null },
      reason: { default: null },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-placeholder-mark]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-placeholder-mark': '',
        style:
          'border-bottom: 1.5px dashed var(--color-warning); '
          + 'background: color-mix(in srgb, var(--color-warning) 12%, transparent); cursor: help;',
      }),
      0,
    ]
  },

  addCommands() {
    return {
      setPlaceholderMark:
        (attrs) =>
        ({ commands }) => {
          return commands.setMark(this.name, attrs)
        },
      unsetPlaceholderMark:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
