<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { FileText, Menu, X } from '@lucide/vue'
import UserMenu from './UserMenu.vue'

const route = useRoute()
const mobileNavOpen = ref(false)

const links = [
  { to: '/workspace/default', label: 'Documenti', match: (p: string) => p.startsWith('/workspace') },
  { to: '/sources', label: 'Fonti', match: (p: string) => p.startsWith('/sources') },
  { to: '/templates', label: 'Template', match: (p: string) => p === '/templates' },
]
</script>

<template>
  <div class="h-screen w-screen bg-surface text-foreground overflow-hidden flex flex-col">
    <a
      href="#main-content"
      class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary focus:text-white focus:rounded-md focus:text-sm focus:font-medium"
    >
      Salta al contenuto principale
    </a>
    <header class="shrink-0 h-14 border-b border-primary/10 bg-surface/95 backdrop-blur-sm flex items-center px-3 sm:px-4">
      <div class="flex items-center gap-2 sm:gap-6 w-full mx-auto">
        <!-- Hamburger (mobile only) -->
        <button
          class="md:hidden p-2 -ml-1 rounded-md text-foreground/70 hover:text-primary hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          :aria-label="mobileNavOpen ? 'Chiudi menu' : 'Apri menu'"
          :aria-expanded="mobileNavOpen"
          @click="mobileNavOpen = !mobileNavOpen"
        >
          <X v-if="mobileNavOpen" class="h-5 w-5" />
          <Menu v-else class="h-5 w-5" />
        </button>

        <router-link to="/workspace/default" class="flex items-center gap-2 text-foreground hover:text-primary transition-colors shrink-0">
          <FileText class="h-5 w-5 text-primary" />
          <span class="font-semibold tracking-tight" style="font-family: var(--font-heading)">DocForge</span>
        </router-link>

        <!-- Desktop nav -->
        <nav class="hidden md:flex items-center gap-1">
          <router-link
            v-for="l in links"
            :key="l.to"
            :to="l.to"
            class="px-3 py-1.5 text-sm rounded-md transition-colors"
            :class="l.match(route.path) ? 'bg-primary/10 text-primary font-medium' : 'text-foreground/60 hover:text-primary hover:bg-primary/8'"
          >
            {{ l.label }}
          </router-link>
        </nav>

        <div class="ml-auto">
          <UserMenu />
        </div>
      </div>
    </header>

    <!-- Mobile nav drawer -->
    <Transition name="fade">
      <div
        v-if="mobileNavOpen"
        class="md:hidden fixed inset-0 top-14 z-40 bg-black/30"
        @click="mobileNavOpen = false"
      >
        <nav class="bg-surface border-b border-primary/10 shadow-lg py-2" @click.stop>
          <router-link
            v-for="l in links"
            :key="l.to"
            :to="l.to"
            class="block px-5 py-3 text-sm transition-colors"
            :class="l.match(route.path) ? 'bg-primary/10 text-primary font-medium' : 'text-foreground/70 hover:text-primary hover:bg-primary/8'"
            @click="mobileNavOpen = false"
          >
            {{ l.label }}
          </router-link>
        </nav>
      </div>
    </Transition>

    <!-- flex flex-col min-h-0 establishes a bounded-height flex context so views
         using flex-1/min-h-0 (e.g. the chat) actually scroll instead of growing. -->
    <main id="main-content" class="flex-1 min-h-0 overflow-hidden flex flex-col">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
