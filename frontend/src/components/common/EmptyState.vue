<script setup lang="ts">
import { type Component } from 'vue'

defineProps<{
  icon?: Component
  title?: string
  description?: string
  actionLabel?: string
  actionDisabled?: boolean
}>()

defineEmits<{
  action: []
}>()
</script>

<template>
  <div class="flex flex-col items-center justify-center h-24 min-h-[6rem] px-4 py-6">
    <component :is="icon" v-if="icon" class="w-6 h-6 text-foreground/30 mb-2" />
    <p v-if="title" class="text-sm font-medium text-foreground/50">{{ title }}</p>
    <p v-if="description" class="text-xs text-foreground/40 mt-1 text-center max-w-xs">
      {{ description }}
    </p>
    <button
      v-if="actionLabel"
      class="mt-3 px-3 py-1.5 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
      :disabled="actionDisabled"
      @click="$emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
