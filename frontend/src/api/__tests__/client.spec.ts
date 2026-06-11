import { describe, it, expect, vi, beforeEach } from 'vitest'

const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

describe('API client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('adds auth token to requests from localStorage', async () => {
    localStorageMock.getItem.mockImplementation((key: string) => {
      if (key === 'auth_token') return 'test-token'
      return null
    })

    const { default: apiClient } = await import('@/api/client')

    const config: any = { headers: {} }
    const handler = (apiClient.interceptors.request as any).handlers[0]
    handler.fulfilled(config)

    expect(config.headers.Authorization).toBe('Bearer test-token')
  })

  it('does not add auth header when no token exists', async () => {
    localStorageMock.getItem.mockReturnValue(null)

    const { default: apiClient } = await import('@/api/client')

    const config: any = { headers: {} }
    const handler = (apiClient.interceptors.request as any).handlers[0]
    handler.fulfilled(config)

    expect(config.headers.Authorization).toBeUndefined()
  })

  it('has the correct base URL', async () => {
    const { default: apiClient } = await import('@/api/client')
    expect(apiClient.defaults.baseURL).toBe('/api/v1')
  })

  it('has JSON content type by default', async () => {
    const { default: apiClient } = await import('@/api/client')
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json')
  })
})
