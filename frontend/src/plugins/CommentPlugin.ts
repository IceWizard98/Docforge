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

export interface CommentPluginOptions {
  comments?: CommentWidget[]
  onClick?: (commentId: string, threadId: string) => void
}

export function CommentPlugin(options: CommentPluginOptions = {}): Plugin {
  const { comments = [], onClick } = options

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

        const foundDecos = pluginState.find(pos, pos)
        if (foundDecos.length > 0 && onClick) {
          const dom = view.domAtPos(pos)
          if (dom.node) {
            const el = dom.node.nodeType === 3 ? dom.node.parentElement : dom.node as HTMLElement
            const commentId = el?.getAttribute('data-comment-id')
            const threadId = el?.getAttribute('data-thread-id')
            if (commentId) {
              onClick(commentId, threadId || '')
              return true
            }
          }
        }
        return foundDecos.length > 0
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
