<script setup lang="ts">
import { computed } from 'vue'
import { Layers, Plus, Minus, Edit3, AlertTriangle, Info } from '@lucide/vue'
import type { DiffSummary } from '@/types/document'
import EmptyState from '@/components/common/EmptyState.vue'

const props = defineProps<{
  summary: DiffSummary | null
}>()

const hasDiff = computed(() => props.summary !== null && props.summary.operations.length > 0)

const impactBadge = computed(() => {
  if (!props.summary) return { class: 'text-foreground/40 bg-foreground/5', label: 'None' }
  const count = props.summary.wordsChanged
  if (count > 100) return { class: 'text-danger bg-danger/10', label: 'High' }
  if (count > 20) return { class: 'text-warning bg-warning/10', label: 'Medium' }
  return { class: 'text-cta bg-cta/10', label: 'Low' }
})

const nonEqualOps = computed(() => {
  if (!props.summary) return []
  return props.summary.operations.filter((o) => o.type !== 'equal')
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <Layers class="w-4 h-4 text-primary" />
      <h2 class="text-sm font-semibold text-foreground">Diff Inspector</h2>
    </div>

    <div class="flex-1 overflow-y-auto">
      <EmptyState
        v-if="!hasDiff"
        title="Nessuna differenza"
        description="Carica due versioni per confrontarle"
      />

      <template v-if="hasDiff && summary">
        <!-- Summary -->
        <div class="px-4 py-3 space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-foreground/50">Impact</span>
            <span
              class="text-[10px] font-medium px-2 py-0.5 rounded-full"
              :class="impactBadge.class"
            >
              {{ impactBadge.label }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs text-foreground/50">Sections added</span>
            <span class="text-xs font-medium flex items-center gap-1 text-cta">
              <Plus class="w-3 h-3" />
              {{ summary.sectionsAdded }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs text-foreground/50">Sections removed</span>
            <span class="text-xs font-medium flex items-center gap-1 text-danger">
              <Minus class="w-3 h-3" />
              {{ summary.sectionsRemoved }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs text-foreground/50">Sections modified</span>
            <span class="text-xs font-medium flex items-center gap-1 text-warning">
              <Edit3 class="w-3 h-3" />
              {{ summary.sectionsModified }}
            </span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-xs text-foreground/50">Words changed</span>
            <span class="text-xs font-medium text-foreground/70">{{ summary.wordsChanged }}</span>
          </div>
        </div>

        <div class="border-t border-primary/10" />

        <!-- Operations list -->
        <div class="px-4 py-2">
          <h3 class="text-[11px] font-semibold text-foreground/40 uppercase tracking-wider mb-2">
            Operations ({{ nonEqualOps.length }})
          </h3>
          <div class="space-y-1">
            <div
              v-for="(op, idx) in nonEqualOps"
              :key="idx"
              class="flex items-start gap-2 py-1.5 px-2 rounded-md text-xs"
              :class="{
                'bg-cta/5': op.type === 'insert',
                'bg-danger/5': op.type === 'delete',
                'bg-warning/5': op.type === 'replace',
              }"
            >
              <span
                class="flex-shrink-0 mt-0.5"
                :class="{
                  'text-cta': op.type === 'insert',
                  'text-danger': op.type === 'delete',
                  'text-warning': op.type === 'replace',
                }"
              >
                <Plus v-if="op.type === 'insert'" class="w-3 h-3" />
                <Minus v-else-if="op.type === 'delete'" class="w-3 h-3" />
                <AlertTriangle v-else class="w-3 h-3" />
              </span>
              <div class="flex-1 min-w-0">
                <span class="text-[10px] font-medium uppercase tracking-wider text-foreground/40">
                  {{ op.type }}
                </span>
                <p v-if="op.originalText" class="text-danger/70 line-through truncate">{{ op.originalText }}</p>
                <p v-if="op.newText" class="text-cta/80 truncate">{{ op.newText }}</p>
                <p v-else class="text-foreground/50 truncate">{{ op.value }}</p>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
