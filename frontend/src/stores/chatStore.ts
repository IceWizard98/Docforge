import { defineStore } from 'pinia'
import { extractApiError } from '@/api/client'
import { ref, computed } from 'vue'
import * as api from '@/api/client'
import type { ChatMessageResponse, ChatSessionListItem, SourceRef } from '@/types/document'
import type { ChatActionPayload } from '@/types/document'

export const useChatStore = defineStore('chat', () => {
  const sessionId = ref<string | null>(null)
  const messages = ref<ChatMessageResponse[]>([])
  const sessions = ref<ChatSessionListItem[]>([])
  const currentSources = ref<SourceRef[]>([])
  const isSending = ref(false)
  const error = ref<string | null>(null)
  const sessionLoading = ref(false)
  const currentDraftId = ref<string | null>(null)
  const promoting = ref(false)
  const hasActiveSession = computed(() => sessionId.value !== null)

  async function loadSessions(documentId: string, autoSelect = true) {
    sessionLoading.value = true
    try {
      sessions.value = await api.listChatSessions(documentId)
      // If current sessionId belongs to a different document (stale from navigation),
      // reset it so autoSelect picks the first session for this document
      if (sessionId.value && !sessions.value.some(s => s.id === sessionId.value)) {
        sessionId.value = null
        messages.value = []
        currentSources.value = []
      }
      if (autoSelect && sessions.value.length > 0 && !sessionId.value) {
        await selectSession(sessions.value[0].id)
      }
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to load sessions')
    } finally {
      sessionLoading.value = false
    }
  }

  async function selectSession(id: string) {
    sessionLoading.value = true
    error.value = null
    try {
      const session = await api.getChatSession(id)
      sessionId.value = session.id
      messages.value = session.messages || []
      const lastAssistant = [...messages.value].reverse().find(m => m.role === 'assistant')
      currentSources.value = (lastAssistant?.sources as SourceRef[]) || []
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to load session')
    } finally {
      sessionLoading.value = false
    }
  }

  function setCurrentDraftId(id: string | null) {
    currentDraftId.value = id
  }

  function newSession() {
    sessionId.value = null
    messages.value = []
    currentSources.value = []
    error.value = null
    currentDraftId.value = null
  }

  async function ensureSession(documentId?: string): Promise<string | null> {
    if (sessionId.value) return sessionId.value
    if (!documentId) return null
    sessionLoading.value = true
    try {
      const session = await api.createChatSession(documentId)
      sessionId.value = session.id
      await loadSessions(documentId, false)
      return session.id
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to create session')
      return null
    } finally {
      sessionLoading.value = false
    }
  }

  function pushMessage(msg: ChatMessageResponse) {
    messages.value.push(msg)
  }

  function setSources(sources: SourceRef[]) {
    currentSources.value = sources
  }

  function setSending(val: boolean) {
    isSending.value = val
  }

  function setError(msg: string | null) {
    error.value = msg
  }

  async function renameSession(id: string, title: string): Promise<void> {
    const session = sessions.value.find(s => s.id === id)
    if (!session) return
    try {
      await api.updateChatSession(id, title)
      session.title = title
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to rename session')
    }
  }

  async function deleteSession(id: string): Promise<void> {
    try {
      await api.deleteChatSession(id)
      sessions.value = sessions.value.filter(s => s.id !== id)
      if (sessionId.value === id) {
        newSession()
      }
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to delete session')
    }
  }

  async function sendMessage(text: string, context?: any, documentId?: string): Promise<ChatMessageResponse | null> {
    if (!text.trim()) return null
    isSending.value = true
    error.value = null
    try {
      const sid = await ensureSession(documentId)
      if (!sid) { isSending.value = false; return null }
      const response = await Promise.race([
        api.sendMessage(sid, text, context),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('Request timed out')), 60000)),
      ])
      currentSources.value = (response.sources as SourceRef[]) || []
      return response as unknown as ChatMessageResponse
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to send message')
      return null
    } finally {
      isSending.value = false
    }
  }

  async function sendWithFiles(text: string, files: File[], context?: any, documentId?: string): Promise<ChatMessageResponse | null> {
    if (!text.trim() && files.length === 0) return null
    isSending.value = true
    error.value = null
    try {
      const sid = await ensureSession(documentId)
      if (!sid) { isSending.value = false; return null }
      const response = await Promise.race([
        api.sendMessageWithAttachment(sid, text, files, context),
        new Promise<never>((_, reject) => setTimeout(() => reject(new Error('Request timed out')), 60000)),
      ])
      currentSources.value = (response.sources as SourceRef[]) || []
      return response as unknown as ChatMessageResponse
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to send message')
      return null
    } finally {
      isSending.value = false
    }
  }

  return {
    sessionId, messages, sessions, currentSources, isSending, error,
    sessionLoading, currentDraftId, promoting,
    hasActiveSession,
    loadSessions, selectSession, newSession, ensureSession,
    pushMessage, setSources, setSending, setError, setCurrentDraftId,
    sendMessage, sendWithFiles, renameSession, deleteSession,
  }
})
