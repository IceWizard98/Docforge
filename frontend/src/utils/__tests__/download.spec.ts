import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { saveBlob } from '../download'

describe('saveBlob', () => {
  beforeEach(() => {
    // jsdom lacks these; stub them
    ;(URL as any).createObjectURL = vi.fn(() => 'blob:mock')
    ;(URL as any).revokeObjectURL = vi.fn()
  })
  afterEach(() => vi.restoreAllMocks())

  it('creates an anchor with the given filename, clicks it, and revokes the url', () => {
    const click = vi.fn()
    const anchor = { href: '', download: '', click, remove: vi.fn() } as any
    const createEl = vi.spyOn(document, 'createElement').mockReturnValue(anchor)
    const append = vi.spyOn(document.body, 'appendChild').mockImplementation((n: any) => n)

    const blob = new Blob(['x'], { type: 'text/plain' })
    saveBlob(blob, 'report.docx')

    expect(createEl).toHaveBeenCalledWith('a')
    expect(anchor.download).toBe('report.docx')
    expect(anchor.href).toBe('blob:mock')
    expect(append).toHaveBeenCalledWith(anchor)
    expect(click).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock')
  })
})
