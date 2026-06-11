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
}))

function makeMessage(overrides: Partial<ChatMessageResponse> = {}): ChatMessageResponse {
  return {
    id: '1',
    role: 'user',
    content: 'Hello',
    timestamp: new Date().toISOString(),
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
          actions: [{ type: 'rewrite_section', label: 'Apply', payload: {} }],
        }),
      },
    })
    expect(wrapper.text()).toContain('Apply')
    const btn = wrapper.find('button')
    expect(btn.exists()).toBe(true)
  })

  it('emits action event when action button clicked', async () => {
    const action = { type: 'rewrite_section' as const, label: 'Apply', payload: {} }
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
})
