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

function safeParse(data: string) {
  try {
    return JSON.parse(data)
  } catch {
    return null
  }
}

function parseSSEStream(reader: ReadableStreamDefaultReader<Uint8Array>, decoder: TextDecoder, handlers: StreamEventHandlers) {
  let buffer = ''

  async function pump(): Promise<void> {
    const { done, value } = await reader.read()
    if (done) {
      handlers.onDone?.()
      return
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    let currentEvent = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = safeParse(line.slice(6))
        if (!data) continue

        switch (currentEvent) {
          case 'message_chunk':
            handlers.onMessageChunk?.(data.content)
            break
          case 'action_proposed': {
            const action = data as ChatActionPayload
            handlers.onActionProposed?.(action)
            break
          }
          case 'section_generated':
            handlers.onSectionGenerated?.(data)
            break
          case 'patch_proposed': {
            const patch = data as PatchPayload
            handlers.onPatchProposed?.(patch)
            break
          }
          case 'progress':
            handlers.onProgress?.(data)
            break
        }
      }
    }

    await pump()
  }

  return pump()
}

export function useChatStream() {
  const messages = ref<ChatMessageResponse[]>([])
  const isStreaming = ref(false)
  const streamError = ref<string | null>(null)
  const actions = ref<ChatActionPayload[]>([])
  const patches = ref<PatchPayload[]>([])

  let abortController: AbortController | null = null
  let retryCount = 0
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  const MAX_RETRIES = 5
  const BASE_DELAY = 1000

  async function connect(url: string, handlers: StreamEventHandlers = {}) {
    disconnect()

    isStreaming.value = true
    streamError.value = null

    const token = localStorage.getItem('auth_token')
    if (!token) {
      isStreaming.value = false
      streamError.value = 'No auth token'
      handlers.onError?.('Authentication required')
      return
    }

    abortController = new AbortController()

    try {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        signal: abortController.signal,
      })

      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status} ${response.statusText}`)
      }

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()

      await parseSSEStream(reader, decoder, {
        ...handlers,
        onDone: () => {
          isStreaming.value = false
          retryCount = 0
          handlers.onDone?.()
        },
      })
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return

      if (retryCount < MAX_RETRIES) {
        const delay = BASE_DELAY * Math.pow(2, retryCount)
        retryCount++
        retryTimer = setTimeout(() => {
          connect(url, handlers)
        }, delay)
      } else {
        isStreaming.value = false
        const msg = err instanceof Error ? err.message : 'Connection failed after retries'
        streamError.value = msg
        handlers.onError?.(msg)
      }
    }
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
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
