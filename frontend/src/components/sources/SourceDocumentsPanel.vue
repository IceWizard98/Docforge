<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { BookOpen, FileText, Eye, EyeOff, RefreshCw } from '@lucide/vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import {
  listDocumentSources,
  excludeDocumentSource,
  includeDocumentSource,
  reindexAllSources,
  extractApiError,
} from '@/api/client'
import type { DocumentSourceItem } from '@/api/client'
import { useDocTypeLabel } from '@/composables/useDocTypeLabel'
import { useToast } from '@/composables/useToast'
import { useConfirm } from '@/composables/useConfirm'

const props = defineProps<{ documentId: string }>()

const docTypeLabel = useDocTypeLabel()
const toast = useToast()
const { confirm } = useConfirm()

const sources = ref<DocumentSourceItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const reindexing = ref(false)

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })
}

async function fetchSources() {
  loading.value = true
  error.value = null
  try {
    sources.value = await listDocumentSources(props.documentId)
  } catch (e: any) {
    error.value = extractApiError(e, 'Failed to load sources')
  } finally {
    loading.value = false
  }
}

// Optimistic toggle: flip the flag, call the API, roll back + toast on failure.
async function toggleExclusion(source: DocumentSourceItem) {
  const nextExcluded = !source.excluded
  source.excluded = nextExcluded
  try {
    if (nextExcluded) {
      await excludeDocumentSource(props.documentId, source.id)
    } else {
      await includeDocumentSource(props.documentId, source.id)
    }
  } catch (e: any) {
    source.excluded = !nextExcluded
    toast.error(extractApiError(e, 'Aggiornamento fonte fallito'))
  }
}

// Re-index the whole corpus (after a chunking/embedding change). Kicks off async
// Celery jobs backend-side; we just confirm, fire, and report how many started.
async function reindexAll() {
  if (reindexing.value) return
  const ok = await confirm({
    title: 'Reindicizza fonti',
    message: 'Reindicizzare tutte le fonti? Le fonti vengono ri-elaborate in background.',
    confirmLabel: 'Reindicizza',
  })
  if (!ok) return
  reindexing.value = true
  try {
    const { count } = await reindexAllSources()
    toast.success(count > 0 ? `Reindicizzazione avviata su ${count} fonti` : 'Nessuna fonte da reindicizzare')
  } catch (e: any) {
    toast.error(extractApiError(e, 'Reindicizzazione fallita'))
  } finally {
    reindexing.value = false
  }
}

onMounted(fetchSources)
</script>

<template>
  <div class="min-h-0 flex-1 overflow-y-auto p-4 space-y-3">
    <div class="flex items-center gap-2">
      <h3 class="text-sm font-semibold text-foreground flex items-center gap-2 min-w-0">
        <BookOpen class="h-4 w-4 text-primary shrink-0" />
        Documenti Sorgente
        <span class="text-xs text-foreground/40 bg-primary/8 px-2 py-0.5 rounded-full">{{ sources.length }}</span>
      </h3>
      <button
        class="ml-auto inline-flex items-center gap-1.5 rounded-md border border-primary/15 px-2 py-1 text-xs font-medium text-foreground/70 hover:bg-primary/8 hover:text-primary transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="reindexing || !sources.length"
        title="Reindicizza tutte le fonti"
        aria-label="Reindicizza tutte le fonti"
        @click="reindexAll"
      >
        <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': reindexing }" />
        <span class="hidden sm:inline">{{ reindexing ? 'Reindicizzo…' : 'Reindicizza' }}</span>
      </button>
    </div>

    <p class="text-xs text-foreground/50">
      Le fonti escluse non vengono usate dall'assistente per questo documento.
    </p>

    <LoadingSpinner v-if="loading" size="sm" />

    <ErrorMessage
      v-else-if="error && !loading"
      :message="error"
      retry-label="Riprova"
      @retry="fetchSources"
    />

    <EmptyState
      v-else-if="!sources.length"
      :icon="FileText"
      title="Nessun documento sorgente"
      description="Carica un documento dall'area di lavoro per iniziare"
    />

    <div v-else class="space-y-2">
      <div
        v-for="source in sources"
        :key="source.id"
        class="rounded-lg border border-primary/10 bg-card p-3 hover:border-primary/20 transition-colors"
        :class="{ 'opacity-50': source.excluded }"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <FileText class="h-4 w-4 text-primary shrink-0" />
            <span class="text-sm font-medium text-foreground truncate">{{ source.filename }}</span>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span
              v-if="source.excluded"
              class="text-xs bg-warning/10 text-warning px-1.5 py-0.5 rounded"
            >
              Esclusa
            </span>
            <span class="text-xs text-foreground/40">{{ docTypeLabel(source.doc_type) }}</span>
            <button
              class="p-1 rounded text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :title="source.excluded ? 'Ripristina fonte' : 'Escludi fonte'"
              :aria-label="source.excluded ? 'Ripristina fonte' : 'Escludi fonte'"
              @click="toggleExclusion(source)"
            >
              <Eye v-if="source.excluded" class="h-3.5 w-3.5" />
              <EyeOff v-else class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <div v-if="source.language || source.tags?.length || source.jurisdiction || source.parties?.length" class="mt-2 flex flex-wrap gap-1">
          <span v-if="source.language" class="text-xs bg-primary/8 text-primary px-1.5 py-0.5 rounded">
            {{ source.language }}
          </span>
          <span v-if="source.jurisdiction" class="text-xs bg-secondary/10 text-secondary px-1.5 py-0.5 rounded">
            {{ source.jurisdiction }}
          </span>
          <span
            v-for="tag in (source.tags || [])"
            :key="tag"
            class="text-xs bg-surface text-foreground/60 px-1.5 py-0.5 rounded"
          >
            {{ tag }}
          </span>
        </div>

        <p class="text-xs text-foreground/40 mt-1">
          Caricato il {{ formatDate(source.created_at) }}
        </p>
      </div>
    </div>
  </div>
</template>
