<script setup lang="ts">
import { computed } from 'vue'
import { useSuggestionStore } from '@/api/suggestionStore'
import { Check, X, ChevronLeft, ChevronRight, CheckCheck, XCircle } from '@lucide/vue'

const suggestionStore = useSuggestionStore()

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
      @click="suggestionStore.acceptAll()"
    >
      <CheckCheck class="w-3 h-3" />
      Accept All
    </button>
    <button
      v-if="hasPending"
      class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-md bg-danger/10 text-danger hover:bg-danger/15 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="suggestionStore.rejectAll()"
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
        class="p-1 rounded-md text-cta hover:bg-cta/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        title="Accept"
        @click="suggestionStore.acceptSuggestion(suggestionStore.currentSuggestion!.suggestionId)"
      >
        <Check class="w-3.5 h-3.5" />
      </button>
      <button
        class="p-1 rounded-md text-danger hover:bg-danger/10 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        title="Reject"
        @click="suggestionStore.rejectSuggestion(suggestionStore.currentSuggestion!.suggestionId)"
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
