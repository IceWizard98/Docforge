<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { Send, Bot, Loader2, Paperclip, Plus, ChevronDown, Pencil } from '@lucide/vue'
import ChatMessage from './ChatMessage.vue'
import SourceContextPanel from './SourceContextPanel.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { useEditorContext } from '@/composables/useEditorContext'
import { sendMessage, createChatSession, listChatSessions, getChatSession, deleteChatSession, updateChatSession, sendMessageWithAttachment } from '@/api/client'
import type { ChatActionPayload, PatchPayload, SourceRef, ChatSessionListItem } from '@/types/document'
import type { Editor } from '@tiptap/core'
import { MessageSquare } from '@lucide/vue'

const props = defineProps<{
  editor: { value: Editor | null }
  documentId: string
}>()

const inputText = ref('')
const messagesEndRef = ref<HTMLElement | null>(null)
const sessionId = ref<string | null>(null)
const sessionLoading = ref(false)
const isSending = ref(false)
const error = ref<string | null>(null)

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  actions?: ChatActionPayload[]
  patches?: PatchPayload[]
  sources?: SourceRef[]
  timestamp: string
}

const messages = ref<ChatMessage[]>([])

const sessions = ref<ChatSessionListItem[]>([])
const sessionsOpen = ref(false)
const sessionsLoading = ref(false)
const renamingSessionId = ref<string | null>(null)
const renameText = ref('')

const attachedFiles = ref<File[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)

const { context } = useEditorContext(props.editor)

const messagesContainer = ref<HTMLElement | null>(null)

const activeSessionTitle = computed(() => {
  if (!sessionId.value) return ''
  const s = sessions.value.find((s) => s.id === sessionId.value)
  return s?.title || 'Chat'
})

watch(messages, async () => {
  await nextTick()
  if (!messagesContainer.value) return
  const el = messagesContainer.value
  const threshold = 100
  const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  if (isNearBottom) {
    messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
  }
})

async function ensureSession() {
  if (sessionId.value) return sessionId.value
  sessionLoading.value = true
  try {
    const session = await createChatSession(props.documentId)
    sessionId.value = session.id
    await loadSessions()
    return session.id
  } finally {
    sessionLoading.value = false
  }
}

async function sendMessageInternal(text: string) {
  const sid = await ensureSession()
  if (!sid) throw new Error('No session')

  if (attachedFiles.value.length > 0) {
    const response = await sendMessageWithAttachment(sid, text, attachedFiles.value, context.value)
    attachedFiles.value = []
    return response
  }

  return sendMessage(sid, text, context.value)
}

async function send() {
  const text = inputText.value.trim()
  if ((!text && attachedFiles.value.length === 0) || isSending.value || sessionLoading.value) return

  inputText.value = ''

  messages.value.push({
    id: `msg_${Date.now()}`,
    role: 'user',
    content: text || '(file attachement)',
    timestamp: new Date().toISOString(),
  })

  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })

  isSending.value = true
  error.value = null
  try {
    const response = await sendMessageInternal(text)
    if (response.role === 'assistant') {
      messages.value.push({
        id: response.id,
        role: 'assistant',
        content: response.content,
        actions: response.actions as ChatActionPayload[] | undefined,
        timestamp: response.timestamp,
      })
    }
    await loadSessions()
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || 'Failed to send message'
  } finally {
    isSending.value = false
  }

  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })
}

