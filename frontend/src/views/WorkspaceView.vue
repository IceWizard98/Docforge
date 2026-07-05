<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import DropZoneOverlay from '@/components/common/DropZoneOverlay.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { Sparkles, Plus, Clock, FileText as FileTextIcon, Search, ChevronLeft, ChevronRight, UploadCloud } from '@lucide/vue'
import { listDocumentsPaged, listTemplates, createDocument, uploadDocument } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { DocumentResponse } from '@/types/document'

interface Template {
  id: string
  name: string
  description?: string
  category?: string
  doc_type?: string
  created_at: string
}

const router = useRouter()
const toast = useToast()

const docs = ref<DocumentResponse[]>([])
const total = ref(0)
const page = ref(1)
const perPage = 12
const search = ref('')
const templates = ref<Template[]>([])
const loading = ref(true)
const listLoading = ref(false)
const creating = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

let searchTimer: ReturnType<typeof setTimeout> | null = null

const totalPages = () => Math.max(1, Math.ceil(total.value / perPage))

async function fetchDocs() {
  listLoading.value = true
  try {
    const res = await listDocumentsPaged({ page: page.value, perPage, search: search.value })
    docs.value = res.data
    total.value = res.total
  } catch {
    docs.value = []
    total.value = 0
  } finally {
    listLoading.value = false
  }
}

async function fetchInitial() {
  loading.value = true
  try {
    const [, tpls] = await Promise.all([
      fetchDocs(),
      listTemplates().then((r) => (r.data || []) as Template[]).catch(() => [] as Template[]),
    ])
    templates.value = tpls.slice(0, 3)
  } finally {
    loading.value = false
  }
}

onMounted(fetchInitial)

// Debounced search: reset to page 1 and refetch.
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchDocs()
  }, 300)
})

function goToPage(p: number) {
  if (p < 1 || p > totalPages() || p === page.value) return
  page.value = p
  fetchDocs()
}

async function createNew() {
  if (creating.value) return
  creating.value = true
  try {
    const doc = await createDocument('Nuovo documento')
    router.push(`/documents/${doc.id}`)
  } catch {
    toast.error('Impossibile creare il documento')
  } finally {
    creating.value = false
  }
}

