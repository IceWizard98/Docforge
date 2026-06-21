import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import type { ChatMessageResponse } from '@/types/document'

vi.mock('@lucide/vue', () => ({
  Bot: { template: '<span class="lucide-bot" />' },
  User: { template: '<span class="lucide-user" />' },
  Check: { template: '<span class="lucide-check" />' },
  X: { template: '<span class="lucide-x" />' },
  ExternalLink: { template: '<span class="lucide-external-link" />' },
  Info: { template: '<span class="lucide-info" />' },
  AlertTriangle: { template: '<span class="lucide-alert-triangle" />' },
}))

function makeMessage(overrides: Partial<ChatMessageResponse> = {}): ChatMessageResponse {
  return {
    id: '1',
    role: 'user',
    content: 'Hello',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

describe('ChatMessage.vue', () => {
  it('renders user message correctly', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'user', content: 'Hello from user' }) },
    })
    expect(wrapper.text()).toContain('Hello from user')
  })

  it('renders assistant message correctly', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'assistant', content: 'Hello from assistant' }) },
    })
    expect(wrapper.text()).toContain('Hello from assistant')
  })

  it('renders markdown in assistant messages', async () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'assistant', content: '**bold** and *italic*' }) },
    })
    await nextTick()
    expect(wrapper.html()).toContain('<strong>')
    expect(wrapper.html()).toContain('<em>')
  })

  it('renders code blocks in assistant messages', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: makeMessage({
          role: 'assistant',
          content: '```js\nconst x = 1\n```',
        }),
      },
    })
    await nextTick()
    expect(wrapper.find('code').exists()).toBe(true)
    expect(wrapper.text()).toContain('const x = 1')
  })

  it('handles empty content gracefully', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'assistant', content: '' }) },
    })
    expect(wrapper.exists()).toBe(true)
  })

  it('shows action buttons when actions are present', async () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: makeMessage({
          role: 'assistant',
          content: 'Apply this change?',
          actions: [{ action: 'suggest_patches', label: 'Apply', payload: {} }],
        }),
      },
    })
    expect(wrapper.text()).toContain('Apply')
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
  })

  it('emits action event when action button clicked', async () => {
    const action = { action: 'suggest_patches', label: 'Apply', payload: {} }
    const wrapper = mount(ChatMessage, {
      props: {
        message: makeMessage({
          role: 'assistant',
          content: 'Apply this?',
          actions: [action],
        }),
      },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('action')).toBeTruthy()
    expect(wrapper.emitted('action')![0]).toEqual([action])
  })

  it('renders user message without markdown processing', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'user', content: '**raw text**' }) },
    })
    expect(wrapper.text()).toContain('**raw text**')
    expect(wrapper.html()).not.toContain('<strong>')
  })

  it('shows intent summary when present', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: makeMessage({
          role: 'assistant',
          content: 'ok',
          intentSummary: 'Ho capito: Contratto. Fonti: nda.pdf.',
        }),
      },
    })
    expect(wrapper.text()).toContain('Ho capito: Contratto')
  })

  it('lists only missing/ambiguous slots', () => {
    const wrapper = mount(ChatMessage, {
      props: {
        message: makeMessage({
          role: 'assistant',
          content: 'ok',
          slotStatus: [
            { slotId: 'parties', label: 'Parti', status: 'filled' },
            { slotId: 'object', label: 'Oggetto', status: 'missing' },
            { slotId: 'law', label: 'Legge', status: 'ambiguous' },
          ],
        }),
      },
    })
    expect(wrapper.text()).toContain('Informazioni mancanti')
    expect(wrapper.text()).toContain('Oggetto')
    expect(wrapper.text()).toContain('Legge')
    expect(wrapper.text()).not.toContain('Parti')
  })

  it('renders nothing extra when transparency fields absent', () => {
    const wrapper = mount(ChatMessage, {
      props: { message: makeMessage({ role: 'assistant', content: 'plain' }) },
    })
    expect(wrapper.text()).not.toContain('Informazioni mancanti')
    expect(wrapper.text()).not.toContain('Ho capito')
  })
})
