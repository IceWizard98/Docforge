import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../chatStore'
import type { ChatMessageResponse } from '@/types/document'

describe('chatStore.updateMessageContent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('updates a pushed message content through the reactive array', () => {
    const store = useChatStore()
    const msg = {
      id: 'gen_1',
      role: 'assistant',
      content: '⏳ Sto generando…',
      created_at: new Date().toISOString(),
    } as ChatMessageResponse
    store.pushMessage(msg)

    store.updateMessageContent('gen_1', 'Documento generato e aperto.')

    expect(store.messages.find(m => m.id === 'gen_1')?.content).toBe(
      'Documento generato e aperto.',
    )
  })

  it('is a no-op for an unknown message id', () => {
    const store = useChatStore()
    store.pushMessage({ id: 'a', role: 'assistant', content: 'x' } as ChatMessageResponse)
    store.updateMessageContent('missing', 'y')
    expect(store.messages[0].content).toBe('x')
  })
})
