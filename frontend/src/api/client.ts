import axios from 'axios'
import type {
  DocumentResponse,
  DocumentSpec,
  ChatMessageResponse,
  ChatActionPayload,
  PatchPayload,
  SourceRef,
  EditorContext,
} from '@/types/document'

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
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
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
  return {
    token: data.token || data.access_token,
    user: data.user || { id: '', email, displayName: '' },
  }
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
  return {
    token: data.token || data.access_token,
    user: data.user || { id: '', email, displayName },
  }
}

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
  const response = await apiClient.post<ChatSessionResponse>('/chat/sessions', { documentId })
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

export async function sendMessage(
  sessionId: string,
  content: string,
  context?: EditorContext,
): Promise<SendMessageResponse> {
  const response = await apiClient.post<SendMessageResponse>(`/chat/sessions/${sessionId}/messages`, {
    content,
    context,
  })
  return response.data
}

export function getStreamUrl(sessionId: string): string {
  return `/api/v1/chat/sessions/${sessionId}/stream`
}

export default apiClient
