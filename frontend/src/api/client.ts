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
  const response = await apiClient.post<DocumentResponse>('/documents', formData, {
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
