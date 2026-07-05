<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Loader2, Download, X } from '@lucide/vue'
import {
  createExport,
  getExport,
  downloadExport,
  listTemplates,
  extractApiError,
  type TemplateResponse,
} from '@/api/client'
import { useToast } from '@/composables/useToast'
import { saveBlob } from '@/utils/download'

const props = defineProps<{ documentId: string; docTitle: string }>()
const emit = defineEmits<{ close: [] }>()

const toast = useToast()

const FORMATS = [
  { value: 'pdf', label: 'PDF', ext: 'pdf' },
  { value: 'docx', label: 'DOCX', ext: 'docx' },
  { value: 'md', label: 'Markdown', ext: 'md' },
] as const

const format = ref<'pdf' | 'docx' | 'md'>('pdf')
const exporting = ref(false)
const error = ref<string | null>(null)

// Templates apply only to the DOCX-backed formats; markdown ignores them.
const templates = ref<TemplateResponse[]>([])
const templateId = ref('')
const templatesUsable = computed(() => format.value !== 'md')

onMounted(async () => {
  try {
    const { data } = await listTemplates()
    templates.value = data.filter((t) => t.hasFile)
  } catch {
    templates.value = []
  }
})

let pollTimer: ReturnType<typeof setTimeout> | null = null
const POLL_MS = 1500
const MAX_POLLS = 80 // ~2 min

function stopPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function safeFilename(): string {
  const ext = FORMATS.find((f) => f.value === format.value)?.ext ?? format.value
  const base = (props.docTitle || 'documento').replace(/[/\\?%*:|"<>]/g, '_').trim() || 'documento'
  return `${base}.${ext}`
}

async function triggerDownload(exportId: string) {
  const blob = await downloadExport(exportId)
  saveBlob(blob, safeFilename())
}

async function startExport() {
  if (exporting.value) return
  exporting.value = true
  error.value = null
  try {
    const useTemplate = templatesUsable.value && templateId.value ? templateId.value : undefined
    const job = await createExport(props.documentId, format.value, useTemplate)
    let polls = 0
    const poll = async () => {
      polls += 1
      try {
        const status = await getExport(job.id)
        if (status.status === 'completed') {
          await triggerDownload(job.id)
          exporting.value = false
          toast.success('Esportazione completata')
          emit('close')
          return
        }
        if (status.status === 'failed') {
          exporting.value = false
          error.value = status.error || 'Esportazione fallita'
          toast.error(error.value)
          return
        }
      } catch (e: any) {
        exporting.value = false
        error.value = extractApiError(e, 'Esportazione fallita')
        toast.error(error.value)
        return
      }
      if (polls >= MAX_POLLS) {
        exporting.value = false
        error.value = 'Esportazione scaduta, riprova'
        toast.error(error.value)
        return
      }
      pollTimer = setTimeout(poll, POLL_MS)
    }
    pollTimer = setTimeout(poll, POLL_MS)
  } catch (e: any) {
    exporting.value = false
    error.value = extractApiError(e, 'Esportazione fallita')
    toast.error(error.value)
  }
}

function close() {
  stopPolling()
  emit('close')
}

onUnmounted(stopPolling)
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      @click.self="close"
    >
      <div class="w-full max-w-md rounded-xl bg-surface p-5 md:p-6 shadow-xl border border-primary/10">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-foreground">Esporta documento</h2>
          <button
            class="p-1 rounded text-foreground/40 hover:text-foreground hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            aria-label="Chiudi"
            @click="close"
          >
            <X class="h-4 w-4" />
          </button>
        </div>

        <fieldset class="space-y-2 mb-4" :disabled="exporting">
          <legend class="sr-only">Formato di esportazione</legend>
          <label
            v-for="f in FORMATS"
            :key="f.value"
            class="flex items-center gap-3 rounded-lg border border-primary/10 bg-card px-3 py-2 cursor-pointer hover:border-primary/30 transition-colors"
            :class="{ 'border-primary/40 bg-primary/5': format === f.value }"
          >
            <input
              v-model="format"
              type="radio"
              name="export-format"
              :value="f.value"
              class="accent-primary"
            />
            <span class="text-sm font-medium text-foreground">{{ f.label }}</span>
          </label>
        </fieldset>

        <div v-if="templates.length" class="mb-4">
          <label for="export-template" class="block text-sm font-medium text-foreground mb-1">
            Template DOCX
          </label>
          <select
            id="export-template"
            v-model="templateId"
            :disabled="exporting || !templatesUsable"
            class="w-full rounded-lg border border-primary/10 bg-card px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="">Nessun template</option>
            <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
          <p v-if="!templatesUsable" class="mt-1 text-xs text-foreground/50">
            I template non si applicano al formato Markdown.
          </p>
        </div>

        <p v-if="error" class="text-xs text-danger mb-3">{{ error }}</p>

        <div v-if="exporting" class="flex items-center gap-2 text-sm text-foreground/60 mb-4">
          <Loader2 class="h-4 w-4 animate-spin text-primary" />
          Esportazione in corso…
        </div>

        <div class="flex justify-end gap-2">
          <button
            class="rounded-lg px-4 py-2 text-sm font-medium text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer"
            @click="close"
          >
            Annulla
          </button>
          <button
            :disabled="exporting"
            class="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            @click="startExport"
          >
            <Loader2 v-if="exporting" class="h-3.5 w-3.5 animate-spin" />
            <Download v-else class="h-3.5 w-3.5" />
            Esporta
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
