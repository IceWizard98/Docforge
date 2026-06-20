<script setup lang="ts">
import { FileText } from '@lucide/vue'
import UserMenu from './UserMenu.vue'
</script>

<template>
  <div class="h-screen w-screen bg-surface text-foreground overflow-hidden flex flex-col">
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary focus:text-white focus:rounded-md focus:text-sm focus:font-medium"
    >
      Salta al contenuto principale
    </a>
    <header class="shrink-0 h-14 border-b border-primary/10 bg-surface/95 backdrop-blur-sm flex items-center px-4">
      <div class="flex items-center gap-6 w-full mx-auto">
        <router-link to="/workspace/default" class="flex items-center gap-2 text-foreground hover:text-primary transition-colors">
          <FileText class="h-5 w-5 text-primary" />
          <span class="font-semibold tracking-tight" style="font-family: var(--font-heading)">DocForge</span>
        </router-link>
        <nav class="flex items-center gap-1">
          <router-link
            to="/workspace/default"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="$route.path.startsWith('/workspace') ? 'bg-primary/10 text-primary font-medium' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
          >
            Documenti
          </router-link>
          <router-link
            to="/sources"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="$route.path.startsWith('/sources') ? 'bg-primary/10 text-primary font-medium' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
          >
            Fonti
          </router-link>
          <router-link
            to="/templates"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="$route.path === '/templates' ? 'bg-primary/10 text-primary font-medium' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
          >
            Template
          </router-link>
        </nav>
        <div class="ml-auto">
          <UserMenu />
        </div>
      </div>
    </header>
    <main id="main-content" class="flex-1 overflow-hidden">
      <slot />
    </main>
  </div>
</template>
