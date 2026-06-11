<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { Send, Bot, Loader2 } from '@lucide/vue'
import ChatMessage from './ChatMessage.vue'
import SourceContextPanel from './SourceContextPanel.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { useChatStream } from '@/composables/useChatStream'
import { useEditorContext } from '@/composables/useEditorContext'
import { sendMessage, createChatSession, getStreamUrl } from '@/api/client'
import type { ChatActionPayload } from '@/types/document'
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

const { context } = useEditorContext(props.editor)
const {
  messages,
  isStreaming,
  streamError,
  actions,
  patches,
  connect,
  disconnect,
  addMessage,
  clearMessages,
} = useChatStream()

const messagesContainer = ref<HTMLElement | null>(null)

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
    connect(getStreamUrl(session.id), {
      onMessageChunk: (chunk) => {
        messages.value = messages.value.map((msg, idx) => {
          if (idx === messages.value.length - 1 && msg.role === 'assistant') {
            return { ...msg, content: msg.content + chunk }
          }
          return msg
        })
      },
    })
    return session.id
  } finally {
    sessionLoading.value = false
  }
}

async function send() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value || sessionLoading.value) return

  inputText.value = ''

  addMessage({
    id: `msg_${Date.now()}`,
    role: 'user',
    content: text,
    timestamp: new Date().toISOString(),
  })

  await nextTick()
  messagesEndRef.value?.scrollIntoView({ behavior: 'smooth' })

  try {
    const sid = await ensureSession()
    if (!sid) return

    const response = await sendMessage(sid, text, context.value)

    if (response.role === 'assistant') {
      addMessage({
        id: response.id,
        role: 'assistant',
        content: response.content,
        actions: response.actions,
        patches: response.patches,
        sources: response.sources,
        timestamp: response.timestamp,
      })
    }
  } catch (err: any) {
    streamError.value = err?.response?.data?.detail || err.message || 'Failed to send message'
  }
}

function handleAction(action: ChatActionPayload) {
  if (!sessionId.value) return
  const description = typeof action.payload?.description === 'string' ? action.payload.description : `Apply action: ${action.label}`
  sendMessage(sessionId.value, description, context.value).catch(() => {})
}

function handleRetry() {
  streamError.value = null
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <Bot class="w-4 h-4 text-primary" />
      <h2 class="text-sm font-semibold text-foreground">Assistant</h2>
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-3 space-y-4">
      <!-- Empty state -->
      <EmptyState
        v-if="messages.length === 0 && !isStreaming && !streamError"
        :icon="MessageSquare"
        title="Usa la chat per descrivere cosa vuoi creare o modificare"
      />

      <!-- Loading skeleton -->
      <LoadingSpinner v-if="isStreaming && messages.length === 0" />

      <!-- Error state -->
      <ErrorMessage
        v-if="streamError && messages.length === 0"
        :message="streamError"
        retry-label="Riprova"
        @retry="handleRetry"
      />

      <!-- Message list -->
      <template v-for="msg in messages" :key="msg.id">
        <ChatMessage :message="msg" @action="handleAction" />
      </template>

      <!-- Streaming indicator -->
      <div v-if="isStreaming && messages.length > 0" class="flex items-center gap-2 text-xs text-foreground/40 pl-10">
        <Loader2 class="w-3 h-3 animate-spin" />
        <span>Sta scrivendo...</span>
      </div>

      <div ref="messagesEndRef" />
    </div>

    <!-- Source context -->
    <SourceContextPanel :sources="messages[messages.length - 1]?.sources || []" />

    <!-- Input area -->
    <div class="border-t border-primary/10 p-3">
      <div class="flex gap-2">
        <textarea
          v-model="inputText"
          class="flex-1 min-h-[36px] max-h-[120px] px-3 py-2 text-sm bg-surface border border-primary/10 rounded-md text-foreground placeholder-foreground/40 resize-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
          placeholder="Descrivi cosa vuoi creare o modificare..."
          rows="1"
          :disabled="isStreaming"
          aria-label="Messaggio per l'assistente"
          @keydown="handleKeydown"
        />
        <button
          class="self-end p-2 rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :disabled="!inputText.trim() || isStreaming"
          aria-label="Invia messaggio"
          @click="send"
        >
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>
  </div>
</template>
