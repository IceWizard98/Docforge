<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FileText, Trash2, Plus, Loader2 } from '@lucide/vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import * as api from '@/api/client'

interface Template {
  id: string
  name: string
  description?: string
  category?: string
  doc_type?: string
  created_at: string
}

const templates = ref<Template[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const showCreator = ref(false)
const newName = ref('')
const newDescription = ref('')
const saving = ref(false)
const creating = ref(false)
const router = useRouter()

async function fetchTemplates() {
  loading.value = true
  error.value = null
  try {
    const resp = await api.listTemplates()
    templates.value = (resp.data || []) as Template[]
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to load templates'
  } finally {
    loading.value = false
  }
}

onMounted(fetchTemplates)

async function saveTemplate() {
  if (!newName.value.trim() || saving.value) return
  saving.value = true
  error.value = null
  try {
    const created = await api.createTemplate({
      name: newName.value.trim(),
      description: newDescription.value.trim(),
    })
    templates.value.push({
      id: created.id,
      name: created.name,
      description: created.description,
      category: created.category || 'Generale',
      created_at: (created as any).created_at || new Date().toISOString(),
    })
    showCreator.value = false
    newName.value = ''
    newDescription.value = ''
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to create template'
  } finally {
    saving.value = false
  }
}

async function deleteTemplateItem(id: string) {
  if (!window.confirm('Eliminare questo template?')) return
  error.value = null
  try {
    await api.deleteTemplate(id)
    templates.value = templates.value.filter(t => t.id !== id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to delete template'
  }
}

async function createFromTemplate(tpl: Template) {
  if (creating.value) return
  creating.value = true
  try {
    const doc = await api.createDocument(tpl.name, tpl.doc_type || '')
    router.push(`/documents/${doc.id}`)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Failed to create document from template'
  } finally {
    creating.value = false
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short', year: 'numeric' })
}
</script>

<template>
  <div class="max-w-4xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-foreground">Template</h1>
      <button
        @click="showCreator = true"
        class="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-light transition-colors cursor-pointer"
      >
        <Plus class="h-4 w-4" />
        Nuovo Template
      </button>
    </div>

    <LoadingSpinner v-if="loading" />

    <ErrorMessage
      v-if="error && !loading"
      :message="error"
      retry-label="Riprova"
      @retry="fetchTemplates"
    />

    <EmptyState
      v-else-if="!templates.length"
      :icon="FileText"
      title="Nessun template creato"
      description="Crea un template per iniziare a riutilizzare strutture di documenti"
      action-label="Nuovo template"
      @action="showCreator = true"
    />

    <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="tpl in templates"
        :key="tpl.id"
        class="rounded-lg border border-primary/10 bg-card p-4 hover:border-primary/30 hover:shadow-sm transition-all group cursor-pointer"
        @click="createFromTemplate(tpl)"
      >
        <div class="flex items-start gap-3">
          <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <FileText class="w-5 h-5 text-primary" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-start justify-between gap-2">
              <h3 class="font-medium text-foreground">{{ tpl.name }}</h3>
              <button
                @click.stop="deleteTemplateItem(tpl.id)"
                class="p-1 rounded hover:bg-danger/8 text-foreground/40 hover:text-danger opacity-0 group-hover:opacity-100 transition-all cursor-pointer shrink-0"
                title="Elimina template"
                aria-label="Elimina template"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
            <p v-if="tpl.description" class="text-sm text-foreground/50 mt-1 line-clamp-2">{{ tpl.description }}</p>
            <div class="flex items-center gap-2 mt-3">
              <span class="text-xs bg-primary/8 text-primary px-2 py-0.5 rounded">
                {{ tpl.category || 'Generale' }}
              </span>
              <span class="text-xs text-foreground/40 ml-auto">
                {{ formatDate(tpl.created_at) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showCreator"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
        @click.self="showCreator = false"
      >
        <div class="w-full max-w-md rounded-xl bg-surface p-6 shadow-xl border border-primary/10">
          <h2 class="text-lg font-semibold text-foreground mb-4">Nuovo Template</h2>
          <input
            v-model="newName"
            placeholder="Nome template"
            class="w-full rounded-lg border border-primary/10 bg-card px-3 py-2 text-sm text-foreground placeholder:text-foreground/30 mb-3 focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Nome del template"
            @keydown.enter="saveTemplate"
          />
          <textarea
            v-model="newDescription"
            placeholder="Descrizione (opzionale)"
            rows="2"
            class="w-full rounded-lg border border-primary/10 bg-card px-3 py-2 text-sm text-foreground placeholder:text-foreground/30 mb-4 resize-none focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Descrizione del template"
          />
          <div class="flex justify-end gap-2">
            <button
              @click="showCreator = false"
              class="rounded-lg px-4 py-2 text-sm font-medium text-foreground/70 hover:bg-primary/8 transition-colors cursor-pointer"
            >
              Annulla
            </button>
            <button
              @click="saveTemplate"
              :disabled="!newName.trim() || saving"
              class="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-light transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <Loader2 v-if="saving" class="h-3.5 w-3.5 animate-spin" />
              Crea
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
