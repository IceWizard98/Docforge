import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore, CHAT_REQUEST_TIMEOUT_MS } from '../chatStore'
import type { ChatMessageResponse } from '@/types/document'
import * as api from '@/api/client'

describe('chatStore.sendMessage timeout', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('does not abort a slow local-model reply that arrives before the timeout', async () => {
    // Regression: a 60s cap aborted slow local replies, discarding the assistant
    // response (and any draft action) while the backend kept working.
    expect(CHAT_REQUEST_TIMEOUT_MS).toBeGreaterThanOrEqual(180000)

    vi.spyOn(api, 'createChatSession').mockResolvedValue({ id: 'sess_1' } as any)
    vi.spyOn(api, 'listChatSessions').mockResolvedValue([] as any)
    vi.spyOn(api, 'sendMessage').mockImplementation(
      () =>
        new Promise(resolve =>
          setTimeout(() => resolve({ id: 'a1', role: 'assistant', content: 'ok' } as any), 90000),
        ),
    )

    const store = useChatStore()
    const p = store.sendMessage('ciao', undefined, 'doc_1')
    await vi.advanceTimersByTimeAsync(90000)
    const res = await p
    expect(res?.content).toBe('ok')
  })

  it('does not set error on a client timeout (backend keeps working, poller recovers it)', async () => {
    vi.spyOn(api, 'createChatSession').mockResolvedValue({ id: 'sess_1' } as any)
    vi.spyOn(api, 'listChatSessions').mockResolvedValue([] as any)
    vi.spyOn(api, 'sendMessage').mockImplementation(() => new Promise(() => {})) // never resolves

    const store = useChatStore()
    const p = store.sendMessage('ciao', undefined, 'doc_1')
    await vi.advanceTimersByTimeAsync(CHAT_REQUEST_TIMEOUT_MS + 10)
    const res = await p

    expect(res).toBeNull()
    expect(store.error).toBeNull() // no misleading error banner on timeout
  })
})

describe('chatStore.awaitingReply', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('is true when the last message is the user (model still working)', () => {
    const store = useChatStore()
    store.pushMessage({ id: 'u1', role: 'user', content: 'ciao' } as ChatMessageResponse)
    expect(store.awaitingReply).toBe(true)
    store.pushMessage({ id: 'a1', role: 'assistant', content: 'risposta' } as ChatMessageResponse)
    expect(store.awaitingReply).toBe(false)
  })

  it('is false for an empty conversation', () => {
    const store = useChatStore()
    expect(store.awaitingReply).toBe(false)
  })
})

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

describe('chatStore.loadSessions clearStale', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('does NOT wipe just-rendered messages when clearStale=false and the session lags the list', async () => {
    // Regression: post-send refresh cleared messages if listChatSessions hadn't
    // yet returned the active session, forcing a hard reload to see the reply.
    vi.spyOn(api, 'listChatSessions').mockResolvedValue([] as any) // session not in list yet
    const store = useChatStore()
    store.sessionId = 'sess_live'
    store.pushMessage({ id: 'r1', role: 'assistant', content: 'risposta' } as ChatMessageResponse)

    await store.loadSessions('doc_1', false, false)

    expect(store.messages.find(m => m.id === 'r1')?.content).toBe('risposta')
    expect(store.sessionId).toBe('sess_live')
  })

  it('still clears a genuinely stale session when clearStale=true (navigation)', async () => {
    vi.spyOn(api, 'listChatSessions').mockResolvedValue([] as any)
    const store = useChatStore()
    store.sessionId = 'sess_other_doc'
    store.pushMessage({ id: 'x', role: 'assistant', content: 'old' } as ChatMessageResponse)

    await store.loadSessions('doc_1', false, true)

    expect(store.sessionId).toBeNull()
    expect(store.messages.length).toBe(0)
  })
})
