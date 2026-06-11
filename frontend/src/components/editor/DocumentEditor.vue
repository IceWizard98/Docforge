<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import TiptapEditor from './TiptapEditor.vue'
import DocumentOutline from './DocumentOutline.vue'
import ChatDock from '@/components/chat/ChatDock.vue'
import SuggestionReviewBar from '@/components/review/SuggestionReviewBar.vue'
import DiffInspector from '@/components/review/DiffInspector.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'
import { useEditorStore } from '@/stores/editorStore'
import { useDocumentStore } from '@/stores/documentStore'
import { PanelRightOpen, PanelRightClose, PanelLeftOpen, PanelLeftClose, Layers } from '@lucide/vue'

const route = useRoute()
const editorStore = useEditorStore()
const documentStore = useDocumentStore()
const editorRef = ref<InstanceType<typeof TiptapEditor> | null>(null)

const mode = ref<'compose' | 'review' | 'diff'>(
  (route.name as string)?.includes('review') ? 'review' : (route.name as string)?.includes('diff') ? 'diff' : 'compose',
)

const showDiffInspector = ref(false)

const isReviewMode = computed(() => mode.value === 'review')
const isDiffMode = computed(() => mode.value === 'diff')

const editorProp = computed(() => ({ value: editorRef.value?.editor || null }))

onMounted(() => {
  const docId = route.params.id as string
  if (docId) {
    documentStore.fetchDocument(docId)
  }
})

function setMode(m: 'compose' | 'review' | 'diff') {
  mode.value = m
}

function handleRetry() {
  const docId = route.params.id as string
  if (docId) {
    documentStore.fetchDocument(docId)
  }
}
</script>

<template>
  <div class="flex h-screen bg-white">
    <!-- Left Sidebar (Outline) -->
    <Transition name="sidebar">
      <div
        v-if="editorStore.showOutline"
        class="w-64 border-r border-primary/10 flex flex-col overflow-hidden"
      >
        <DocumentOutline />
      </div>
    </Transition>

    <!-- Main Editor Area -->
    <main class="flex-1 flex flex-col min-w-0">
      <!-- Toolbar -->
      <header class="h-12 border-b border-primary/10 bg-white flex items-center px-4 gap-1">
        <!-- Outline toggle -->
        <button
          class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :title="editorStore.showOutline ? 'Hide outline' : 'Show outline'"
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

        <!-- Diff inspector toggle -->
        <button
          v-if="isDiffMode"
          class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :title="showDiffInspector ? 'Hide diff inspector' : 'Show diff inspector'"
          @click="showDiffInspector = !showDiffInspector"
        >
          <Layers class="w-4 h-4" />
        </button>

        <span class="text-xs text-foreground/40 font-medium">
          v{{ documentStore.version }} · {{ documentStore.status }}
        </span>

        <span class="w-px h-5 bg-primary/10 mx-1" />

        <!-- Assistant toggle -->
        <button
          class="p-1.5 rounded-md text-foreground/50 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :title="editorStore.showAssistant ? 'Hide assistant' : 'Show assistant'"
          @click="editorStore.toggleAssistant()"
        >
          <PanelRightOpen v-if="!editorStore.showAssistant" class="w-4 h-4" />
          <PanelRightClose v-else class="w-4 h-4" />
        </button>
      </header>

      <!-- Document title -->
      <div v-if="documentStore.title" class="px-6 pt-4 pb-2 border-b border-primary/5">
        <h1 class="text-xl font-bold text-foreground">{{ documentStore.title }}</h1>
      </div>

      <!-- Loading -->
      <div v-if="documentStore.loading && !documentStore.title" class="flex-1 flex items-center justify-center">
        <LoadingSpinner />
      </div>

      <!-- Error -->
      <ErrorMessage
        v-if="documentStore.error && !documentStore.loading"
        :message="documentStore.error"
        retry-label="Riprova"
        @retry="handleRetry"
      />

      <!-- Editor -->
      <div v-else class="flex-1 overflow-y-auto bg-surface/40">
        <div class="max-w-3xl mx-auto py-8">
          <div class="bg-white rounded-lg shadow-sm border border-primary/10">
            <TiptapEditor ref="editorRef" />
          </div>
        </div>
      </div>

      <!-- Review mode bottom bar -->
      <SuggestionReviewBar v-if="isReviewMode" />
    </main>

    <!-- Right Sidebar: Diff Inspector -->
    <Transition name="sidebar">
      <aside
        v-if="isDiffMode && showDiffInspector"
        class="w-72 border-l border-primary/10 bg-surface flex flex-col overflow-hidden"
      >
        <DiffInspector :summary="null" />
      </aside>
    </Transition>

    <!-- Right Sidebar: Assistant / Chat -->
    <Transition name="sidebar">
      <aside
        v-if="editorStore.showAssistant && !isDiffMode"
        class="w-72 border-l border-primary/10 bg-surface flex flex-col overflow-hidden"
      >
        <ChatDock
          :editor="editorProp"
          :document-id="route.params.id as string"
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
</style>
