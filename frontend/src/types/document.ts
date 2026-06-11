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
  chunkId?: string
  text?: string
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
  type: 'insert' | 'delete' | 'replace'
  status: 'pending' | 'accepted' | 'rejected'
  rationale?: string
  fromPos?: number
  toPos?: number
  insertedText?: string
  deletedText?: string
}

export interface Comment {
  commentId: string
  threadId: string
  author: string
  text: string
  resolved: boolean
  createdAt: string
  replies: CommentReply[]
}

export interface CommentReply {
  replyId: string
  author: string
  text: string
  createdAt: string
}

export interface ChatMessageResponse {
  id: string
  role: 'user' | 'assistant'
  content: string
  actions?: ChatActionPayload[]
  patches?: PatchPayload[]
  sources?: SourceRef[]
  timestamp: string
}

export interface ChatActionPayload {
  type: 'create_section' | 'rewrite_section' | 'suggest_change' | 'insert_clause'
  label: string
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
  status: string
  version: number
  sections: Array<{
    id: string
    number: string
    title: string
    status: string
  }>
  content?: ProseMirrorJSON
  createdAt: string
  updatedAt: string
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
