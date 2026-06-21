import { Plugin, PluginKey } from 'prosemirror-state'
import type { Transaction } from 'prosemirror-state'
import { ReplaceStep, ReplaceAroundStep } from 'prosemirror-transform'

export interface TrackChange {
  id: string
  type: 'insert' | 'delete' | 'replace'
  from: number
  to: number
  oldText?: string
  newText?: string
  timestamp: number
  accepted: boolean
}

export const trackChangesKey = new PluginKey<TrackChange[]>('track-changes')

export function TrackChangesPlugin() {
  return new Plugin<TrackChange[]>({
    key: trackChangesKey,

    state: {
      init(): TrackChange[] {
        return []
      },
      apply(tr: Transaction, state: TrackChange[]): TrackChange[] {
        if (!tr.docChanged) return state

        const changes: TrackChange[] = [...state]

        tr.steps.forEach((step, idx) => {
          if (step instanceof ReplaceStep) {
            const stepMap = step.getMap()
            const inverted = step.invert(tr.docs[idx])
            const invMap = inverted.getMap()

            const insertedText = (step as any).slice?.content?.textBetween?.(0, (step as any).slice?.content?.size || 0, ' ') || ''
            const deletedText = (inverted as any).slice?.content?.textBetween?.(0, (inverted as any).slice?.content?.size || 0, ' ') || ''

            if (insertedText && deletedText) {
              changes.push({
                id: `tc_${Date.now()}_${changes.length}`,
                type: 'replace',
                from: step.from,
                to: step.to,
                oldText: deletedText,
                newText: insertedText,
                timestamp: Date.now(),
                accepted: false,
              })
            } else if (insertedText) {
              changes.push({
                id: `tc_${Date.now()}_${changes.length}`,
                type: 'insert',
                from: step.from,
                to: step.from,
                newText: insertedText,
                timestamp: Date.now(),
                accepted: false,
              })
            } else if (deletedText) {
              changes.push({
                id: `tc_${Date.now()}_${changes.length}`,
                type: 'delete',
                from: step.from,
                to: step.to,
                oldText: deletedText,
                timestamp: Date.now(),
                accepted: false,
              })
            }
          }
        })

        if (changes.length > 500) {
          return changes.slice(-500)
        }
        return changes
      },
    },
  })
}

export function getTrackChanges(state: any): TrackChange[] {
  return trackChangesKey.getState(state) || []
}