async function handleAction(action: ChatActionPayload) {
  isSending.value = true
  error.value = null

  let contextMessage = ''
  const actionType = (action.type as string)
  if (actionType === 'suggest_draft') {
    contextMessage = 'Vorrei che tu generassi una bozza di documento per me.'
  } else if (actionType === 'suggest_patches') {
    contextMessage = 'Vorrei che tu proponessi delle modifiche al documento.'
  } else if (actionType === 'validate') {
    contextMessage = 'Vorrei che tu validassi il documento.'
  } else {
    contextMessage = action.label || `Esegui azione: ${actionType}`
  }

  messages.value.push({
    id: `action_${Date.now()}`,
    role: 'user',
    content: contextMessage,
    timestamp: new Date().toISOString(),
  })

  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })

  try {
    const response = await sendMessageInternal(contextMessage)
    if (response.role === 'assistant') {
      messages.value.push({
        id: response.id,
        role: 'assistant',
        content: response.content,
        actions: response.actions as ChatActionPayload[] | undefined,
        timestamp: response.timestamp,
      })
    }
    await loadSessions()
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || 'Failed to send message'
  } finally {
    isSending.value = false
  }
}

function handleRetry() {
  error.value = null
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

// Session management
async function loadSessions() {
  sessionsLoading.value = true
  try {
    sessions.value = await listChatSessions(props.documentId)
  } catch {
    // silently fail
  } finally {
    sessionsLoading.value = false
  }
}

async function selectSession(sid: string) {
  sessionsOpen.value = false
  if (sid === sessionId.value) return
  sessionLoading.value = true
  error.value = null
  try {
    const detail = await getChatSession(sid)
    sessionId.value = detail.id
    messages.value = detail.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      actions: m.actions as ChatActionPayload[] | undefined,
      patches: m.patches as PatchPayload[] | undefined,
      sources: m.sources as SourceRef[] | undefined,
      timestamp: m.timestamp,
    }))
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err.message || 'Failed to load session'
  } finally {
    sessionLoading.value = false
  }
}

async function newSession() {
  sessionsOpen.value = false
  sessionId.value = null
  messages.value = []
  attachedFiles.value = []
  error.value = null
  await ensureSession()
}

function startRename(sid: string, currentTitle: string) {
  renamingSessionId.value = sid
  renameText.value = currentTitle || ''
}

async function finishRename(sid: string) {
  const title = renameText.value.trim()
  if (title && title !== sessions.value.find((s) => s.id === sid)?.title) {
    try {
      await updateChatSession(sid, title)
      await loadSessions()
    } catch {
      // silently fail
    }
  }
  renamingSessionId.value = null
  renameText.value = ''
}

function cancelRename() {
  renamingSessionId.value = null
  renameText.value = ''
}

// File attachment
function openFilePicker() {
  fileInputRef.value?.click()
}

function handleFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  attachedFiles.value = [...attachedFiles.value, ...files]
  input.value = ''
}

