import axios from 'axios'
import type { AxiosError } from 'axios'
import type {
  DocumentResponse,
  DocumentSpec,
  ChatMessageResponse,
  ChatActionPayload,
  PatchPayload,
  SourceRef,
  EditorContext,
  ChatSessionListItem,
  ChatSessionDetailResponse,
} from '@/types/document'

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any
    if (!originalRequest) return Promise.reject(error)

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const response = await apiClient.post('/auth/refresh', { refresh_token: refreshToken })
          const { token } = response.data
          localStorage.setItem('auth_token', token)
          if (response.data.refresh_token) {
            localStorage.setItem('refresh_token', response.data.refresh_token)
          }
          apiClient.defaults.headers.Authorization = `Bearer ${token}`
          processQueue(null, token)
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError, null)
          localStorage.removeItem('auth_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      }

      localStorage.removeItem('auth_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export interface AuthResponse {
  token: string
  user: { id: string; email: string; displayName: string }
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await apiClient.post('/auth/login', { email, password })
  const data = response.data
  const token = data.token || data.access_token
  const user = data.user
  if (!token) throw new Error('No token in response')
  if (!user || !user.id) throw new Error('No user data in response')
  if (data.refresh_token) {
    localStorage.setItem('refresh_token', data.refresh_token)
  }
  return { token, user }
}

export async function register(
  email: string,
  password: string,
  displayName: string,
  tenantSlug: string,
): Promise<AuthResponse> {
  const response = await apiClient.post('/auth/register', {
    email,
    password,
    display_name: displayName,
    tenant_slug: tenantSlug,
  })
  const data = response.data
  const token = data.token || data.access_token
  const user = data.user
  if (!token) throw new Error('No token in response')
  if (!user || !user.id) throw new Error('No user data in response')
  if (data.refresh_token) {
    localStorage.setItem('refresh_token', data.refresh_token)
  }
  return { token, user }
}

// NOTE: JWT stored in localStorage is XSS-vulnerable.
// For production, migrate to httpOnly cookies for better security.

export async function uploadDocument(file: File): Promise<DocumentResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const response = await apiClient.post<DocumentResponse>('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const response = await apiClient.get('/documents')
  const body = response.data as { data: DocumentResponse[]; meta: object }
  return body.data
}

export async function createDocument(title: string, docType = ''): Promise<DocumentResponse> {
  const response = await apiClient.post('/documents', { title, doc_type: docType })
  return response.data as DocumentResponse
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const response = await apiClient.get<DocumentResponse>(`/documents/${id}`)
  return response.data
}

export interface ChatSessionResponse {
  id: string
  documentId: string
  messages: ChatMessageResponse[]
  createdAt: string
  updatedAt: string
}

export async function createChatSession(documentId: string): Promise<ChatSessionResponse> {
  const response = await apiClient.post<ChatSessionResponse>('/chat/sessions', { document_id: documentId })
  return response.data
}

export interface SendMessageResponse {
  id: string
  role: 'assistant'
  content: string
  actions?: ChatActionPayload[]
  patches?: PatchPayload[]
  sources?: SourceRef[]
  timestamp: string
}

function mapSource(src: any): SourceRef {
  return {
    sourceDocId: src.doc_id ?? src.sourceDocId ?? '',
    title: src.title ?? '',
    snippet: src.snippet ?? src.text ?? undefined,
    chunkId: src.chunk_id ?? src.chunkId ?? undefined,
    confidence: src.confidence ?? 0,
  }
}

export async function sendMessage(
  sessionId: string,
  content: string,
  context?: EditorContext,
): Promise<SendMessageResponse> {
  const response = await apiClient.post<SendMessageResponse>(`/chat/sessions/${sessionId}/messages`, {
    content,
    context,
  })
  const data = response.data
  if (data.sources) {
    data.sources = data.sources.map(mapSource)
  }
  return data
}

export function getStreamUrl(sessionId: string): string {
  return `/api/v1/chat/sessions/${sessionId}/stream`
}

export async function listChatSessions(documentId: string): Promise<ChatSessionListItem[]> {
  const response = await apiClient.get<{ data: ChatSessionListItem[] }>(`/chat/sessions`, {
    params: { document_id: documentId },
  })
  return response.data.data
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetailResponse> {
  const response = await apiClient.get<ChatSessionDetailResponse>(`/chat/sessions/${sessionId}`)
  const data = response.data
  if (data.messages) {
    data.messages = data.messages.map((msg: any) => ({
      ...msg,
      sources: msg.sources ? msg.sources.map(mapSource) : undefined,
    }))
  }
  return data
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/chat/sessions/${sessionId}`)
}

export async function updateChatSession(sessionId: string, title: string): Promise<void> {
  await apiClient.patch(`/chat/sessions/${sessionId}`, { title })
}

export async function sendMessageWithAttachment(
  sessionId: string,
  content: string,
  files: File[],
  context?: EditorContext,
): Promise<SendMessageResponse> {
  const formData = new FormData()
  formData.append('content', content)
  files.forEach((file) => formData.append('files', file))
  if (context) {
    formData.append('context', JSON.stringify(context))
  }
  const response = await apiClient.post<SendMessageResponse>(`/chat/sessions/${sessionId}/messages/with-files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  const data = response.data
  if (data.sources) {
    data.sources = data.sources.map(mapSource)
  }
  return data
}

export async function saveDocumentVersion(documentId: string): Promise<DocumentResponse> {
  const response = await apiClient.post(`/documents/${documentId}/versions`)
  return response.data
}

export async function diffDocumentVersion(documentId: string, v1: number, v2?: number): Promise<any> {
  const response = await apiClient.get(`/documents/${documentId}/diff`, { params: { v1, v2 } })
  return response.data
}

export async function createComment(documentId: string, content: string, threadId?: string): Promise<any> {
  const response = await apiClient.post('/comments', {
    document_id: documentId,
    content,
    thread_id: threadId,
  })
  return response.data
}

export async function listComments(documentId: string): Promise<any[]> {
  const response = await apiClient.get(`/comments/document/${documentId}`)
  return response.data
}

export async function resolveComment(commentId: string): Promise<any> {
  const response = await apiClient.patch(`/comments/${commentId}/resolve`)
  return response.data
}

export async function acceptPatchOperation(patchId: string, operationId: string): Promise<any> {
  const response = await apiClient.post(`/patches/${patchId}/operations/${operationId}/accept`)
  return response.data
}

export async function rejectPatchOperation(patchId: string, operationId: string): Promise<any> {
  const response = await apiClient.post(`/patches/${patchId}/operations/${operationId}/reject`)
  return response.data
}

export default apiClient
