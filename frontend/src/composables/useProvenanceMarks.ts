// Converts backend "runs" (per-span generated text + provenance/placeholder)
// into ProseMirror node JSON with the matching marks applied per span, so
// sourced text carries the provenance mark and unsourced text the placeholder
// mark. Pure + framework-free for easy testing and reuse at insert time.

export interface RunProvenance {
  source?: string
  source_doc_id?: string
  chunk_id?: string
  confidence?: number
}

export interface RunPlaceholder {
  slot_id?: string
  reason?: string
}

export interface GeneratedRun {
  text: string
  provenance?: RunProvenance | null
  placeholder?: RunPlaceholder | null
}

interface PMMark {
  type: string
  attrs?: Record<string, unknown>
}

interface PMTextNode {
  type: 'text'
  text: string
  marks?: PMMark[]
}

interface PMParagraph {
  type: 'paragraph'
  content?: PMTextNode[]
}

function runToTextNode(run: GeneratedRun): PMTextNode | null {
  if (!run.text) return null
  const node: PMTextNode = { type: 'text', text: run.text }
  if (run.provenance) {
    node.marks = [{
      type: 'provenance',
      attrs: {
        sourceDocId: run.provenance.source_doc_id ?? run.provenance.source ?? '',
        chunkId: run.provenance.chunk_id ?? null,
        confidence: run.provenance.confidence ?? 0,
      },
    }]
  } else if (run.placeholder) {
    node.marks = [{
      type: 'placeholderMark',
      attrs: {
        slotId: run.placeholder.slot_id ?? null,
        reason: run.placeholder.reason ?? null,
      },
    }]
  }
  return node
}

/**
 * Convert generated runs to a single ProseMirror paragraph (as a one-element
 * array of nodes). Returns [] when there are no runs.
 */
export function runsToContent(runs: GeneratedRun[]): PMParagraph[] {
  if (!runs || runs.length === 0) return []
  const content: PMTextNode[] = []
  for (const run of runs) {
    const node = runToTextNode(run)
    if (node) content.push(node)
  }
  return [{ type: 'paragraph', content }]
}
