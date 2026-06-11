<script setup lang="ts">
import { FileText } from '@lucide/vue'
import UserMenu from './UserMenu.vue'
</script>

<template>
  <div class="h-screen w-screen bg-surface text-foreground overflow-hidden flex flex-col">
    <header class="shrink-0 h-14 border-b border-primary/10 bg-surface/95 backdrop-blur-sm flex items-center px-4">
      <div class="flex items-center gap-6 max-w-7xl w-full mx-auto">
        <router-link to="/workspace/default" class="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
          <FileText class="h-5 w-5 text-primary" />
          <span class="font-semibold">DocForge</span>
        </router-link>
        <nav class="flex items-center gap-4 ml-4">
          <router-link to="/templates" class="text-sm text-foreground/60 hover:text-primary transition-colors">
            Template
          </router-link>
        </nav>
        <div class="ml-auto">
          <UserMenu />
        </div>
      </div>
    </header>
    <main class="flex-1 overflow-hidden">
      <slot />
    </main>
  </div>
</template>
