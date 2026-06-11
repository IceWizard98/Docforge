import { defineStore } from 'pinia'
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
  const sections = ref<SectionInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const sectionCount = computed(() => sections.value.length)

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
      sections.value = (data.sections || []).map((s: any) => ({
        id: s.id,
        number: s.number,
        title: s.title,
        status: s.status,
      }))
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || 'Failed to fetch document'
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
      error.value = e?.response?.data?.detail || e.message || 'Failed to update title'
    }
  }

  async function saveContent(json: Record<string, unknown>) {
    const id = currentDocId.value
    if (!id) return
    error.value = null
    try {
      await apiClient.patch(`/documents/${id}`, { content: json })
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || 'Failed to save content'
    }
  }

  async function updateSectionStatus(sectionId: string, newStatus: string) {
    if (!currentDocId.value) return
    error.value = null

    try {
      await apiClient.patch(`/documents/${currentDocId.value}/sections/${sectionId}`, {
        status: newStatus,
      })
      const idx = sections.value.findIndex((s) => s.id === sectionId)
      if (idx !== -1) {
        sections.value[idx] = { ...sections.value[idx], status: newStatus }
      }
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e.message || 'Failed to update section status'
    }
  }

  return {
    currentDocId,
    title,
    status,
    version,
    sections,
    loading,
    error,
    sectionCount,
    fetchDocument,
    updateTitle,
    updateSectionStatus,
    saveContent,
  }
})
