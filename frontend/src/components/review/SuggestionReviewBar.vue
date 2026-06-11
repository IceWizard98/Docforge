<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useSuggestionStore } from '@/api/suggestionStore'
import { useRoute } from 'vue-router'
import type { Editor } from '@tiptap/core'
import { Check, X, ChevronLeft, ChevronRight, CheckCheck, XCircle, Loader2 } from '@lucide/vue'

const props = defineProps<{
  editor: { value: Editor | null }
}>()

const route = useRoute()
const suggestionStore = useSuggestionStore()
const persisting = ref<Set<string>>(new Set())

const hasSuggestions = computed(() => suggestionStore.totalCount > 0)
const hasPending = computed(() => suggestionStore.pendingCount > 0)

const suggestionTypeLabel = computed(() => {
  const s = suggestionStore.currentSuggestion
  if (!s) return ''
  switch (s.type) {
    case 'insert':
      return 'Insertion'
    case 'delete':
      return 'Deletion'
    case 'replace':
      return 'Replacement'
    default:
      return 'Suggestion'
  }
})

async function persistDecision(suggestionId: string, decision: 'accepted' | 'rejected') {
  persisting.value.add(suggestionId)
  try {
    const editor = props.editor.value
    if (editor) {
      if (decision === 'accepted') {
        editor.commands.acceptSuggestion({ suggestionId })
      } else {
        editor.commands.rejectSuggestion({ suggestionId })
      }
    }
    if (decision === 'accepted') {
      await suggestionStore.acceptSuggestion(suggestionId)
    } else {
      await suggestionStore.rejectSuggestion(suggestionId)
    }
  } catch {
  } finally {
    persisting.value.delete(suggestionId)
  }
}

async function persistAll(decision: 'accepted' | 'rejected') {
  for (const s of suggestionStore.pendingSuggestions) {
    await persistDecision(s.suggestionId, decision)
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (!hasPending.value || !suggestionStore.currentSuggestion) return
  if (e.key === 'ArrowLeft') {
    suggestionStore.goPrev()
    e.preventDefault()
  } else if (e.key === 'ArrowRight') {
    suggestionStore.goNext()
    e.preventDefault()
  } else if (e.key === 'Enter') {
    persistDecision(suggestionStore.currentSuggestion.suggestionId, 'accepted')
    e.preventDefault()
  } else if (e.key === 'Delete' || e.key === 'Escape') {
    persistDecision(suggestionStore.currentSuggestion.suggestionId, 'rejected')
    e.preventDefault()
  }
}

onMounted(() => {
  const docId = route.params.id as string
  if (docId) {
    suggestionStore.loadSuggestions(docId)
  }
  window.addEventListener('keydown', handleKeydown)
})
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div
    v-if="hasSuggestions"
    class="h-14 border-t border-primary/10 bg-surface flex items-center px-4 gap-3 text-sm"
  >
    <!-- Pending count -->
    <span class="text-xs text-foreground/50 font-medium whitespace-nowrap">
      {{ suggestionStore.pendingCount }} / {{ suggestionStore.totalCount }} pending
    </span>

    <span class="w-px h-5 bg-primary/10" />

    <!-- Accept / Reject All -->
    <button
      v-if="hasPending"
      class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md bg-cta/10 text-cta hover:bg-cta/15 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="persistAll('accepted')"
    >
      <CheckCheck class="w-3 h-3" />
      Accept All
    </button>
    <button
      v-if="hasPending"
      class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md bg-danger/10 text-danger hover:bg-danger/15 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="persistAll('rejected')"
    >
      <XCircle class="w-3 h-3" />
      Reject All
    </button>

    <span class="flex-1" />

    <!-- Current suggestion details -->
    <template v-if="suggestionStore.currentSuggestion">
      <span class="text-xs font-medium text-foreground/70">{{ suggestionTypeLabel }}</span>
      <span class="text-xs text-foreground/50">{{ suggestionStore.currentSuggestion.rationale }}</span>

      <!-- Individual accept/reject -->
      <button
        class="p-1 rounded-md text-cta hover:bg-cta/10 transition-colors duration-150 disabled:opacity-50 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        title="Accept"
        :disabled="persisting.has(suggestionStore.currentSuggestion.suggestionId)"
        @click="persistDecision(suggestionStore.currentSuggestion!.suggestionId, 'accepted')"
      >
        <Loader2 v-if="persisting.has(suggestionStore.currentSuggestion.suggestionId)" class="w-3.5 h-3.5 animate-spin" />
        <Check v-else class="w-3.5 h-3.5" />
      </button>
      <button
        class="p-1 rounded-md text-danger hover:bg-danger/10 transition-colors duration-150 disabled:opacity-50 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        title="Reject"
        :disabled="persisting.has(suggestionStore.currentSuggestion.suggestionId)"
        @click="persistDecision(suggestionStore.currentSuggestion!.suggestionId, 'rejected')"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    </template>

    <!-- Navigation -->
    <button
      class="p-1 rounded-md text-foreground/40 hover:text-primary hover:bg-primary/5 transition-colors duration-150 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :disabled="!suggestionStore.canGoPrev"
      @click="suggestionStore.goPrev()"
    >
      <ChevronLeft class="w-3.5 h-3.5" />
    </button>
    <button
      class="p-1 rounded-md text-foreground/40 hover:text-primary hover:bg-primary/5 transition-colors duration-150 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      :disabled="!suggestionStore.canGoNext"
      @click="suggestionStore.goNext()"
    >
      <ChevronRight class="w-3.5 h-3.5" />
    </button>
  </div>
</template>
