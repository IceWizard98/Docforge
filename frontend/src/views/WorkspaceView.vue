<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DocumentListPanel from '@/components/workspace/DocumentListPanel.vue'
import DropZoneOverlay from '@/components/common/DropZoneOverlay.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { FileText, Plus, Clock, FileText as FileTextIcon } from '@lucide/vue'
import { listDocuments, listTemplates, createDocument, uploadDocument } from '@/api/client'
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
const recentDocs = ref<DocumentResponse[]>([])
const templates = ref<Template[]>([])
const loading = ref(true)
const creating = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const [docs, tpls] = await Promise.all([
      listDocuments().catch(() => [] as DocumentResponse[]),
      listTemplates().then(r => (r.data || []) as Template[]).catch(() => [] as Template[]),
    ])
    recentDocs.value = docs.slice(0, 6)
    templates.value = tpls.slice(0, 3)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

async function createNew() {
  if (creating.value) return
  creating.value = true
  try {
    const doc = await createDocument('Nuovo documento')
    router.push(`/documents/${doc.id}`)
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
  } finally {
    creating.value = false
  }
}

async function handleDrop(file: File) {
  try {
    const doc = await uploadDocument(file)
    router.push(`/documents/${doc.id}`)
  } catch {
    // silently fail, user can retry from sidebar
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
  <div class="flex h-screen bg-surface">
    <div class="hidden md:block w-64 shrink-0">
      <DocumentListPanel />
    </div>

    <main class="flex-1 overflow-y-auto">
      <div class="max-w-4xl mx-auto p-6 md:p-8 lg:p-10">
        <!-- Hero -->
        <div class="text-center mb-10">
          <div class="flex justify-center mb-4">
            <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
              <FileText class="w-8 h-8 text-primary" />
            </div>
          </div>
          <h1 class="text-2xl font-bold text-foreground mb-2">DocForge</h1>
          <p class="text-sm text-foreground/50 max-w-sm mx-auto mb-6">
            Crea, modifica e collabora su documenti con l'assistenza dell'AI
          </p>
          <button
            class="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary-light transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="creating"
            @click="createNew"
          >
            <Plus class="w-4 h-4" />
            {{ creating ? 'Creazione...' : 'Nuovo Documento' }}
          </button>
        </div>

        <LoadingSpinner v-if="loading" />

        <template v-else>
          <!-- Recent Documents -->
          <section v-if="recentDocs.length" class="mb-10">
            <h2 class="text-lg font-semibold text-foreground mb-4">Documenti recenti</h2>
            <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div
                v-for="doc in recentDocs"
                :key="doc.id"
                class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer group"
                @click="navigateToDoc(doc.id)"
              >
                <div class="flex items-start gap-3">
                  <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileTextIcon class="w-4 h-4 text-primary" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-foreground truncate">{{ doc.title || 'Untitled' }}</p>
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
                class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer group"
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

          <!-- Empty state (no docs, no templates) -->
          <div v-if="!recentDocs.length && !templates.length" class="text-center py-12">
            <FileTextIcon class="w-10 h-10 text-foreground/20 mx-auto mb-3" />
            <p class="text-sm text-foreground/50">Nessun documento ancora. Crea il tuo primo documento per iniziare.</p>
          </div>
        </template>
      </div>
    </main>

    <DropZoneOverlay @dropped="handleDrop" />
  </div>
</template>
