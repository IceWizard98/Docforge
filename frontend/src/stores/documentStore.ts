import { defineStore } from 'pinia'
import { extractApiError } from '@/api/client'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

export interface SectionInfo {
  id: string
  number: string
  title: string
  status: string
}

export const useDocumentStore = defineStore('document', () => {
  const currentDocId = ref<string | null>(null)
  const title = ref('')
  const status = ref('draft')
  const version = ref(1)
  const content = ref<Record<string, unknown> | null>(null)
  const sections = ref<SectionInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const isSaving = ref(false)
  const lastSavedAt = ref<number | null>(null)

  const sectionCount = computed(() => sections.value.length)
  const saveStatus = computed<'saved' | 'unsaved' | 'saving'>(() => {
    if (isSaving.value) return 'saving'
    if (lastSavedAt.value) return 'saved'
    return 'unsaved'
  })

  async function fetchDocument(id: string) {
    loading.value = true
    error.value = null
    currentDocId.value = id

    try {
      const response = await apiClient.get(`/documents/${id}`)
      const data = response.data
      title.value = data.title || ''
      status.value = data.status || 'draft'
      version.value = data.version || 1
      content.value = data.content || null
      // Extract sections from ProseMirror content or outline
      // NOTE: data.outline is `[]` by default in the DB (empty array is truthy in JS),
      // so we must explicitly check for a non-empty array before using it.
      let rawSections: any[] = []
      if (data.outline && Array.isArray(data.outline) && data.outline.length > 0) {
        rawSections = data.outline
      } else if (data.content?.content) {
        const nodes = Array.isArray(data.content.content) ? data.content.content : []
        rawSections = nodes.filter((n: any) => n?.type === 'section')
      }
      sections.value = rawSections.map((s: any) => {
        // Section nodes store the title as the first heading inside their content,
        // not as a node attribute. Extract it from content as fallback.
        let title = s.title || s.attrs?.title || ''
        if (!title && s.content) {
          const contentArr = Array.isArray(s.content) ? s.content : []
          const heading = contentArr.find((n: any) => n?.type === 'heading')
          if (heading?.content) {
            const textArr = Array.isArray(heading.content) ? heading.content : []
            title = textArr.map((c: any) => c.text || '').join('')
          }
        }
        return {
          id: s.attrs?.sectionId || s.sectionId || s.id || '',
          number: s.attrs?.number || s.number || '',
          title,
          status: s.attrs?.status || s.status || 'draft',
        }
      })
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to fetch document')
    } finally {
      loading.value = false
    }
  }

  async function updateTitle(newTitle: string) {
    if (!currentDocId.value) return
    error.value = null

    try {
      await apiClient.patch(`/documents/${currentDocId.value}`, { title: newTitle })
      title.value = newTitle
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to update title')
      throw e // let the caller show a failure toast instead of a false success
    }
  }

  function setContent(json: Record<string, unknown>) {
    content.value = json
    // Extract sections from new content
    const nodes = (json?.content as any[]) || []
    const rawSections: any[] = nodes.filter((n: any) => n?.type === 'section') || []
    sections.value = rawSections.map((s: any) => {
      let title = s.attrs?.title || ''
      if (!title && s.content) {
        const contentArr = Array.isArray(s.content) ? s.content : []
        const heading = contentArr.find((n: any) => n?.type === 'heading')
        if (heading?.content) {
          const textArr = Array.isArray(heading.content) ? heading.content : []
          title = textArr.map((c: any) => c.text || '').join('')
        }
      }
      return {
        id: s.attrs?.sectionId || s.sectionId || s.id || '',
        number: s.attrs?.number || s.number || '',
        title,
        status: s.attrs?.status || s.status || 'draft',
      }
    })
  }

  async function saveContent(json: Record<string, unknown>) {
    const id = currentDocId.value
    if (!id) return
    error.value = null
    isSaving.value = true
    try {
      await apiClient.patch(`/documents/${id}`, { content: json })
      setContent(json)
      lastSavedAt.value = Date.now()
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to save content')
    } finally {
      isSaving.value = false
    }
  }

  async function updateSectionStatus(sectionId: string, newStatus: string) {
    if (!currentDocId.value || !content.value) return
    error.value = null

    try {
      // Update section status in ProseMirror content and save
      const updatedContent = { ...content.value } as Record<string, unknown>
      const nodes = updatedContent.content as Array<Record<string, unknown>> | undefined
      if (nodes && Array.isArray(nodes)) {
        for (const node of nodes) {
          const attrs = (node.attrs || {}) as Record<string, unknown>
          if (attrs.sectionId === sectionId) {
            node.attrs = { ...attrs, status: newStatus }
            break
          }
        }
      }
      await apiClient.patch(`/documents/${currentDocId.value}`, { content: updatedContent })
      content.value = updatedContent
      const idx = sections.value.findIndex((s) => s.id === sectionId)
      if (idx !== -1) {
        sections.value[idx] = { ...sections.value[idx], status: newStatus }
      }
    } catch (e: any) {
      error.value = extractApiError(e, 'Failed to update section status')
    }
  }

  return {
    currentDocId,
    title,
    status,
    version,
    content,
    sections,
    loading,
    error,
    sectionCount,
    isSaving,
    lastSavedAt,
    saveStatus,
    fetchDocument,
    updateTitle,
    updateSectionStatus,
    saveContent,
    setContent,
  }
})
