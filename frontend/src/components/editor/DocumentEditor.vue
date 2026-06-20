<script setup lang="ts">
import { ref, shallowReactive, computed, onMounted, watch, watchEffect, nextTick } from 'vue'
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
import { saveDocumentVersion } from '@/api/client'
import { PanelRightOpen, PanelRightClose, PanelLeftOpen, PanelLeftClose, Layers, MessageSquare, Save, Pencil, BookOpen, ArrowLeft, ChevronRight, Bot } from '@lucide/vue'
import RightPanelTabs from './RightPanelTabs.vue'
import type { PanelTab } from './RightPanelTabs.vue'

const route = useRoute()
const router = useRouter()
const editorStore = useEditorStore()
const documentStore = useDocumentStore()
const editorRef = ref<InstanceType<typeof TiptapEditor> | null>(null)
const toast = useToast()
const { summary: diffSummary, setDocuments } = useDocumentDiff()

watch(() => documentStore.version, () => {
  // Version comparison available via /documents/:id/diff/:v1/:v2
})

const mode = ref<'compose' | 'review' | 'diff'>(
  (route.name as string)?.includes('review') ? 'review' : (route.name as string)?.includes('diff') ? 'diff' : 'compose',
)

const rightPanelOpen = ref(false)
const rightActiveTab = ref('chat')

const tabs = computed<PanelTab[]>(() => {
  const t: PanelTab[] = [
    { id: 'chat', icon: Bot, label: 'Assistant' },
    { id: 'comments', icon: MessageSquare, label: 'Commenti' },
    { id: 'sources', icon: BookOpen, label: 'Fonti' },
  ]
  if (isDiffMode.value) {
    t.push({ id: 'diff', icon: Layers, label: 'Diff' })
  }
  return t
})

function toggleRightPanel(tabId: string) {
  if (rightActiveTab.value === tabId && rightPanelOpen.value) {
    rightPanelOpen.value = false
  } else {
    rightActiveTab.value = tabId
    rightPanelOpen.value = true
  }
}

const isReviewMode = computed(() => mode.value === 'review')
const isDiffMode = computed(() => mode.value === 'diff')

// Stable object whose `.value` updates reactively once the Tiptap editor
// resolves (editorRef starts null). A fresh computed object each tick would be
// captured stale by useEditorContext, leaving edit-context permanently null.
const editorProp = shallowReactive<{ value: Editor | null }>({ value: null })
watchEffect(() => {
  editorProp.value = (editorRef.value as any)?.editor || null
})

