import { defineStore } from 'pinia'
import { extractApiError } from '@/api/client'
import { ref, computed } from 'vue'
import * as api from '@/api/client'
import type { ChatMessageResponse, ChatSessionListItem, SourceRef } from '@/types/document'
import type { ChatActionPayload } from '@/types/document'

// Local models can take minutes to produce a chat reply (especially one that
// decides to draft). A short cap aborted the request client-side while the
// backend kept working — the reply (and its draft action) was discarded, so the
// UI looked frozen. Give the request real headroom.
export const CHAT_REQUEST_TIMEOUT_MS = 240000

// Race a request against a timeout, ALWAYS clearing the timer afterwards so a won
// request doesn't leave a dangling 4-minute timer that later rejects (ignored).
function raceWithTimeout<T>(p: Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout>
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new Error('Request timed out')), CHAT_REQUEST_TIMEOUT_MS)
  })
  return Promise.race([p, timeout]).finally(() => clearTimeout(timer))
}

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

  // The model is still working when the last message is the user's and no
  // assistant reply has landed yet. Drives a reload-survivable "working" indicator
  // and the reconciliation poller (the reply is always persisted server-side, even
  // if the client request timed out).
  const awaitingReply = computed(() => {
    const last = messages.value[messages.value.length - 1]
    return !!last && last.role === 'user'
  })

  async function loadSessions(documentId: string, autoSelect = true, clearStale = true) {
    sessionLoading.value = true
    try {
      sessions.value = await api.listChatSessions(documentId)
      // If current sessionId belongs to a different document (stale from navigation),
      // reset it so autoSelect picks the first session for this document.
      // Skipped on a post-send refresh (clearStale=false): listChatSessions can
      // briefly lag behind a just-created session, and clearing here would wipe the
      // reply we just rendered (forcing the user to hard-reload to see it).
      if (clearStale && sessionId.value && !sessions.value.some(s => s.id === sessionId.value)) {
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

  // Update a message's content THROUGH the reactive array element (find returns
  // the proxy), so the change is tracked. Mutating the original pushed object
  // reference directly bypasses Vue's set-trap and won't re-render (the draft
  // spinner stayed stuck "Sto generando…" because of exactly that).
  function updateMessageContent(id: string, content: string) {
    const m = messages.value.find(x => x.id === id)
    if (m) m.content = content
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
      const response = await raceWithTimeout(api.sendMessage(sid, text, context))
      currentSources.value = (response.sources as SourceRef[]) || []
      return response as unknown as ChatMessageResponse
    } catch (e: any) {
      // On the client-side timeout, stay silent: the backend keeps working and
      // persists the reply, which the reconciliation poller will surface. Showing
      // an error banner here would be misleading.
      if (e?.message !== 'Request timed out') {
        error.value = extractApiError(e, 'Failed to send message')
      }
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
      const response = await raceWithTimeout(api.sendMessageWithAttachment(sid, text, files, context))
      currentSources.value = (response.sources as SourceRef[]) || []
      return response as unknown as ChatMessageResponse
    } catch (e: any) {
      if (e?.message !== 'Request timed out') {
        error.value = extractApiError(e, 'Failed to send message')
      }
      return null
    } finally {
      isSending.value = false
    }
  }

  return {
    sessionId, messages, sessions, currentSources, isSending, error,
    sessionLoading, currentDraftId, promoting,
    hasActiveSession, awaitingReply,
    loadSessions, selectSession, newSession, ensureSession,
    pushMessage, updateMessageContent, setSources, setSending, setError, setCurrentDraftId,
    sendMessage, sendWithFiles, renameSession, deleteSession,
  }
})
