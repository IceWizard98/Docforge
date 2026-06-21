import { describe, it, expect } from 'vitest'
import { runsToContent, type GeneratedRun } from '@/composables/useProvenanceMarks'

describe('runsToContent', () => {
  it('marks sourced runs with provenance', () => {
    const runs: GeneratedRun[] = [
      { text: 'Le parti sono Acme e Beta.', provenance: { source: 'd1', chunk_id: 'c1', confidence: 0.9 }, placeholder: null },
    ]
    const nodes = runsToContent(runs)
    expect(nodes).toHaveLength(1)
    const text = nodes[0].content![0]
    expect(text.text).toContain('Acme')
    expect(text.marks![0].type).toBe('provenance')
    expect(text.marks![0].attrs!.sourceDocId).toBe('d1')
    expect(text.marks![0].attrs!.chunkId).toBe('c1')
  })

  it('marks unsourced runs as placeholder', () => {
    const runs: GeneratedRun[] = [
      { text: '[foro competente]', provenance: null, placeholder: { slot_id: 'governing_law', reason: 'non trovato' } },
    ]
    const nodes = runsToContent(runs)
    const text = nodes[0].content![0]
    expect(text.marks![0].type).toBe('placeholderMark')
    expect(text.marks![0].attrs!.slotId).toBe('governing_law')
  })

  it('mixes sourced and placeholder runs into one paragraph', () => {
    const runs: GeneratedRun[] = [
      { text: 'Sourced. ', provenance: { source: 'd1' }, placeholder: null },
      { text: '[manca]', provenance: null, placeholder: { slot_id: 'x', reason: 'r' } },
    ]
    const nodes = runsToContent(runs)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].content).toHaveLength(2)
    expect(nodes[0].content![0].marks![0].type).toBe('provenance')
    expect(nodes[0].content![1].marks![0].type).toBe('placeholderMark')
  })

  it('leaves plain runs unmarked', () => {
    const nodes = runsToContent([{ text: 'plain', provenance: null, placeholder: null }])
    expect(nodes[0].content![0].marks).toBeUndefined()
  })

  it('skips empty-text runs', () => {
    const nodes = runsToContent([{ text: '', provenance: null, placeholder: null }])
    expect(nodes[0].content).toEqual([])
  })

  it('returns empty for no runs', () => {
    expect(runsToContent([])).toEqual([])
  })
})
