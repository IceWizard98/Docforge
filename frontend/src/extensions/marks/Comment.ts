import { Mark, mergeAttributes } from '@tiptap/core'

export interface CommentOptions {
  HTMLAttributes: Record<string, unknown>
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    comment: {
      addComment: (attrs: { commentId: string; threadId: string; resolved?: boolean }) => ReturnType
      resolveComment: (attrs: { commentId: string }) => ReturnType
      unsetComment: () => ReturnType
    }
  }
}

export const Comment = Mark.create<CommentOptions>({
  name: 'comment',
  group: 'annotation',

  addOptions() {
    return {
      HTMLAttributes: {},
    }
  },

  addAttributes() {
    return {
      commentId: { default: null },
      threadId: { default: null },
      resolved: { default: false },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-comment]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-comment': '',
        style: 'background-color: color-mix(in srgb, var(--color-warning) 20%, transparent); cursor: pointer; border-radius: 2px;',
      }),
      0,
    ]
  },

  addCommands() {
    return {
      addComment:
        (attrs) =>
        ({ commands }) => {
          return commands.setMark(this.name, { ...attrs, resolved: false })
        },
      resolveComment:
        (attrs) =>
        ({ tr, state, dispatch }) => {
          const markType = state.schema.marks[this.name]
          const { from, to } = tr.selection
          if (from === to) return false

          let oldAttrs: Record<string, unknown> | null = null
          state.doc.nodesBetween(from, to, (node) => {
            if (!oldAttrs) {
              node.marks.forEach((mark) => {
                if (mark.type === markType && mark.attrs.commentId === attrs.commentId) {
                  oldAttrs = Object.assign({}, mark.attrs)
                }
              })
            }
          })

          if (!oldAttrs) return false
          tr.removeMark(from, to, markType)
          tr.addMark(from, to, markType.create(Object.assign({}, oldAttrs, { resolved: true })))
          if (dispatch) dispatch(tr)
          return true
        },
      unsetComment:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