function removeFile(index: number) {
  attachedFiles.value.splice(index, 1)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(() => {
  loadSessions()
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header with session selector -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <Bot class="w-4 h-4 text-primary flex-shrink-0" />
      <div class="relative flex-1 min-w-0">
        <button
          class="w-full flex items-center gap-1 text-sm font-semibold text-foreground truncate hover:text-primary transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="sessionsOpen = !sessionsOpen"
        >
          <span class="truncate">{{ activeSessionTitle || 'Assistant' }}</span>
          <ChevronDown class="w-3 h-3 flex-shrink-0" />
        </button>

        <!-- Session dropdown -->
        <div
          v-if="sessionsOpen"
          class="absolute top-full left-0 right-0 mt-1 bg-white border border-primary/10 rounded-lg shadow-lg z-20 max-h-60 overflow-y-auto"
        >
          <div class="p-1">
            <button
              class="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground hover:bg-primary/8 rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              @click="newSession"
            >
              <Plus class="w-3.5 h-3.5" />
              New Chat
            </button>
            <div class="border-t border-primary/5 my-1" />
            <div v-if="sessionsLoading" class="flex items-center justify-center py-3">
              <Loader2 class="w-4 h-4 animate-spin text-foreground/40" />
            </div>
            <div
              v-for="s in sessions"
              :key="s.id"
              class="group relative"
            >
              <button
                class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                :class="s.id === sessionId ? 'bg-primary/10 text-primary' : 'text-foreground hover:bg-primary/8'"
                @click="selectSession(s.id)"
                @dblclick="startRename(s.id, s.title)"
              >
                <div class="flex-1 min-w-0">
                  <template v-if="renamingSessionId === s.id">
                    <input
                      v-model="renameText"
                      class="w-full text-sm bg-surface border border-primary/20 rounded px-1 py-0.5 text-foreground focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
                      @click.stop
                      @keydown.enter.stop="finishRename(s.id)"
                      @keydown.escape.stop="cancelRename"
                      @blur="finishRename(s.id)"
                    />
                  </template>
                  <template v-else>
                    <p class="text-sm truncate">{{ s.title || 'Untitled' }}</p>
                    <p v-if="s.lastMessagePreview" class="text-[11px] text-foreground/40 truncate mt-0.5">
                      {{ s.lastMessagePreview }}
                    </p>
                  </template>
                </div>
                <Pencil
                  class="w-3 h-3 text-foreground/30 hover:text-foreground/60 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click.stop="startRename(s.id, s.title)"
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      <!-- Empty state -->
      <EmptyState
        v-if="messages.length === 0 && !isSending && !error && !sessionLoading"
        :icon="MessageSquare"
        title="Usa la chat per descrivere cosa vuoi creare o modificare"
      />

      <!-- Loading skeleton -->
      <LoadingSpinner v-if="(isSending || sessionLoading) && messages.length === 0" />

      <!-- Error state -->
      <ErrorMessage
        v-if="error && messages.length === 0"
        :message="error"
        retry-label="Riprova"
        @retry="handleRetry"
      />

      <!-- Message list -->
      <template v-for="msg in messages" :key="msg.id">
        <ChatMessage :message="msg" @action="handleAction" />
      </template>

      <!-- Sending indicator -->
      <div v-if="isSending && messages.length > 0" class="flex items-center gap-2 text-xs text-foreground/40 pl-10">
        <Loader2 class="w-3 h-3 animate-spin" />
        <span>Sta scrivendo...</span>
      </div>

      <div ref="messagesEndRef" />
    </div>

    <!-- Source context -->
    <SourceContextPanel :sources="[]" />

    <!-- Input area -->
    <div class="border-t border-primary/10 p-3">
      <!-- File attachment chips -->
      <div v-if="attachedFiles.length > 0" class="flex flex-wrap gap-2 mb-2">
        <div
          v-for="(file, idx) in attachedFiles"
          :key="idx"
          class="inline-flex items-center gap-1.5 px-2 py-1 text-xs bg-primary/5 border border-primary/10 rounded-md"
        >
          <Paperclip class="w-3 h-3 text-primary/60" />
          <span class="text-foreground/70 truncate max-w-[120px]">{{ file.name }}</span>
          <span class="text-foreground/40">({{ formatFileSize(file.size) }})</span>
          <button
            class="ml-1 text-foreground/40 hover:text-danger transition-colors cursor-pointer"
            @click="removeFile(idx)"
          >
            x
          </button>
        </div>
      </div>

      <div class="flex gap-2">
        <input
          ref="fileInputRef"
          type="file"
          accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
          class="hidden"
          multiple
          @change="handleFilesSelected"
        />
        <button
          class="self-end p-2 rounded-md text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          aria-label="Allega file"
          @click="openFilePicker"
        >
          <Paperclip class="w-4 h-4" />
        </button>
        <textarea
          v-model="inputText"
          class="flex-1 min-h-[36px] max-h-[120px] px-3 py-2 text-sm bg-surface border border-primary/10 rounded-md text-foreground placeholder-foreground/40 resize-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
          placeholder="Descrivi cosa vuoi creare o modificare..."
          rows="1"
          :disabled="isSending"
          aria-label="Messaggio per l'assistente"
          @keydown="handleKeydown"
        />
        <button
          class="self-end p-2 rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :disabled="(!inputText.trim() && attachedFiles.length === 0) || isSending"
          aria-label="Invia messaggio"
          @click="send"
        >
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
