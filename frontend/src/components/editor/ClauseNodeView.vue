<script setup lang="ts">
import { nodeViewProps, NodeViewWrapper, NodeViewContent } from '@tiptap/vue-3'
import { CircleDot, GripVertical } from '@lucide/vue'

const props = defineProps(nodeViewProps)

const hasProvenance = props.node.attrs.provenance && props.node.attrs.provenance.length > 0
</script>

<template>
  <NodeViewWrapper
    class="clause-node group relative my-2 pl-2 border-l-2 border-primary/10 transition-colors duration-150"
    :class="{
      'border-primary/40 bg-primary/5': props.selected,
    }"
  >
    <div class="flex items-start gap-2">
      <!-- Drag handle -->
      <span
        class="mt-1 cursor-grab active:cursor-grabbing text-foreground/20 hover:text-primary/50 transition-colors duration-150 opacity-0 group-hover:opacity-100"
      >
        <GripVertical class="w-3.5 h-3.5" />
      </span>

      <!-- Clause number marker -->
      <span class="mt-0.5 text-primary/40 flex-shrink-0">
        <CircleDot class="w-3 h-3" />
      </span>

      <div class="flex-1 min-w-0">
        <!-- Clause number -->
        <span class="text-[11px] font-medium text-primary/50 uppercase tracking-wide">
          {{ props.node.attrs.number || 'Clause' }}
        </span>

        <!-- Provenance badge -->
        <span
          v-if="hasProvenance"
          class="ml-2 text-[10px] font-medium text-primary-light px-1.5 py-0.5 rounded-full bg-primary-light/10"
        >
          {{ props.node.attrs.provenance.length }} source{{ props.node.attrs.provenance.length > 1 ? 's' : '' }}
        </span>

        <!-- Content -->
        <div class="mt-1 prose prose-sm max-w-none">
          <NodeViewContent />
        </div>
      </div>
    </div>
  </NodeViewWrapper>
</template>