onMounted(() => {
  const docId = route.params.id as string
  if (docId) {
    documentStore.fetchDocument(docId)
  }
})

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
  const docId = route.params.id as string
  if (docId) {
    documentStore.fetchDocument(docId)
  }
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
  <div class="flex min-h-0 flex-1 bg-surface">
    <!-- Left Sidebar (Outline) -->
    <Transition name="sidebar">
      <div
        v-if="editorStore.showOutline"
        class="w-64 border-r border-primary/10 flex flex-col min-h-0 flex-1 overflow-hidden"
      >
        <DocumentOutline
          @navigate-section="handleNavigateSection"
          @toggle-section-status="handleToggleSectionStatus"
          @rename-section="handleRenameSection"
        />
      </div>
    </Transition>

    <!-- Main Editor Area -->
    <main class="flex-1 flex flex-col min-w-0">
      <!-- Toolbar -->
      <header class="h-12 border-b border-primary/10 bg-surface flex items-center px-4 gap-1">
        <!-- Outline toggle -->
        <button
          class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :title="editorStore.showOutline ? 'Hide outline' : 'Show outline'"
          aria-label="Mostra o nascondi la struttura del documento"
          @click="editorStore.toggleOutline()"
        >
          <PanelLeftOpen v-if="!editorStore.showOutline" class="w-4 h-4" />
          <PanelLeftClose v-else class="w-4 h-4" />
        </button>

        <span class="w-px h-5 bg-primary/10 mx-1" />

        <!-- Compose / Review toggle -->
        <button
          class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="mode === 'compose' ? 'bg-primary/10 text-primary' : 'text-foreground/70 hover:text-primary hover:bg-primary/8'"
          @click="setMode('compose')"
        >
          Compose
        </button>
        <button
          class="px-3 py-1.5 text-sm font-medium rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="mode === 'review' ? 'bg-primary/10 text-primary' : 'text-foreground/70 hover:text-primary hover:bg-primary/8'"
          @click="setMode('review')"
        >
          Review
        </button>

        <span class="flex-1" />

        <span class="text-xs text-foreground/40 font-medium">
          v{{ documentStore.version }} · {{ documentStore.status }}
        </span>

        <!-- Save indicator -->
        <span
          class="flex items-center gap-1.5 text-xs font-medium"
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

        <!-- Save Version button -->
        <button
          class="p-1.5 rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="versionSaved ? 'text-green-600 hover:bg-green-50' : 'text-foreground/50 hover:text-primary hover:bg-primary/8'"
          :title="versionSaved ? 'Version saved!' : 'Save version'"
          aria-label="Salva una nuova versione del documento"
          :disabled="savingVersion"
          @click="saveVersion"
        >
          <Save class="w-4 h-4" />
        </button>

        <span class="w-px h-5 bg-primary/10 mx-1" />

        <!-- Right panel toggle -->
        <button
          class="p-1.5 rounded-md transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="rightPanelOpen ? 'text-primary bg-primary/10' : 'text-foreground/50 hover:text-primary hover:bg-primary/8'"
          :title="rightPanelOpen ? 'Chiudi pannello' : 'Apri pannello'"
          aria-label="Mostra o nascondi il pannello laterale"
          @click="rightPanelOpen = !rightPanelOpen"
        >
          <PanelRightOpen v-if="!rightPanelOpen" class="w-4 h-4" />
          <PanelRightClose v-else class="w-4 h-4" />
        </button>
      </header>

      <!-- Document title & breadcrumb -->
      <div v-if="documentStore.title" class="px-4 md:px-6 pt-3 pb-2 border-b border-primary/5">
        <div class="flex items-center gap-1 text-xs text-foreground/50 mb-2 overflow-hidden">
          <button
            @click="router.push('/workspace/default')"
            class="p-1 -ml-1 rounded hover:bg-primary/8 text-foreground/50 hover:text-primary transition-colors cursor-pointer shrink-0"
            title="Torna al workspace"
            aria-label="Torna al workspace"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
          </button>
          <router-link to="/workspace/default" class="hover:text-primary transition-colors shrink-0">
            Workspace
          </router-link>
          <ChevronRight class="h-3 w-3 shrink-0" />
          <span class="text-foreground/70 truncate min-w-0">{{ documentStore.title }}</span>
        </div>
        <div class="group flex items-center gap-2">
          <template v-if="isEditingTitle">
            <input
              ref="titleInputRef"
              v-model="editingTitle"
              @keydown.enter="saveTitle"
              @keydown.escape="cancelEditTitle"
              @blur="saveTitle"
              class="text-xl font-bold text-foreground bg-transparent border-b-2 border-primary outline-none px-0 py-0 w-full max-w-md"
              aria-label="Titolo del documento"
            />
          </template>
          <template v-else>
            <h1
              class="text-xl font-bold text-foreground cursor-pointer truncate"
              @dblclick="startEditTitle"
            >{{ documentStore.title }}</h1>
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

      <!-- Loading -->
      <div v-if="documentStore.loading && !documentStore.title" class="flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>

      <!-- Error -->
      <ErrorMessage
        v-else-if="documentStore.error && !documentStore.loading"
        :message="documentStore.error"
        retry-label="Riprova"
        @retry="handleRetry"
      />

      <!-- Editor -->
      <div v-else class="flex-1 overflow-y-auto bg-surface/40">
        <div class="max-w-3xl mx-auto py-8">
          <div class="bg-card rounded-lg shadow-sm border border-primary/10">
            <TiptapEditor
              ref="editorRef"
              :document-id="route.params.id as string"
              :content="(documentStore.content as Record<string, unknown> | undefined)"
              @save="documentStore.saveContent"
            />
          </div>
        </div>
      </div>

      <!-- Review mode bottom bar -->
      <SuggestionReviewBar v-if="isReviewMode" :editor="editorProp" />
    </main>

    <!-- Right Panel with Tabs -->
    <Transition name="sidebar">
      <aside
        v-if="rightPanelOpen"
        class="w-96 border-l border-primary/10 bg-surface flex flex-col overflow-hidden"
      >
        <RightPanelTabs
          :tabs="tabs"
          :active-tab="rightActiveTab"
          @update:active-tab="toggleRightPanel"
        >
          <ChatDock
            v-show="rightActiveTab === 'chat'"
            :editor="editorProp"
            :document-id="route.params.id as string"
          />
          <CommentThreadPanel
            v-if="rightActiveTab === 'comments'"
            :document-id="route.params.id as string"
            @close="rightPanelOpen = false"
          />
          <SourceDocumentsPanel
            v-if="rightActiveTab === 'sources'"
            :document-id="route.params.id as string"
          />
          <DiffInspector
            v-if="rightActiveTab === 'diff'"
            :summary="diffSummary"
          />
        </RightPanelTabs>
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
</style>
