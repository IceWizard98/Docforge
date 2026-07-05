export interface ProseMirrorJSON {
  type: string
  content?: ProseMirrorJSON[]
  marks?: Array<{
    type: string
    attrs?: Record<string, unknown>
  }>
  text?: string
  attrs?: Record<string, unknown>
}

export interface OutlineEntry {
  id: string
  number: string
  title: string
  status: string
  depth: number
  children?: OutlineEntry[]
}

export interface SourceRef {
  sourceDocId: string
  title: string
  snippet?: string
  chunkId?: string
  confidence: number
}

export interface ProvenanceLink {
  sourceDocId: string
  chunkId: string
  confidence: number
  text: string
}

export interface Suggestion {
  suggestionId: string
  patchSetId?: string
  sectionId?: string
  type: 'insert' | 'delete' | 'replace'
  status: 'pending' | 'accepted' | 'rejected'
  rationale?: string
  fromPos?: number
  toPos?: number
  insertedText?: string
  deletedText?: string
}

export interface Comment {
  id: string
  document_id: string
  thread_id: string | null
  section_id: string | null
  clause_id: string | null
  author: string
  content: string
  resolved: boolean
  created_at: string
}

export interface SlotStatusItem {
  slotId: string
  label: string
  status: 'filled' | 'missing' | 'ambiguous'
}

export interface ChatMessageResponse {
  id: string
  role: 'user' | 'assistant'
  content: string
  actions?: ChatActionPayload[]
  patches?: PatchPayload[]
  sources?: SourceRef[]
  intentSummary?: string | null
  slotStatus?: SlotStatusItem[]
  created_at: string
}

export interface ChatActionPayload {
  action: string
  label: string
  icon?: string | null
  payload: Record<string, unknown>
}

export interface PatchPayload {
  sectionId: string
  operations: DiffOperation[]
}

export interface DiffOperation {
  type: 'insert' | 'delete' | 'replace' | 'equal'
  value?: string
  originalText?: string
  newText?: string
  fromPos?: number
  toPos?: number
}

export interface DiffSummary {
  wordsAdded: number
  wordsRemoved: number
  wordsModified: number
  wordsChanged: number
  operations: DiffOperation[]
}

export interface DocumentResponse {
  id: string
  title: string
  doc_type: string
  status: string
  language: string
  version: number
  content?: ProseMirrorJSON
  outline?: OutlineEntry[]
  sections: Array<{
    id: string
    number: string
    title: string
    status: string
  }>
  created_at: string
  updated_at: string
}

export interface DocumentSpec {
  title: string
  docType: string
  sections?: Array<{
    number: string
    title: string
    instructions?: string
  }>
}

export interface ValidationIssue {
  type: 'error' | 'warning' | 'info'
  message: string
  path?: string
  rule?: string
}

export interface ChatSessionListItem {
  id: string
  title: string
  last_message_preview: string | null
  created_at: string
  updated_at: string
}

export interface ChatSessionDetailResponse {
  id: string
  title: string
  messages: ChatMessageResponse[]
  created_at: string
  updated_at: string
}

export interface EditorContext {
  activeSectionId: string | null
  activeClauseId: string | null
  selectedText: string | null
  mode: 'compose' | 'review'
  cursorPosition: { from: number; to: number } | null
  visibleSections: string[]
  documentVersion: number
  documentTitle: string
}
