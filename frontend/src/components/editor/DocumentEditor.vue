<script setup lang="ts">
import { ref, shallowReactive, computed, onMounted, watch, watchEffect, nextTick, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Editor } from '@tiptap/core'
import { useToast } from '@/composables/useToast'
import TiptapEditor from './TiptapEditor.vue'
import DocumentOutline from './DocumentOutline.vue'
import ChatDock from '@/components/chat/ChatDock.vue'
import SuggestionReviewBar from '@/components/review/SuggestionReviewBar.vue'
import DiffInspector from '@/components/review/DiffInspector.vue'
import CommentThreadPanel from '@/components/review/CommentThreadPanel.vue'
import SourceDocumentsPanel from '@/components/sources/SourceDocumentsPanel.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { useEditorStore } from '@/stores/editorStore'
import { useDocumentStore } from '@/stores/documentStore'
import { useDocumentDiff } from '@/composables/useDocumentDiff'
import { saveDocumentVersion, diffDocumentVersion } from '@/api/client'
import { PanelLeftOpen, PanelLeftClose, Layers, MessageSquare, Save, Pencil, BookOpen, ArrowLeft, ChevronRight, FileText, X } from '@lucide/vue'

const route = useRoute()
const router = useRouter()
const editorStore = useEditorStore()
const documentStore = useDocumentStore()
const editorRef = ref<InstanceType<typeof TiptapEditor> | null>(null)
const toast = useToast()
const { summary: diffSummary, setDocuments } = useDocumentDiff()

function modeFromRoute(): 'compose' | 'review' | 'diff' {
  const n = route.name as string
  return n?.includes('review') ? 'review' : n?.includes('diff') ? 'diff' : 'compose'
}
const mode = ref<'compose' | 'review' | 'diff'>(modeFromRoute())
// The same component is reused across /documents/:id, /:id/review and
// /:id/diff; a route change that does NOT change the id must still resync mode.
watch(() => route.name, () => { mode.value = modeFromRoute() })

// Chat-first layout: the conversation is the primary surface; the document panel
// (the "artifact") slides in on the right only when there is content to show.
const showDocPanel = ref(false)
const docTab = ref<'editor' | 'sources' | 'comments' | 'diff'>('editor')

const isReviewMode = computed(() => mode.value === 'review')
const isDiffMode = computed(() => mode.value === 'diff')

const hasDocContent = computed(() => {
  if (documentStore.sectionCount > 0) return true
  const c = documentStore.content as { content?: unknown[] } | null
  return !!(c && Array.isArray(c.content) && c.content.length > 0)
})

// Auto-open the document panel the moment real content appears (false -> true
// only), mirroring Claude's artifact behaviour. Never force it open on every save.
watch(hasDocContent, (has, was) => {
  if (has && !was) showDocPanel.value = true
})

function toggleDoc() {
  showDocPanel.value = !showDocPanel.value
}

type DocTab = 'editor' | 'sources' | 'comments' | 'diff'
const docTabs = computed(() => {
  const t: { id: DocTab; icon: Component; label: string }[] = [
    { id: 'editor', icon: FileText, label: 'Documento' },
    { id: 'sources', icon: BookOpen, label: 'Fonti' },
    { id: 'comments', icon: MessageSquare, label: 'Commenti' },
  ]
  if (isDiffMode.value) t.push({ id: 'diff', icon: Layers, label: 'Diff' })
  return t
})

// Stable object whose `.value` updates reactively once the Tiptap editor
// resolves (editorRef starts null). A fresh computed object each tick would be
// captured stale by useEditorContext, leaving edit-context permanently null.
const editorProp = shallowReactive<{ value: Editor | null }>({ value: null })
watchEffect(() => {
  editorProp.value = (editorRef.value as any)?.editor || null
})

// Walk a ProseMirror JSON fragment collecting its text, for the version diff.
function pmText(nodes: unknown): string {
  if (!Array.isArray(nodes)) return ''
  let out = ''
  for (const n of nodes as Array<Record<string, unknown>>) {
    if (typeof n?.text === 'string') out += n.text
    if (Array.isArray(n?.content)) out += pmText(n.content)
  }
  return out
}

async function loadDiff(docId: string) {
  try {
    const v1 = Number(route.params.v1)
    const v2 = route.params.v2 != null ? Number(route.params.v2) : undefined
    const data = await diffDocumentVersion(docId, v1, v2)
    setDocuments(
      { textContent: pmText(data?.sections_v1) } as any,
      { textContent: pmText(data?.sections_v2) } as any,
    )
  } catch (e) {
    console.error('Failed to load version diff:', e)
  }
}

