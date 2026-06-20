<script setup lang="ts">
import type { Component } from 'vue'

export interface PanelTab {
  id: string
  icon: Component
  label: string
}

defineProps<{
  tabs: PanelTab[]
  activeTab: string
}>()

const emit = defineEmits<{
  'update:activeTab': [tabId: string]
}>()
</script>

<template>
  <div class="flex flex-col min-h-0 flex-1">
    <div class="flex border-b border-primary/10 shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="flex-1 flex items-center justify-center gap-1.5 px-2 py-2.5 text-xs font-medium transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none border-b-2 -mb-px"
        :class="activeTab === tab.id
          ? 'text-primary border-primary bg-primary/5'
          : 'text-foreground/50 border-transparent hover:text-foreground/70 hover:bg-primary/3'"
        :title="tab.label"
        :aria-label="tab.label"
        :aria-selected="activeTab === tab.id"
        role="tab"
        @click="emit('update:activeTab', tab.id === activeTab ? '' : tab.id)"
      >
        <component :is="tab.icon" class="w-3.5 h-3.5" />
        <span class="hidden lg:inline">{{ tab.label }}</span>
      </button>
    </div>
    <div class="flex-1 overflow-hidden">
      <slot />
    </div>
  </div>
</template>
