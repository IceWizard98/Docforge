<script setup lang="ts">
import DocumentListPanel from '@/components/workspace/DocumentListPanel.vue'
import { FileText } from '@lucide/vue'
</script>

<template>
  <div class="flex h-screen bg-white">
    <div class="hidden md:block w-64 shrink-0">
      <DocumentListPanel />
    </div>

    <!-- Welcome / empty state -->
    <main class="flex-1 flex items-center justify-center">
      <div class="text-center max-w-sm px-8">
        <div class="flex justify-center mb-4">
          <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
            <FileText class="w-8 h-8 text-primary" />
          </div>
        </div>
        <h1 class="text-2xl font-bold text-foreground mb-2">DocForge</h1>
        <p class="text-sm text-foreground/50 leading-relaxed">
          Seleziona un documento dalla lista o creane uno nuovo per iniziare a lavorare.
        </p>
      </div>
    </main>
  </div>
</template>