async function loadDoc(docId: string) {
  if (!docId) return
  await documentStore.fetchDocument(docId)
  if (isDiffMode.value) {
    docTab.value = 'diff'
    showDocPanel.value = true
    await loadDiff(docId)
  } else {
    docTab.value = 'editor'
    // Open the artifact panel iff the freshly-loaded document has content.
    // (The false->true edge watcher can't fire on doc->doc nav when both docs
    // have content, so derive it explicitly here.) Reopening stays user-driven.
    showDocPanel.value = hasDocContent.value
  }
}

onMounted(() => { loadDoc(route.params.id as string) })

// Promote-to-document and inter-document navigation reuse this component;
// refetch and re-derive panel/tab state when the id changes.
watch(() => route.params.id, (id) => { if (id) loadDoc(id as string) })

function setMode(m: 'compose' | 'review' | 'diff') {
  mode.value = m
}

function handleNavigateSection(sectionId: string) {
  editorStore.setActiveSection(sectionId)
  ;(editorRef.value as any)?.scrollToSection?.(sectionId)
}

function handleToggleSectionStatus(sectionId: string) {
  const section = documentStore.sections.find((s) => s.id === sectionId)
  if (!section) return
  const newStatus = section.status === 'draft' ? 'approved' : 'draft'

  // Update ProseMirror state (triggers auto-save)
  ;(editorRef.value as any)?.updateSectionAttrs?.(sectionId, { status: newStatus })

  // Optimistic update for outline display
  const idx = documentStore.sections.findIndex((s) => s.id === sectionId)
  if (idx !== -1) {
    documentStore.sections[idx] = { ...documentStore.sections[idx], status: newStatus }
  }
}

function handleRenameSection(sectionId: string, newTitle: string) {
  // Update ProseMirror state (triggers auto-save)
  ;(editorRef.value as any)?.updateSectionAttrs?.(sectionId, { title: newTitle })

  // Optimistic update for outline display
  const idx = documentStore.sections.findIndex((s) => s.id === sectionId)
  if (idx !== -1) {
    documentStore.sections[idx] = { ...documentStore.sections[idx], title: newTitle }
  }
}

function handleRetry() {
  loadDoc(route.params.id as string)
}

const isEditingTitle = ref(false)
const editingTitle = ref('')
const titleInputRef = ref<HTMLInputElement>()

function startEditTitle() {
  editingTitle.value = documentStore.title
  isEditingTitle.value = true
  nextTick(() => titleInputRef.value?.focus())
}

async function saveTitle() {
  if (!isEditingTitle.value) return
  isEditingTitle.value = false
  const trimmed = editingTitle.value.trim()
  if (!trimmed) {
    toast.error('Il titolo non può essere vuoto')
    return
  }
  if (trimmed !== documentStore.title) {
    try {
      await documentStore.updateTitle(trimmed)
      toast.success('Titolo aggiornato')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Errore nell\'aggiornamento del titolo')
    }
  }
}

function cancelEditTitle() {
  isEditingTitle.value = false
  editingTitle.value = ''
}

const savingVersion = ref(false)
const versionSaved = ref(false)

async function saveVersion() {
  const docId = route.params.id as string
  if (!docId || savingVersion.value) return
  savingVersion.value = true
  versionSaved.value = false
  try {
    await saveDocumentVersion(docId)
    versionSaved.value = true
    documentStore.version += 1
    toast.success('Versione salvata')
    setTimeout(() => { versionSaved.value = false }, 2000)
  } catch (e: any) {
    toast.error('Salvataggio versione fallito')
    console.error('Failed to save version:', e)
  } finally {
    savingVersion.value = false
  }
}
</script>

