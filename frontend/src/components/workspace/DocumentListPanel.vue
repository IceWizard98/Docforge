<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FileText, Plus, Clock, FileText as FileTextIcon } from '@lucide/vue'
import { listDocuments, createDocument } from '@/api/client'
import type { DocumentResponse } from '@/types/document'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'

const router = useRouter()
const documents = ref<DocumentResponse[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

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
  try {
    const doc = await createDocument('Nuovo documento')
    router.push(`/documents/${doc.id}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Creazione fallita'
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}

onMounted(fetchDocs)
</script>

<template>
  <aside class="flex flex-col h-full bg-surface w-64 border-r border-primary/10">
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

    <!-- Empty state -->
    <EmptyState
      v-if="!loading && !error && documents.length === 0"
      :icon="FileTextIcon"
      title="Nessun documento"
      description="Crea il tuo primo documento per iniziare"
      action-label="Nuovo documento"
      @action="createNew"
    />

    <!-- Document list -->
    <div v-if="!loading && documents.length > 0" class="flex-1 overflow-y-auto">
      <button
        v-for="doc in documents"
        :key="doc.id"
        class="w-full flex items-center gap-3 px-4 py-3 text-left transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none hover:bg-primary/5 border-b border-primary/5 last:border-b-0"
        @click="navigateToDoc(doc.id)"
      >
        <FileText class="w-4 h-4 text-primary/40 flex-shrink-0" />
        <div class="flex-1 min-w-0">
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
              {{ formatDate(doc.updatedAt) }}
            </span>
          </div>
        </div>
      </button>
    </div>

    <!-- Create button -->
    <div class="p-3 border-t border-primary/10">
      <button
        class="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        @click="createNew"
      >
        <Plus class="w-4 h-4" />
        Nuovo documento
      </button>
    </div>
  </aside>
</template>
