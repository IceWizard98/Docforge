<script setup lang="ts">
import { computed } from 'vue'
import { useDocumentStore } from '@/stores/documentStore'
import { useEditorStore } from '@/stores/editorStore'
import { FileText, ChevronRight } from '@lucide/vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorMessage from '@/components/common/ErrorMessage.vue'

const documentStore = useDocumentStore()
const editorStore = useEditorStore()

const statusBadgeClass = (status: string) => {
  switch (status) {
    case 'approved':
      return 'bg-cta/10 text-cta border-cta/20'
    case 'draft':
      return 'bg-primary/10 text-primary border-primary/20'
    default:
      return 'bg-foreground/5 text-foreground/50 border-foreground/10'
  }
}

function goToSection(sectionId: string) {
  editorStore.setActiveSection(sectionId)
}
</script>

<template>
  <aside class="flex flex-col h-full bg-surface">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-primary/10">
      <FileText class="w-4 h-4 text-primary" />
      <h2 class="text-sm font-semibold text-foreground">Outline</h2>
      <span class="ml-auto text-[11px] text-foreground/40 font-medium">
        {{ documentStore.sectionCount }} section{{ documentStore.sectionCount !== 1 ? 's' : '' }}
      </span>
    </div>

    <!-- Sections list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Loading state -->
      <LoadingSpinner v-if="documentStore.loading" class="h-24" />

      <!-- Error state -->
      <ErrorMessage
        v-if="documentStore.error"
        :message="documentStore.error"
      />

      <!-- Empty state -->
      <div
        v-if="!documentStore.loading && !documentStore.error && documentStore.sections.length === 0"
        class="flex flex-col items-center justify-center h-24 px-4"
      >
        <p class="text-sm text-foreground/40">No sections found.</p>
      </div>

      <!-- Section list -->
      <nav class="py-1" v-if="documentStore.sections.length > 0">
        <button
          v-for="section in documentStore.sections"
          :key="section.id"
          class="w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :class="{
            'bg-primary/8 text-primary font-medium': editorStore.activeSectionId === section.id,
            'text-foreground/70 hover:bg-primary/5 hover:text-foreground': editorStore.activeSectionId !== section.id,
          }"
          @click="goToSection(section.id)"
        >
          <ChevronRight
            class="w-3 h-3 flex-shrink-0"
            :class="editorStore.activeSectionId === section.id ? 'text-primary' : 'text-foreground/30'"
          />
          <span class="text-[11px] font-semibold text-primary/50 uppercase min-w-[1.5rem]">
            {{ section.number }}
          </span>
          <span class="flex-1 truncate">{{ section.title }}</span>
          <span
            class="text-[10px] font-medium uppercase px-1 py-0.5 rounded-full border"
            :class="statusBadgeClass(section.status)"
          >
            {{ section.status }}
          </span>
        </button>
      </nav>
    </div>
  </aside>
</template>
