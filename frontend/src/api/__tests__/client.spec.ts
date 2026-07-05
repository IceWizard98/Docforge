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

  it('updateProfile PATCHes /auth/me and maps display_name → displayName', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'patch').mockResolvedValue({
      data: { id: 'u1', email: 'a@b.c', display_name: 'Nuovo Nome', role: 'user' },
    } as any)
    const user = await mod.updateProfile('Nuovo Nome')
    expect(spy).toHaveBeenCalledWith('/auth/me', { display_name: 'Nuovo Nome' })
    expect(user).toEqual({ id: 'u1', email: 'a@b.c', displayName: 'Nuovo Nome', role: 'user' })
  })

  it('listDocumentVersions GETs versions and maps snake_case → camelCase', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'get').mockResolvedValue({
      data: [{ version: 2, created_at: '2026-01-01T10:00:00', created_by: 'u1' }],
    } as any)
    const versions = await mod.listDocumentVersions('doc1')
    expect(spy).toHaveBeenCalledWith('/documents/doc1/versions')
    expect(versions).toEqual([{ version: 2, createdAt: '2026-01-01T10:00:00', createdBy: 'u1' }])
  })

  it('restoreDocumentVersion POSTs the restore endpoint', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({ data: { id: 'doc1' } } as any)
    const doc = await mod.restoreDocumentVersion('doc1', 3)
    expect(spy).toHaveBeenCalledWith('/documents/doc1/versions/3/restore')
    expect(doc).toEqual({ id: 'doc1' })
  })

  it('listDocumentSources GETs the document sources with excluded flags', async () => {
    const mod = await import('@/api/client')
    const rows = [{ id: 's1', filename: 'a.pdf', excluded: true }]
    const spy = vi.spyOn(mod.default, 'get').mockResolvedValue({ data: rows } as any)
    const out = await mod.listDocumentSources('doc1')
    expect(spy).toHaveBeenCalledWith('/documents/doc1/sources')
    expect(out).toEqual(rows)
  })

  it('excludeDocumentSource PUTs the exclusion endpoint', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'put').mockResolvedValue({ data: undefined } as any)
    await mod.excludeDocumentSource('doc1', 's1')
    expect(spy).toHaveBeenCalledWith('/documents/doc1/sources/s1/exclusion')
  })

  it('includeDocumentSource DELETEs the exclusion endpoint', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'delete').mockResolvedValue({ data: undefined } as any)
    await mod.includeDocumentSource('doc1', 's1')
    expect(spy).toHaveBeenCalledWith('/documents/doc1/sources/s1/exclusion')
  })

  it('reindexAllSources POSTs the corpus reindex endpoint', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({ data: { status: 'reindexing', count: 3 } } as any)
    const out = await mod.reindexAllSources()
    expect(spy).toHaveBeenCalledWith('/sources/reindex-all')
    expect(out).toEqual({ status: 'reindexing', count: 3 })
  })

  it('validateDocument POSTs the validation endpoint and returns the report', async () => {
    const mod = await import('@/api/client')
    const report = { document_id: 'doc1', version: 2, passed: true, score: 0.9, issues: [], summary: '' }
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({ data: report } as any)
    const out = await mod.validateDocument('doc1')
    expect(spy).toHaveBeenCalledWith('/documents/doc1/validate')
    expect(out).toEqual(report)
  })

  it('createExport POSTs the export endpoint with the format', async () => {
    const mod = await import('@/api/client')
    const job = { id: 'e1', document_id: 'doc1', format: 'pdf', status: 'processing' }
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({ data: job } as any)
    const out = await mod.createExport('doc1', 'pdf')
    expect(spy).toHaveBeenCalledWith('/exports/documents/doc1/export', { format: 'pdf' })
    expect(out).toEqual(job)
  })

  it('createExport includes template_id when a template is chosen', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({ data: {} } as any)
    await mod.createExport('doc1', 'docx', 'tpl-9')
    expect(spy).toHaveBeenCalledWith('/exports/documents/doc1/export', {
      format: 'docx',
      template_id: 'tpl-9',
    })
  })

  it('getExport GETs the export status', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'get').mockResolvedValue({ data: { id: 'e1', status: 'completed' } } as any)
    const out = await mod.getExport('e1')
    expect(spy).toHaveBeenCalledWith('/exports/e1')
    expect(out.status).toBe('completed')
  })

  it('downloadExport GETs the download endpoint as a blob', async () => {
    const mod = await import('@/api/client')
    const blob = new Blob(['x'])
    const spy = vi.spyOn(mod.default, 'get').mockResolvedValue({ data: blob } as any)
    const out = await mod.downloadExport('e1')
    expect(spy).toHaveBeenCalledWith('/exports/e1/download', { responseType: 'blob' })
    expect(out).toBe(blob)
  })

  it('listTemplates unwraps a bare array and maps has_file → hasFile', async () => {
    const mod = await import('@/api/client')
    vi.spyOn(mod.default, 'get').mockResolvedValue({
      data: [{ id: 't1', name: 'T', has_file: true }],
    } as any)
    const out = await mod.listTemplates()
    expect(out.data).toEqual([{ id: 't1', name: 'T', has_file: true, hasFile: true }])
  })

  it('uploadTemplate POSTs multipart FormData and maps has_file → hasFile', async () => {
    const mod = await import('@/api/client')
    const spy = vi.spyOn(mod.default, 'post').mockResolvedValue({
      data: { id: 't2', name: 'Doc', has_file: true },
    } as any)
    const file = new File(['x'], 'tpl.docx')
    const out = await mod.uploadTemplate(file, { name: 'Doc', docType: 'nda' })
    const [url, body, config] = spy.mock.calls[0]
    expect(url).toBe('/templates/upload')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('name')).toBe('Doc')
    expect((body as FormData).get('doc_type')).toBe('nda')
    expect((config as any).headers['Content-Type']).toBe('multipart/form-data')
    expect(out.hasFile).toBe(true)
  })
})
