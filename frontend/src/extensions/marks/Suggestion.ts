import { Mark, mergeAttributes } from '@tiptap/core'

export interface SuggestionOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    suggestion: {
      addSuggestion: (attrs: {
        suggestionId: string
        type: 'insert' | 'delete' | 'replace'
        status?: 'pending' | 'accepted' | 'rejected'
      }) => ReturnType
      acceptSuggestion: (attrs: { suggestionId: string }) => ReturnType
      rejectSuggestion: (attrs: { suggestionId: string }) => ReturnType
      unsetSuggestion: () => ReturnType
    }
  }
}

interface MarkRange {
  from: number
  to: number
  type: string
}

function collectMarkRanges(
  doc: import('prosemirror-model').Node,
  markType: import('prosemirror-model').MarkType,
  suggestionId: string,
): MarkRange[] {
  const ranges: MarkRange[] = []
  doc.descendants((node, pos) => {
    if (!node.isText) return
    node.marks.forEach((mark) => {
      if (
        mark.type === markType &&
        mark.attrs.suggestionId === suggestionId
      ) {
        ranges.push({
          from: pos,
          to: pos + node.nodeSize,
          type: mark.attrs.type as string,
        })
      }
    })
  })
  return ranges
}

export const Suggestion = Mark.create<SuggestionOptions>({
  name: 'suggestion',
  group: 'annotation',

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      suggestionId: { default: null },
      type: { default: 'insert' },
      status: { default: 'pending' },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-suggestion]' }]
  },

  renderHTML({ mark }) {
    const { type, status } = mark.attrs
    if (status === 'accepted') {
      return ['span', mergeAttributes({ 'data-suggestion': 'accepted' }), 0]
    }
    if (status === 'rejected') {
      return ['span', mergeAttributes({ 'data-suggestion': 'rejected', style: 'display: none;' }), 0]
    }
    let style = ''
    if (type === 'insert') {
      style = 'border-bottom: 2px solid var(--color-cta); text-decoration: none;'
    } else if (type === 'delete') {
      style = 'text-decoration: line-through; color: var(--color-danger);'
    } else if (type === 'replace') {
      style = 'text-decoration: underline wavy var(--color-warning); text-underline-offset: 3px;'
    }
    return ['span', mergeAttributes({ 'data-suggestion': 'pending', style }), 0]
  },

  addCommands() {
    return {
      addSuggestion:
        (attrs) =>
        ({ commands }) => {
          return commands.setMark(this.name, attrs)
        },

      acceptSuggestion:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const markType = state.schema.marks[this.name]
          const ranges = collectMarkRanges(state.doc, markType, attrs.suggestionId)
          if (ranges.length === 0) return false

          ranges.sort((a, b) => b.from - a.from)

          for (const { from, to, type } of ranges) {
            if (type === 'delete') {
              tr.delete(from, to)
            } else {
              tr.removeMark(from, to, markType)
            }
          }

          if (dispatch) {
            dispatch(tr)
          }
          return true
        },

      rejectSuggestion:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const markType = state.schema.marks[this.name]
          const ranges = collectMarkRanges(state.doc, markType, attrs.suggestionId)
          if (ranges.length === 0) return false

          ranges.sort((a, b) => b.from - a.from)

          for (const { from, to, type } of ranges) {
            if (type === 'insert') {
              tr.delete(from, to)
            } else {
              tr.removeMark(from, to, markType)
            }
          }

          if (dispatch) {
            dispatch(tr)
          }
          return true
        },

      unsetSuggestion:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
