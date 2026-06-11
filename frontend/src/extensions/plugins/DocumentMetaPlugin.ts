import { Plugin, PluginKey } from 'prosemirror-state'
import type { Node as PMNode } from 'prosemirror-model'

export interface DocumentMeta {
  title: string
  status: string
  version: number
  docType: string
}

export interface DocumentMetaPluginOptions {
  onMetaChange?: (meta: DocumentMeta) => void
}

export const documentMetaPluginKey = new PluginKey<DocumentMeta>('document-meta')

const DEFAULT_META: DocumentMeta = {
  title: 'Untitled Document',
  status: 'draft',
  version: 1,
  docType: 'document',
}

function extractMetaFromDoc(doc: PMNode): DocumentMeta {
  const meta = { ...DEFAULT_META }

  const firstSection = doc.content.content.find((node: PMNode) => node.type.name === 'section')
  if (firstSection) {
    const text = firstSection.textContent || ''
    if (text) {
      meta.title = text
    }
    const statusAttr = firstSection.attrs.status
    if (statusAttr) {
      meta.status = statusAttr
    }
    const versionAttr = firstSection.attrs.version
    if (versionAttr != null) {
      meta.version = Number(versionAttr)
    }
    const docTypeAttr = firstSection.attrs.docType
    if (docTypeAttr) {
      meta.docType = docTypeAttr
    }
  }

  return meta
}

export function DocumentMetaPlugin(options: DocumentMetaPluginOptions = {}): Plugin {
  return new Plugin({
    key: documentMetaPluginKey,

    state: {
      init(_config, instance) {
        return extractMetaFromDoc(instance.doc)
      },

      apply(tr, prev, _oldState, newState) {
        if (!tr.docChanged) return prev

        const meta = extractMetaFromDoc(newState.doc)
        if (
          meta.title !== prev.title ||
          meta.status !== prev.status ||
          meta.version !== prev.version ||
          meta.docType !== prev.docType
        ) {
          options.onMetaChange?.(meta)
          return meta
        }
        return prev
      },
    },
  })
}
