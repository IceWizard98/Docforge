<script setup lang="ts">
import { ref } from 'vue'
import { nodeViewProps, NodeViewWrapper, NodeViewContent } from '@tiptap/vue-3'
import { ChevronDown, ChevronRight, GripVertical, X } from '@lucide/vue'

const props = defineProps(nodeViewProps)

const collapsed = ref(false)

function toggleCollapse() {
  collapsed.value = !collapsed.value
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'approved':
      return 'text-cta'
    case 'draft':
      return 'text-primary'
    default:
      return 'text-foreground/50'
  }
}
</script>

<template>
  <NodeViewWrapper
    class="section-node group relative my-4 rounded-lg border border-primary/10 bg-surface transition-colors duration-150"
    :class="{
      'ring-2 ring-primary/30': props.selected,
    }"
  >
    <!-- Header -->
    <div
      class="flex items-center gap-2 px-3 py-2 border-b border-primary/10 select-none"
    >
      <!-- Drag handle -->
      <span
        class="cursor-grab active:cursor-grabbing text-foreground/30 hover:text-primary/60 transition-colors duration-150"
        title="Trascina per riordinare"
      >
        <GripVertical class="w-4 h-4" />
      </span>

      <!-- Collapse toggle -->
      <button
        class="p-0.5 rounded text-foreground/40 hover:text-primary hover:bg-primary/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        @click="toggleCollapse"
      >
        <ChevronDown v-if="!collapsed" class="w-4 h-4" />
        <ChevronRight v-else class="w-4 h-4" />
      </button>

      <!-- Section number -->
      <span class="text-xs font-semibold text-primary/70 uppercase tracking-wide min-w-[2rem]">
        {{ props.node.attrs.number }}
      </span>

      <!-- Spacer -->
      <span class="flex-1" />

      <!-- Status badge -->
      <span
        class="text-[10px] font-medium uppercase tracking-widest px-1.5 py-0.5 rounded-full border border-current/20"
        :class="getStatusColor(props.node.attrs.status)"
      >
        {{ props.node.attrs.status }}
      </span>

      <!-- Provenance badge -->
      <span
        v-if="props.node.attrs.provenance && props.node.attrs.provenance.length > 0"
        class="text-[10px] font-medium text-primary-light px-1.5 py-0.5 rounded-full bg-primary-light/10"
      >
        {{ props.node.attrs.provenance.length }} docs
      </span>

      <!-- Delete button -->
      <button
        class="p-0.5 rounded text-foreground/30 hover:text-danger hover:bg-danger/8 transition-colors duration-150 opacity-0 group-hover:opacity-100 cursor-pointer focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        title="Elimina sezione"
        @click="props.deleteNode"
      >
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Content (collapsible) -->
    <div v-show="!collapsed" class="px-4 py-3">
      <NodeViewContent />
    </div>
  </NodeViewWrapper>
</template>
