import { Plugin, PluginKey } from 'prosemirror-state'
import { Decoration, DecorationSet } from 'prosemirror-view'

export const commentPluginKey = new PluginKey('comment')

export interface CommentWidget {
  commentId: string
  threadId: string
  resolved: boolean
  from: number
  to: number
}

export function CommentPlugin(comments: CommentWidget[] = []): Plugin {
  return new Plugin({
    key: commentPluginKey,

    state: {
      init(_config, instance) {
        return buildDecorationSet(comments, instance.doc)
      },

      apply(tr, prev: DecorationSet, _oldState, newState) {
        const meta = tr.getMeta(commentPluginKey)
        if (meta?.comments !== undefined) {
          return buildDecorationSet(meta.comments, newState.doc)
        }
        return prev
      },
    },

    props: {
      decorations(state) {
        return this.getState(state) as DecorationSet
      },

      handleClick(view, pos) {
        const state = view.state
        const pluginState = commentPluginKey.getState(state) as DecorationSet | undefined
        if (!pluginState) return false

        let found = false
        pluginState.find(pos, pos).forEach(() => {
          found = true
        })

        return found
      },
    },
  })
}

function buildDecorationSet(
  comments: CommentWidget[],
  doc: import('prosemirror-model').Node,
): DecorationSet {
  const decorations: Decoration[] = []

  comments.forEach((comment) => {
    if (comment.resolved) return

    decorations.push(
      Decoration.inline(comment.from, comment.to, {
        class: 'comment-highlight',
        style: 'background-color: rgba(245, 158, 11, 0.2); cursor: pointer; border-radius: 2px;',
        'data-comment-id': comment.commentId,
        'data-thread-id': comment.threadId,
      }),
    )
  })

  return DecorationSet.create(doc, decorations)
}
