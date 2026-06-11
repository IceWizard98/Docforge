import { Plugin, PluginKey } from 'prosemirror-state'
import { Decoration, DecorationSet } from 'prosemirror-view'
import type { DiffOperation } from '@/types/document'

export const diffPluginKey = new PluginKey('diff')

export interface DiffPluginState {
  decorations: DecorationSet
  showDiff: boolean
  operations: DiffOperation[]
}

export function DiffPlugin(ops: DiffOperation[], show: boolean = true): Plugin {
  return new Plugin({
    key: diffPluginKey,

    state: {
      init(_config, instance) {
        return buildState(ops, show, instance.doc)
      },

      apply(tr, prev: DiffPluginState, _oldState, newState) {
        const meta = tr.getMeta(diffPluginKey)
        if (meta?.toggle !== undefined) {
          return buildState(prev.operations, meta.toggle, newState.doc)
        }
        if (meta?.operations) {
          return buildState(meta.operations, prev.showDiff, newState.doc)
        }
        return prev
      },
    },

    props: {
      decorations(state) {
        const pluginState = this.getState(state) as DiffPluginState | undefined
        return pluginState?.decorations || DecorationSet.empty
      },
    },
  })
}

function buildState(
  operations: DiffOperation[],
  showDiff: boolean,
  doc: import('prosemirror-model').Node,
): DiffPluginState {
  const decorations: Decoration[] = []
  let offset = 0

  if (showDiff) {
    operations.forEach((op) => {
      const length = op.value?.length || 0
      if (length === 0) return

      if (op.type === 'insert') {
        decorations.push(
          Decoration.inline(offset, offset + length, {
            class: 'diff-insert',
            style: 'background-color: rgba(16, 185, 129, 0.15); border-bottom: 2px solid var(--color-cta);',
          }),
        )
      } else if (op.type === 'delete') {
        decorations.push(
          Decoration.inline(offset, offset + length, {
            class: 'diff-delete',
            style: 'text-decoration: line-through; color: var(--color-danger); background-color: rgba(239, 68, 68, 0.1);',
          }),
        )
      } else if (op.type === 'replace') {
        decorations.push(
          Decoration.inline(offset, offset + length, {
            class: 'diff-replace',
            style: 'text-decoration: underline wavy var(--color-warning); text-underline-offset: 3px; background-color: rgba(245, 158, 11, 0.1);',
          }),
        )
      }

      offset += length
    })
  }

  return {
    decorations: DecorationSet.create(doc, decorations),
    showDiff,
    operations,
  }
}