async function createFromTemplate(tpl: Template) {
  if (creating.value) return
  creating.value = true
  try {
    const doc = await createDocument(tpl.name, tpl.doc_type || '')
    router.push(`/documents/${doc.id}`)
  } catch {
    toast.error('Impossibile creare dal template')
  } finally {
    creating.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFileChosen(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) await doUpload(file)
}

async function doUpload(file: File) {
  if (uploading.value) return
  uploading.value = true
  try {
    const doc = await uploadDocument(file)
    router.push(`/documents/${doc.id}`)
  } catch {
    toast.error('Caricamento del documento fallito')
  } finally {
    uploading.value = false
  }
}

function navigateToDoc(id: string) {
  router.push(`/documents/${id}`)
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
}
</script>

<template>
  <div class="h-full overflow-y-auto bg-surface">
    <div class="max-w-5xl mx-auto p-6 md:p-8 lg:p-10">
      <!-- Hero -->
      <div class="text-center mb-10">
        <div class="flex justify-center mb-4">
          <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Sparkles class="w-8 h-8 text-primary" />
          </div>
        </div>
        <h1 class="text-2xl font-bold text-foreground mb-2" style="font-family: var(--font-heading)">DocForge</h1>
        <p class="text-sm text-foreground/50 max-w-sm mx-auto mb-6">
          Parla con l'AI per redigere il tuo documento — il contenuto appare quando c'è qualcosa da mostrare
        </p>
        <div class="flex items-center justify-center gap-2">
          <button
            class="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-light transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="creating"
            @click="createNew"
          >
            <Plus class="w-4 h-4" />
            {{ creating ? 'Creazione...' : 'Inizia a scrivere' }}
          </button>
          <button
            class="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg border border-primary/15 text-foreground/80 hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="uploading"
            @click="pickFile"
          >
            <UploadCloud class="w-4 h-4" />
            {{ uploading ? 'Caricamento...' : 'Carica' }}
          </button>
          <input
            ref="fileInput"
            type="file"
            accept=".pdf,.docx,.txt,.md"
            class="hidden"
            @change="onFileChosen"
          />
        </div>
      </div>

      <LoadingSpinner v-if="loading" />

      <template v-else>
        <!-- Documents: search + paginated grid -->
        <section class="mb-10">
          <div class="flex items-center justify-between gap-3 mb-4">
            <h2 class="text-lg font-semibold text-foreground">
              Documenti
              <span v-if="total" class="text-sm font-normal text-foreground/40">({{ total }})</span>
            </h2>
            <div class="relative w-full max-w-xs">
              <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-foreground/40" />
              <input
                v-model="search"
                type="search"
                placeholder="Cerca documenti..."
                class="w-full rounded-lg border border-primary/10 bg-card pl-9 pr-3 py-2 text-sm text-foreground placeholder:text-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              />
            </div>
          </div>

          <div v-if="listLoading" class="py-10">
            <LoadingSpinner />
          </div>

          <div v-else-if="docs.length" class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="doc in docs"
              :key="doc.id"
              class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer"
              @click="navigateToDoc(doc.id)"
            >
              <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <FileTextIcon class="w-4 h-4 text-primary" />
                </div>
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-medium text-foreground truncate">{{ doc.title || 'Senza titolo' }}</p>
                  <div class="flex items-center gap-2 mt-1.5">
                    <span
                      class="text-[10px] font-medium uppercase tracking-widest px-1.5 py-0.5 rounded-full"
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
                </div>
              </div>
            </div>
          </div>

          <div v-else class="text-center py-12 rounded-lg border border-dashed border-primary/15">
            <FileTextIcon class="w-10 h-10 text-foreground/20 mx-auto mb-3" />
            <p class="text-sm text-foreground/50">
              {{ search ? 'Nessun documento corrisponde alla ricerca.' : 'Nessun documento ancora. Crea il tuo primo documento per iniziare.' }}
            </p>
          </div>

          <!-- Pagination -->
          <div v-if="total > perPage" class="flex items-center justify-center gap-3 mt-6">
            <button
              class="p-2 rounded-lg border border-primary/10 text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :disabled="page <= 1"
              aria-label="Pagina precedente"
              @click="goToPage(page - 1)"
            >
              <ChevronLeft class="w-4 h-4" />
            </button>
            <span class="text-sm text-foreground/60">Pagina {{ page }} di {{ totalPages() }}</span>
            <button
              class="p-2 rounded-lg border border-primary/10 text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :disabled="page >= totalPages()"
              aria-label="Pagina successiva"
              @click="goToPage(page + 1)"
            >
              <ChevronRight class="w-4 h-4" />
            </button>
          </div>
        </section>

        <!-- Templates -->
        <section v-if="templates.length">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-foreground">Template</h2>
            <router-link to="/templates" class="text-sm text-primary hover:text-primary-light transition-colors font-medium">
              Vedi tutti
            </router-link>
          </div>
          <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div
              v-for="tpl in templates"
              :key="tpl.id"
              class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer"
              @click="createFromTemplate(tpl)"
            >
              <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-lg bg-cta/10 flex items-center justify-center shrink-0">
                  <FileTextIcon class="w-4 h-4 text-cta" />
                </div>
                <div class="min-w-0 flex-1">
                  <p class="text-sm font-medium text-foreground truncate">{{ tpl.name }}</p>
                  <p v-if="tpl.description" class="text-xs text-foreground/50 mt-0.5 line-clamp-2">
                    {{ tpl.description }}
                  </p>
                  <span class="inline-block text-xs bg-primary/8 text-primary px-2 py-0.5 rounded mt-2">
                    {{ tpl.category || 'Generale' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </template>
    </div>

    <DropZoneOverlay @dropped="doUpload" />
  </div>
</template>
