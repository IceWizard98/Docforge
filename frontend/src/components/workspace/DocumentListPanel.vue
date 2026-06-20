<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { FileText, Plus, Clock, Upload, Loader2, FileText as FileTextIcon, Pencil, Trash2, Search, Menu, X } from '@lucide/vue'
import Tooltip from '@/components/common/Tooltip.vue'
import { useToast } from '@/composables/useToast'
import { listDocuments, createDocument, uploadDocument, deleteDocument, renameDocument } from '@/api/client'
import type { DocumentResponse } from '@/types/document'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'

const router = useRouter()
const route = useRoute()
const toast = useToast()
const documents = ref<DocumentResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const creating = ref(false)
const uploading = ref(false)
const searchQuery = ref('')
const renamingId = ref<string | null>(null)
const renameValue = ref('')
const renameInputRef = ref<HTMLInputElement>()

const filteredDocuments = computed(() => {
  if (!searchQuery.value.trim()) return documents.value
  const q = searchQuery.value.toLowerCase()
  return documents.value.filter(d => (d.title || '').toLowerCase().includes(q))
})

const fileInputRef = ref<HTMLInputElement | null>(null)
const dropZoneActive = ref(false)
const mobileOpen = ref(false)

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function fetchDocs() {
  loading.value = true
  error.value = null
  try {
    documents.value = await listDocuments()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to load documents'
  } finally {
    loading.value = false
  }
}

function navigateToDoc(id: string) {
  router.push(`/documents/${id}`)
}

