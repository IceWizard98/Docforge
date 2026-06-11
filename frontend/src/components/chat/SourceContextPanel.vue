<script setup lang="ts">
import { ref, computed } from 'vue'
import { FileText, ChevronDown, ChevronRight, ChevronUp } from '@lucide/vue'
import type { SourceRef } from '@/types/document'

const props = defineProps<{
  sources: SourceRef[]
}>()

const panelOpen = ref(true)
const expandedSources = ref<Set<string>>(new Set())

const hasSources = computed(() => props.sources.length > 0)

function toggleSource(id: string) {
  const newSet = new Set(expandedSources.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSources.value = newSet
}
</script>

<template>
  <div
    v-if="hasSources"
    class="border-t border-primary/10"
  >
    <button
      class="w-full flex items-center gap-2 px-4 py-2 text-left hover:bg-primary/5 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="panelOpen = !panelOpen"
    >
      <h3 class="text-[11px] font-semibold text-foreground/40 uppercase tracking-wider">
        Fonti utilizzate
      </h3>
      <span class="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary/60 font-medium">
        {{ sources.length }}
      </span>
      <div class="flex-1" />
      <ChevronUp v-if="panelOpen" class="w-3 h-3 text-foreground/30 transition-transform duration-200" />
      <ChevronDown v-else class="w-3 h-3 text-foreground/30 transition-transform duration-200" />
    </button>

    <Transition
      enter-from-class="max-h-0 opacity-0"
      enter-active-class="overflow-hidden transition-all duration-200 ease-out"
      enter-to-class="max-h-80 opacity-100"
      leave-from-class="max-h-80 opacity-100"
      leave-active-class="overflow-hidden transition-all duration-200 ease-in"
      leave-to-class="max-h-0 opacity-0"
    >
      <div v-if="panelOpen" class="px-4 pb-2 space-y-1 max-h-40 overflow-y-auto">
        <div
          v-for="src in sources"
          :key="src.sourceDocId"
          class="rounded-md border border-primary/10 overflow-hidden"
        >
          <button
            class="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-left text-foreground/70 hover:bg-primary/5 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            @click="toggleSource(src.sourceDocId)"
          >
            <FileText class="w-3 h-3 text-primary/50 flex-shrink-0" />
            <span class="flex-1 truncate font-medium">{{ src.title }}</span>
            <span
              class="text-[10px] px-1 py-0.5 rounded-full"
              :class="
                src.confidence > 0.8
                  ? 'bg-cta/10 text-cta'
                  : src.confidence > 0.5
                    ? 'bg-warning/10 text-warning'
                    : 'bg-danger/10 text-danger'
              "
            >
              {{ Math.round(src.confidence * 100) }}%
            </span>
            <ChevronDown v-if="expandedSources.has(src.sourceDocId)" class="w-3 h-3 text-foreground/30" />
            <ChevronRight v-else class="w-3 h-3 text-foreground/30" />
          </button>
          <div v-if="expandedSources.has(src.sourceDocId)" class="px-3 pb-2 space-y-1">
            <p
              v-if="src.snippet"
              class="text-[11px] text-foreground/50 leading-relaxed"
            >
              {{ src.snippet }}
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
