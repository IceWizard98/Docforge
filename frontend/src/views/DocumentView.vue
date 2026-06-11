<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useDocumentStore } from '@/stores/documentStore'
import DocumentEditor from '@/components/editor/DocumentEditor.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const route = useRoute()
const documentStore = useDocumentStore()

const hasId = !!route.params.id
</script>

<template>
  <DocumentEditor v-if="hasId && documentStore.currentDocId" />
  <LoadingSpinner v-else-if="hasId && documentStore.loading" size="lg" />
  <div v-else class="flex items-center justify-center h-screen text-foreground/40 text-sm">
    Document ID is missing
  </div>
</template>