async function createNew() {
  if (creating.value) return
  creating.value = true
  try {
    const doc = await createDocument('Nuovo documento')
    router.push(`/documents/${doc.id}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Creazione fallita'
  } finally {
    creating.value = false
  }
}

function openFilePicker() {
  fileInputRef.value?.click()
}

async function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await uploadFile(file)
  input.value = ''
}

async function uploadFile(file: File) {
  uploading.value = true
  error.value = null
  try {
    const doc = await uploadDocument(file)
    await fetchDocs()
    router.push(`/documents/${doc.id}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Upload fallito'
  } finally {
    uploading.value = false
  }
}

function onDragEnter(e: DragEvent) {
  e.preventDefault()
  dropZoneActive.value = true
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dropZoneActive.value = true
}

function onDragLeave(e: DragEvent) {
  e.preventDefault()
  dropZoneActive.value = false
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dropZoneActive.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadFile(file)
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}

function startRename(doc: DocumentResponse) {
  renamingId.value = doc.id
  renameValue.value = doc.title || ''
  nextTick(() => renameInputRef.value?.focus())
}

async function confirmRename(id: string) {
  if (!renamingId.value) return
  renamingId.value = null
  const trimmed = renameValue.value.trim()
  if (!trimmed) {
    toast.error('Il titolo non può essere vuoto')
    return
  }
  const originalTitle = documents.value.find(d => d.id === id)?.title || ''
  try {
    await renameDocument(id, trimmed)
    const doc = documents.value.find(d => d.id === id)
    if (doc) doc.title = trimmed
    toast.success('Documento rinominato')
  } catch (e: any) {
    const doc = documents.value.find(d => d.id === id)
    if (doc) doc.title = originalTitle
    toast.error(e?.response?.data?.detail || 'Errore nel rinominare il documento')
  }
}

function cancelRename() {
  renamingId.value = null
  renameValue.value = ''
}

async function confirmDelete(doc: DocumentResponse) {
  if (window.confirm(`Eliminare "${doc.title || 'Untitled'}"?`)) {
    try {
      await deleteDocument(doc.id)
      documents.value = documents.value.filter(d => d.id !== doc.id)
    } catch (e: any) {
      console.warn('Failed to delete document:', e?.message || e)
    }
  }
}

onMounted(fetchDocs)
</script>

<template>
  <!-- Mobile toggle button -->
  <Tooltip text="Documenti" position="right">
    <button
      @click="mobileOpen = !mobileOpen"
      class="md:hidden fixed bottom-4 left-4 z-50 rounded-full bg-primary p-3 text-white shadow-lg hover:bg-primary/90 transition-colors cursor-pointer"
      aria-label="Apri elenco documenti"
    >
      <Menu class="h-5 w-5" />
    </button>
  </Tooltip>

  <!-- Mobile sidebar -->
  <div v-if="mobileOpen" class="fixed inset-0 z-40 md:hidden" @click="mobileOpen = false">
    <div class="absolute inset-0 bg-black/30" />
    <aside
      class="absolute left-0 top-0 h-full w-72 bg-surface shadow-xl p-4 overflow-y-auto border-r border-primary/10"
      @click.stop
    >
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-foreground text-sm">Documenti</h2>
        <button
          @click="mobileOpen = false"
          class="p-1 rounded hover:bg-primary/8 text-foreground/50 cursor-pointer"
          aria-label="Chiudi elenco documenti"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <div class="relative mb-3">
        <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/40" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Cerca documenti..."
          class="w-full rounded-md border border-primary/10 bg-card pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-foreground/30 focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="Cerca documenti"
        />
      </div>
      <div class="space-y-1">
        <div
          v-for="doc in filteredDocuments"
          :key="doc.id"
          class="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors hover:bg-primary/5"
          @click="navigateToDoc(doc.id); mobileOpen = false"
        >
          <FileText class="w-4 h-4 text-primary/40 shrink-0" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-foreground truncate">{{ doc.title || 'Untitled' }}</p>
            <p class="text-xs text-foreground/40">{{ formatDate(doc.updated_at) }}</p>
          </div>
        </div>
      </div>
      <div class="mt-4 flex gap-2">
        <button
          @click="createNew(); mobileOpen = false"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors cursor-pointer"
        >
          Nuovo
        </button>
        <button
          @click="openFilePicker(); mobileOpen = false"
          class="flex-1 px-3 py-2 text-sm font-medium rounded-md border border-primary/20 text-primary hover:bg-primary/8 transition-colors cursor-pointer"
        >
          Upload
        </button>
      </div>
    </aside>
  </div>

  <!-- Desktop sidebar -->
  <aside class="hidden md:flex flex-col h-full bg-surface w-64 border-r border-primary/10">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <FileText class="w-4 h-4 text-primary" />
      <h2 class="text-sm font-semibold text-foreground">Documents</h2>
    </div>

    <!-- Loading state -->
    <LoadingSpinner v-if="loading" size="sm" />

    <!-- Error state -->
    <ErrorMessage
      v-if="error && !loading"
      :message="error"
      retry-label="Riprova"
      @retry="fetchDocs"
    />

    <!-- Search input -->
    <div v-if="!loading && !error && documents.length > 0" class="px-3 pt-2 pb-1">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/40" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Cerca documenti..."
          class="w-full rounded-md border border-primary/10 bg-card pl-8 pr-3 py-1.5 text-xs text-foreground placeholder:text-foreground/30 focus:outline-none focus:ring-2 focus:ring-primary"
          aria-label="Cerca documenti"
        />
      </div>
    </div>

    <!-- Empty state -->
    <EmptyState
      v-if="!loading && !error && filteredDocuments.length === 0 && !searchQuery"
      :icon="FileTextIcon"
      title="Nessun documento"
      description="Crea il tuo primo documento per iniziare"
      action-label="Nuovo documento"
      @action="createNew"
    />

    <!-- No search results -->
    <div
      v-if="!loading && !error && filteredDocuments.length === 0 && searchQuery"
      class="flex flex-col items-center justify-center py-8 px-4 text-center"
    >
      <p class="text-sm text-foreground/50">Nessun documento trovato per "{{ searchQuery }}"</p>
    </div>

    <!-- Document list with drag-drop zone -->
    <div
      class="flex-1 overflow-y-auto relative"
      @dragenter="onDragEnter"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <div
        v-if="dropZoneActive"
        class="absolute inset-0 z-10 flex items-center justify-center bg-primary/5 border-2 border-dashed border-primary/40 rounded-lg m-2"
      >
        <p class="text-sm font-medium text-primary">Drop file here</p>
      </div>

      <div
        v-for="doc in filteredDocuments"
        :key="doc.id"
        class="group relative flex items-center gap-3 px-4 py-3 text-left transition-colors duration-150 cursor-pointer border-b border-primary/5 last:border-b-0"
	        :class="route.params.id === doc.id ? 'bg-primary/10 text-primary' : 'hover:bg-primary/5'"
        @click="navigateToDoc(doc.id)"
      >
        <FileText class="w-4 h-4 text-primary/40 flex-shrink-0 mt-0.5 self-start" />
        <div class="flex-1 min-w-0">
          <template v-if="renamingId === doc.id">
            <input
              ref="renameInputRef"
              v-model="renameValue"
              @keydown.enter.stop="confirmRename(doc.id)"
              @keydown.escape.stop="cancelRename"
              @click.stop
              @blur="confirmRename(doc.id)"
              class="w-full text-sm font-medium bg-transparent border-b border-primary outline-none text-foreground px-0 py-0"
              aria-label="Nuovo nome del documento"
            />
          </template>
          <template v-else>
            <p class="text-sm font-medium text-foreground truncate">{{ doc.title || 'Untitled' }}</p>
            <div class="flex items-center gap-2 mt-0.5">
              <span
                class="text-[10px] font-medium uppercase tracking-widest px-1 py-0.5 rounded-full"
                :class="{
                  'bg-cta/10 text-cta': doc.status === 'approved',
                  'bg-primary/10 text-primary': doc.status === 'draft',
                  'bg-foreground/5 text-foreground/50': !['approved', 'draft'].includes(doc.status),
                }"
              >
                {{ doc.status }}
              </span>
              <span class="text-[10px] text-foreground/40 flex items-center gap-1">
                <Clock class="w-2.5 h-2.5" />
                {{ formatDate(doc.updated_at) }}
              </span>
            </div>
          </template>
        </div>
        <div v-if="renamingId !== doc.id" class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            @click.stop="startRename(doc)"
            class="p-1 rounded hover:bg-primary/8 text-foreground/40 hover:text-primary transition-colors cursor-pointer"
            title="Rinomina"
            aria-label="Rinomina"
          >
            <Pencil class="h-3.5 w-3.5" />
          </button>
          <button
            @click.stop="confirmDelete(doc)"
            class="p-1 rounded hover:bg-danger/8 text-foreground/40 hover:text-danger transition-colors cursor-pointer"
            title="Elimina"
            aria-label="Elimina"
          >
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom actions -->
    <div class="p-3 border-t border-primary/10 flex gap-2">
      <input
        ref="fileInputRef"
        type="file"
        accept=".pdf,.docx,.txt,.md"
        class="hidden"
        @change="handleFileSelected"
      />
      <button
        class="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="creating"
        @click="createNew"
      >
        <Plus class="w-4 h-4" />
        Nuovo
      </button>
      <button
        class="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md border border-primary/20 text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="uploading"
        @click="openFilePicker"
      >
        <Upload v-if="!uploading" class="w-4 h-4" />
        <Loader2 v-else class="w-4 h-4 animate-spin" />
        {{ uploading ? 'Uploading...' : 'Upload' }}
      </button>
    </div>
  </aside>
</template>
