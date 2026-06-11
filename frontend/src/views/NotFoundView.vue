<script setup lang="ts">
import { FileQuestion } from '@lucide/vue'
</script>

<template>
  <div class="h-screen w-screen flex items-center justify-center bg-surface">
    <div class="text-center max-w-sm px-8">
      <div class="flex justify-center mb-4">
        <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
          <FileQuestion class="w-8 h-8 text-primary" />
        </div>
      </div>
      <h1 class="text-2xl font-bold text-foreground mb-2">Pagina non trovata</h1>
      <p class="text-sm text-foreground/50 leading-relaxed mb-6">
        La pagina che stai cercando non esiste o è stata spostata.
      </p>
      <router-link
        to="/workspace/default"
        class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150"
      >
        Torna al workspace
      </router-link>
    </div>
  </div>
</template>
