<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { BookOpen, FileText } from '@lucide/vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { listSources, extractApiError } from '@/api/client'
import type { SourceDocumentResponse } from '@/api/client'
import { useDocTypeLabel } from '@/composables/useDocTypeLabel'

const props = defineProps<{ documentId: string }>()

const docTypeLabel = useDocTypeLabel()

const sources = ref<SourceDocumentResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '\u2014'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })
}

async function fetchSources() {
  loading.value = true
  error.value = null
  try {
    sources.value = await listSources(props.documentId)
  } catch (e: any) {
    error.value = extractApiError(e, 'Failed to load sources')
  } finally {
    loading.value = false
  }
}

onMounted(fetchSources)
</script>

<template>
  <div class="min-h-0 flex-1 overflow-y-auto p-4 space-y-3">
    <h3 class="text-sm font-semibold text-foreground flex items-center gap-2">
      <BookOpen class="h-4 w-4 text-primary" />
      Documenti Sorgente
      <span class="ml-auto text-xs text-foreground/40 bg-primary/8 px-2 py-0.5 rounded-full">{{ sources.length }}</span>
    </h3>

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
      >
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <FileText class="h-4 w-4 text-primary shrink-0" />
            <span class="text-sm font-medium text-foreground truncate">{{ source.filename }}</span>
          </div>
          <span class="text-xs text-foreground/40 shrink-0">{{ docTypeLabel(source.doc_type) }}</span>
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