<template>
  <div class="relative flex min-h-0 flex-1 bg-surface">
    <!-- PRIMARY: Chat -->
    <main class="flex flex-1 flex-col min-w-0">
      <!-- Slim chat top bar -->
      <header class="h-12 shrink-0 border-b border-primary/10 bg-surface flex items-center gap-2 px-3">
        <button
          class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          title="Torna al workspace"
          aria-label="Torna al workspace"
          @click="router.push('/workspace/default')"
        >
          <ArrowLeft class="w-4 h-4" />
        </button>

        <div class="flex items-center gap-1 text-xs text-foreground/50 min-w-0">
          <router-link to="/workspace/default" class="hover:text-primary transition-colors shrink-0">
            Workspace
          </router-link>
          <template v-if="documentStore.title">
            <ChevronRight class="h-3 w-3 shrink-0" />
            <span class="text-foreground/70 truncate min-w-0">{{ documentStore.title }}</span>
          </template>
        </div>

        <span class="flex-1" />

        <!-- Document toggle: only when there is something to show -->
        <button
          v-if="hasDocContent"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="showDocPanel ? 'bg-primary/10 text-primary' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
          :title="showDocPanel ? 'Nascondi documento' : 'Mostra documento'"
          @click="toggleDoc"
        >
          <FileText class="w-3.5 h-3.5" />
          Documento
        </button>
      </header>

      <!-- Centered conversation column (widens only when the doc panel is closed) -->
      <div class="flex flex-1 min-h-0 justify-center">
        <div class="flex w-full flex-col min-h-0" :class="showDocPanel ? '' : 'max-w-3xl'">
          <ChatDock
            :editor="editorProp"
            :document-id="route.params.id as string"
          />
        </div>
      </div>
    </main>

    <!-- ARTIFACT: Document panel (only when content exists / user opened it) -->
    <Transition name="docpanel">
      <aside
        v-if="showDocPanel"
        class="absolute inset-y-0 right-0 z-20 flex w-full flex-col border-l border-primary/10 bg-surface shadow-xl
               lg:static lg:z-auto lg:w-[48%] lg:max-w-3xl lg:shadow-none xl:w-[46rem]"
      >
        <!-- Doc toolbar -->
        <header class="h-12 shrink-0 border-b border-primary/10 bg-surface flex items-center gap-1 px-2">
          <!-- View tabs -->
          <div class="flex items-center gap-0.5" role="tablist">
            <button
              v-for="t in docTabs"
              :key="t.id"
              role="tab"
              :aria-selected="docTab === t.id"
              :aria-label="t.label"
              class="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :class="docTab === t.id ? 'bg-primary/10 text-primary' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
              @click="docTab = t.id"
            >
              <component :is="t.icon" class="w-3.5 h-3.5" />
              <span class="hidden sm:inline">{{ t.label }}</span>
            </button>
          </div>

          <span class="flex-1" />

          <!-- Editor-only controls -->
          <template v-if="docTab === 'editor'">
            <button
              class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :title="editorStore.showOutline ? 'Nascondi struttura' : 'Mostra struttura'"
              aria-label="Mostra o nascondi la struttura del documento"
              @click="editorStore.toggleOutline()"
            >
              <PanelLeftOpen v-if="!editorStore.showOutline" class="w-4 h-4" />
              <PanelLeftClose v-else class="w-4 h-4" />
            </button>

            <button
              class="px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :class="mode === 'compose' ? 'bg-primary/10 text-primary' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
              @click="setMode('compose')"
            >
              Compose
            </button>
            <button
              class="px-2.5 py-1.5 text-xs font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :class="mode === 'review' ? 'bg-primary/10 text-primary' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
              @click="setMode('review')"
            >
              Review
            </button>

            <span class="hidden md:inline-flex items-center gap-1.5 text-xs font-medium ml-1"
              :class="{
                'text-cta': documentStore.saveStatus === 'saved',
                'text-warning': documentStore.saveStatus === 'unsaved',
                'text-foreground/40': documentStore.saveStatus === 'saving',
              }"
            >
              <span
                class="w-1.5 h-1.5 rounded-full"
                :class="{
                  'bg-cta': documentStore.saveStatus === 'saved',
                  'bg-warning': documentStore.saveStatus === 'unsaved',
                  'bg-foreground/40 animate-pulse': documentStore.saveStatus === 'saving',
                }"
              />
              <span v-if="documentStore.saveStatus === 'saved'">Salvato</span>
              <span v-else-if="documentStore.saveStatus === 'unsaved'">Non salvato</span>
              <span v-else>Salvando...</span>
            </span>

            <button
              class="p-1.5 rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
              :class="versionSaved ? 'text-cta hover:bg-cta/10' : 'text-foreground/50 hover:text-primary hover:bg-primary/8'"
              :title="versionSaved ? 'Versione salvata!' : 'Salva versione'"
              aria-label="Salva una nuova versione del documento"
              :disabled="savingVersion"
              @click="saveVersion"
            >
              <Save class="w-4 h-4" />
            </button>
          </template>

          <span class="w-px h-5 bg-primary/10 mx-1" />

          <!-- Close panel -->
          <button
            class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            title="Chiudi documento"
            aria-label="Chiudi pannello documento"
            @click="showDocPanel = false"
          >
            <X class="w-4 h-4" />
          </button>
        </header>

        <!-- Editor tab — kept mounted (v-show) so the live editor and its
             edit-context survive tab switches instead of being torn down. -->
        <div v-show="docTab === 'editor'" style="display: contents">
          <!-- Title -->
          <div v-if="documentStore.title" class="px-4 pt-3 pb-2 border-b border-primary/5 shrink-0">
            <div class="group flex items-center gap-2">
              <template v-if="isEditingTitle">
                <input
                  ref="titleInputRef"
                  v-model="editingTitle"
                  @keydown.enter="saveTitle"
                  @keydown.escape="cancelEditTitle"
                  @blur="saveTitle"
                  class="text-lg font-bold text-foreground bg-transparent border-b-2 border-primary outline-none px-0 py-0 w-full"
                  aria-label="Titolo del documento"
                />
              </template>
              <template v-else>
                <h1 class="text-lg font-bold text-foreground cursor-pointer truncate" @dblclick="startEditTitle">
                  {{ documentStore.title }}
                </h1>
                <button
                  @click="startEditTitle"
                  class="opacity-60 hover:opacity-100 transition-opacity p-1 rounded hover:bg-primary/8 text-foreground/50 hover:text-primary cursor-pointer shrink-0"
                  title="Rinomina documento"
                  aria-label="Rinomina documento"
                >
                  <Pencil class="h-4 w-4" />
                </button>
              </template>
            </div>
          </div>

          <div class="flex flex-1 min-h-0">
            <!-- Outline -->
            <Transition name="sidebar">
              <div
                v-if="editorStore.showOutline"
                class="w-56 shrink-0 border-r border-primary/10 flex flex-col min-h-0 overflow-hidden"
              >
                <DocumentOutline
                  @navigate-section="handleNavigateSection"
                  @toggle-section-status="handleToggleSectionStatus"
                  @rename-section="handleRenameSection"
                />
              </div>
            </Transition>

            <!-- Editor surface -->
            <div class="flex-1 min-w-0 flex flex-col min-h-0">
              <div v-if="documentStore.loading && !documentStore.title" class="flex-1 flex items-center justify-center">
                <LoadingSpinner />
              </div>
              <ErrorMessage
                v-else-if="documentStore.error && !documentStore.loading"
                :message="documentStore.error"
                retry-label="Riprova"
                @retry="handleRetry"
              />
              <div v-else class="flex-1 overflow-y-auto bg-surface/40">
                <div class="max-w-2xl mx-auto py-6 px-2">
                  <div class="bg-card rounded-lg shadow-sm border border-primary/10">
                    <TiptapEditor
                      ref="editorRef"
                      :key="route.params.id as string"
                      :document-id="route.params.id as string"
                      :content="(documentStore.content as Record<string, unknown> | undefined)"
                      @save="documentStore.saveContent"
                    />
                  </div>
                </div>
              </div>
              <SuggestionReviewBar v-if="isReviewMode" :editor="editorProp" />
            </div>
          </div>
        </div>

        <!-- Sources tab -->
        <SourceDocumentsPanel
          v-if="docTab === 'sources'"
          :document-id="route.params.id as string"
        />

        <!-- Comments tab -->
        <CommentThreadPanel
          v-else-if="docTab === 'comments'"
          :document-id="route.params.id as string"
          @close="docTab = 'editor'"
        />

        <!-- Diff tab -->
        <DiffInspector
          v-else-if="docTab === 'diff'"
          :summary="diffSummary"
        />
      </aside>
    </Transition>
  </div>
</template>

<style scoped>
.sidebar-enter-active,
.sidebar-leave-active {
  transition: width 0.2s ease, opacity 0.2s ease;
  overflow: hidden;
}

.sidebar-enter-from,
.sidebar-leave-to {
  width: 0 !important;
  opacity: 0;
}

.docpanel-enter-active,
.docpanel-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}

.docpanel-enter-from,
.docpanel-leave-to {
  transform: translateX(16px);
  opacity: 0;
}
</style>
