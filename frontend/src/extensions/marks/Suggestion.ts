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
    const { type } = mark.attrs
    let style = ''
    if (type === 'insert') {
      style = 'border-bottom: 2px solid var(--color-cta); text-decoration: none;'
    } else if (type === 'delete') {
      style = 'text-decoration: line-through; color: var(--color-danger);'
    } else if (type === 'replace') {
      style = 'text-decoration: underline wavy var(--color-warning); text-underline-offset: 3px;'
    }
    return ['span', mergeAttributes({ 'data-suggestion': '', style }), 0]
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
          let updated = false

          state.doc.descendants((node, pos) => {
            node.marks.forEach((mark) => {
              if (
                mark.type === markType &&
                mark.attrs.suggestionId === attrs.suggestionId &&
                mark.attrs.status !== 'accepted'
              ) {
                const newMark = markType.create(Object.assign({}, mark.attrs, { status: 'accepted' }))
                tr.removeMark(pos, pos + node.nodeSize, markType)
                tr.addMark(pos, pos + node.nodeSize, newMark)
                updated = true
              }
            })
          })

          if (updated && dispatch) {
            dispatch(tr)
            return true
          }
          return false
        },

      rejectSuggestion:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const markType = state.schema.marks[this.name]
          let updated = false

          state.doc.descendants((node, pos) => {
            node.marks.forEach((mark) => {
              if (
                mark.type === markType &&
                mark.attrs.suggestionId === attrs.suggestionId &&
                mark.attrs.status !== 'rejected'
              ) {
                const newMark = markType.create(Object.assign({}, mark.attrs, { status: 'rejected' }))
                tr.removeMark(pos, pos + node.nodeSize, markType)
                tr.addMark(pos, pos + node.nodeSize, newMark)
                updated = true
              }
            })
          })

          if (updated && dispatch) {
            dispatch(tr)
            return true
          }
          return false
        },

      unsetSuggestion:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
