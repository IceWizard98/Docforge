<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { BookOpen, FileText, UploadCloud, Download, Trash2, RefreshCw } from '@lucide/vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import {
  listAllSources,
  uploadSource,
  downloadSource,
  deleteSource,
  type SourceDocumentResponse,
} from '@/api/client'
import { useToast } from '@/composables/useToast'

const { success, error: toastError } = useToast()

const sources = ref<SourceDocumentResponse[]>([])
const loading = ref(true)
const uploading = ref(false)
const error = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasPending = computed(() =>
  sources.value.some((s) => s.status === 'uploaded' || s.status === 'indexing'),
)

function extractError(e: any): string {
  return e?.response?.data?.detail || e?.message || 'Operazione fallita'
}

function statusLabel(status?: string): { text: string; cls: string } {
  switch (status) {
    case 'indexed':
      return { text: 'Indicizzato', cls: 'bg-primary/10 text-primary' }
    case 'indexing':
      return { text: 'Indicizzazione…', cls: 'bg-warning/15 text-warning' }
    case 'failed':
      return { text: 'Errore', cls: 'bg-danger/15 text-danger' }
    default:
      return { text: 'In coda', cls: 'bg-secondary/10 text-secondary' }
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })
}

async function fetchSources() {
  error.value = null
  try {
    const res = await listAllSources()
    sources.value = res.data
  } catch (e: any) {
    error.value = extractError(e)
  } finally {
    loading.value = false
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  uploading.value = true
  try {
    for (const file of Array.from(files)) {
      const created = await uploadSource(file)
      sources.value.unshift(created)
    }
    success('Fonte caricata, indicizzazione avviata')
  } catch (e: any) {
    toastError(extractError(e))
  } finally {
    uploading.value = false
    input.value = ''
  }
}

async function onDownload(source: SourceDocumentResponse) {
  try {
    const blob = await downloadSource(source.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = source.filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    toastError(extractError(e))
  }
}

async function onDelete(source: SourceDocumentResponse) {
  if (!confirm(`Eliminare "${source.filename}" dalla libreria?`)) return
  try {
    await deleteSource(source.id)
    sources.value = sources.value.filter((s) => s.id !== source.id)
    success('Fonte eliminata')
  } catch (e: any) {
    toastError(extractError(e))
  }
}

onMounted(() => {
  fetchSources()
  // Refresh while any source is still being indexed.
  pollTimer = setInterval(() => {
    if (hasPending.value) fetchSources()
  }, 4000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div class="mx-auto max-w-5xl p-6">
    <div class="flex items-center gap-3 mb-6">
      <BookOpen class="h-6 w-6 text-primary" />
      <div>
        <h1 class="text-xl font-semibold text-foreground">Libreria fonti</h1>
        <p class="text-sm text-foreground/60">
          Documenti caricati e indicizzati, usati dall'AI per comporre nuovi documenti.
        </p>
      </div>
      <div class="ml-auto flex items-center gap-2">
        <button
          class="p-2 rounded-md text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors"
          title="Aggiorna"
          @click="fetchSources"
        >
          <RefreshCw class="h-4 w-4" />
        </button>
        <button
          class="flex items-center gap-2 px-3 py-2 text-sm rounded-md bg-primary text-white hover:bg-primary-light transition-colors disabled:opacity-50"
          :disabled="uploading"
          @click="triggerUpload"
        >
          <UploadCloud class="h-4 w-4" />
          {{ uploading ? 'Caricamento…' : 'Carica fonte' }}
        </button>
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.docx,.txt,.md"
          multiple
          class="hidden"
          @change="onFileSelected"
        />
      </div>
    </div>

    <LoadingSpinner v-if="loading" size="md" />

    <ErrorMessage
      v-else-if="error"
      :message="error"
      retry-label="Riprova"
      @retry="fetchSources"
    />

    <EmptyState
      v-else-if="!sources.length"
      :icon="FileText"
      title="Nessuna fonte caricata"
      description="Carica PDF, DOCX, TXT o Markdown per costruire la tua base di conoscenza"
    />

    <div v-else class="space-y-2">
      <div
        v-for="source in sources"
        :key="source.id"
        class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/20 transition-colors"
      >
        <div class="flex items-center gap-3">
          <FileText class="h-5 w-5 text-primary shrink-0" />
          <div class="min-w-0 flex-1">
            <div class="text-sm font-medium text-foreground truncate">{{ source.filename }}</div>
            <div class="text-xs text-foreground/50 flex items-center gap-2 mt-0.5">
              <span class="uppercase">{{ source.doc_type || 'N/A' }}</span>
              <span v-if="source.language">· {{ source.language }}</span>
              <span>· {{ formatDate(source.created_at) }}</span>
            </div>
          </div>
          <span
            class="text-xs px-2 py-0.5 rounded-full shrink-0"
            :class="statusLabel(source.status).cls"
          >
            {{ statusLabel(source.status).text }}
          </span>
          <button
            class="p-2 rounded-md text-foreground/60 hover:text-primary hover:bg-primary/8 transition-colors"
            title="Scarica originale"
            @click="onDownload(source)"
          >
            <Download class="h-4 w-4" />
          </button>
          <button
            class="p-2 rounded-md text-foreground/60 hover:text-danger hover:bg-danger/10 transition-colors"
            title="Elimina"
            @click="onDelete(source)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>

        <div
          v-if="source.tags?.length || source.jurisdiction || source.parties?.length"
          class="mt-2 flex flex-wrap gap-1 pl-8"
        >
          <span v-if="source.jurisdiction" class="text-xs bg-secondary/10 text-secondary px-1.5 py-0.5 rounded">
            {{ source.jurisdiction }}
          </span>
          <span
            v-for="tag in source.tags || []"
            :key="tag"
            class="text-xs bg-primary/8 text-primary px-1.5 py-0.5 rounded"
          >
            {{ tag }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
