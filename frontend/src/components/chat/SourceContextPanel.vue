<script setup lang="ts">
import { ref } from 'vue'
import { FileText, ChevronDown, ChevronRight } from '@lucide/vue'
import EmptyState from '@/components/common/EmptyState.vue'

interface SourceDoc {
  id: string
  title: string
  type: 'document' | 'clause' | 'template'
  confidence: number
  chunks: Array<{ id: string; text: string }>
}

const sources = ref<SourceDoc[]>([])
const expandedSources = ref<Set<string>>(new Set())

function toggleSource(id: string) {
  const newSet = new Set(expandedSources.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSources.value = newSet
}

const hasSources = () => sources.value.length > 0
</script>

<template>
  <div
    v-if="hasSources()"
    class="border-t border-primary/10 px-4 py-2 max-h-40 overflow-y-auto"
  >
    <h3 class="text-[11px] font-semibold text-foreground/40 uppercase tracking-wider mb-2">
      Fonti utilizzate
    </h3>
    <div class="space-y-1">
      <div
        v-for="src in sources"
        :key="src.id"
        class="rounded-md border border-primary/10 overflow-hidden"
      >
        <button
          class="w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-left text-foreground/70 hover:bg-primary/5 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="toggleSource(src.id)"
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
          <ChevronDown v-if="expandedSources.has(src.id)" class="w-3 h-3 text-foreground/30" />
          <ChevronRight v-else class="w-3 h-3 text-foreground/30" />
        </button>
        <div v-if="expandedSources.has(src.id)" class="px-3 pb-2 space-y-1">
          <p
            v-for="chunk in src.chunks"
            :key="chunk.id"
            class="text-[11px] text-foreground/50 leading-relaxed"
          >
            {{ chunk.text }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
