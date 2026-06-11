<script setup lang="ts">
import { AlertCircle } from '@lucide/vue'

defineProps<{
  message: string
  retryLabel?: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center h-24 min-h-[6rem] px-4 py-6">
    <AlertCircle class="w-5 h-5 text-danger mb-2" />
    <p class="text-sm text-danger/80 text-center max-w-xs">{{ message }}</p>
    <button
      v-if="retryLabel"
      class="mt-3 px-3 py-1.5 text-sm font-medium rounded-md border border-danger/30 text-danger hover:bg-danger/8 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="$emit('retry')"
    >
      {{ retryLabel }}
    </button>
  </div>
</template>
