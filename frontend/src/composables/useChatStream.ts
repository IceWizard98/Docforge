import { ref, onBeforeUnmount } from 'vue'
import type { ChatMessageResponse, ChatActionPayload, PatchPayload } from '@/types/document'

interface StreamEventHandlers {
  onMessageChunk?: (chunk: string) => void
  onActionProposed?: (action: ChatActionPayload) => void
  onSectionGenerated?: (section: { sectionId: string; content: string }) => void
  onPatchProposed?: (patch: PatchPayload) => void
  onProgress?: (progress: { current: number; total: number }) => void
  onDone?: () => void
  onError?: (error: string) => void
}

export function useChatStream() {
  const messages = ref<ChatMessageResponse[]>([])
  const isStreaming = ref(false)
  const streamError = ref<string | null>(null)
  const actions = ref<ChatActionPayload[]>([])
  const patches = ref<PatchPayload[]>([])

  let eventSource: EventSource | null = null
  let retryCount = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  const MAX_RETRIES = 5
  const BASE_DELAY = 1000

  function connect(url: string, handlers: StreamEventHandlers = {}) {
    disconnect()

    isStreaming.value = true
    streamError.value = null

    eventSource = new EventSource(url)

    eventSource.addEventListener('message_chunk', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      handlers.onMessageChunk?.(data.content)
    })

    eventSource.addEventListener('action_proposed', (e: MessageEvent) => {
      const action = JSON.parse(e.data) as ChatActionPayload
      actions.value.push(action)
      handlers.onActionProposed?.(action)
    })

    eventSource.addEventListener('section_generated', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      handlers.onSectionGenerated?.(data)
    })

    eventSource.addEventListener('patch_proposed', (e: MessageEvent) => {
      const patch = JSON.parse(e.data) as PatchPayload
      patches.value.push(patch)
      handlers.onPatchProposed?.(patch)
    })

    eventSource.addEventListener('progress', (e: MessageEvent) => {
      const data = JSON.parse(e.data)
      handlers.onProgress?.(data)
    })

    eventSource.addEventListener('done', () => {
      isStreaming.value = false
      retryCount = 0
      handlers.onDone?.()
    })

    eventSource.addEventListener('error', (e: MessageEvent) => {
      if (e.data) {
        const data = JSON.parse(e.data)
        streamError.value = data.error || 'Stream error'
        handlers.onError?.(data.error || 'Stream error')
      }
    })

    eventSource.onerror = () => {
      eventSource?.close()
      if (retryCount < MAX_RETRIES) {
        const delay = BASE_DELAY * Math.pow(2, retryCount)
        retryCount++
        retryTimer = setTimeout(() => {
          connect(url, handlers)
        }, delay)
      } else {
        isStreaming.value = false
        streamError.value = 'Connection failed after retries'
        handlers.onError?.('Connection failed after retries')
      }
    }
  }

  function disconnect() {
    eventSource?.close()
    eventSource = null
    if (retryTimer) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    isStreaming.value = false
    retryCount = 0
  }

  function addMessage(msg: ChatMessageResponse) {
    messages.value.push(msg)
  }

  function clearMessages() {
    messages.value = []
    actions.value = []
    patches.value = []
    streamError.value = null
  }

  onBeforeUnmount(() => {
    disconnect()
  })

  return {
    messages,
    isStreaming,
    streamError,
    actions,
    patches,
    connect,
    disconnect,
    addMessage,
    clearMessages,
  }
}
