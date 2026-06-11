<script setup lang="ts">
import { useRoute } from 'vue-router'
import DocumentEditor from '@/components/editor/DocumentEditor.vue'

const route = useRoute()

const hasId = !!route.params.id
</script>

<template>
  <DocumentEditor v-if="hasId" />
  <div v-else class="flex items-center justify-center h-screen text-foreground/40 text-sm">
    Document ID is missing
  </div>
</template>
