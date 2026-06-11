<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/api/authStore'
import { User, ChevronDown, Settings, LogOut } from '@lucide/vue'

const authStore = useAuthStore()
const router = useRouter()
const open = ref(false)
const menuRef = ref<HTMLElement | null>(null)

function toggle() {
  open.value = !open.value
}

function onDocumentClick(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

function handleLogout() {
  open.value = false
  authStore.logout()
}

function handleSettings() {
  open.value = false
  router.push('/settings')
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})
</script>

<template>
  <div ref="menuRef" class="relative">
    <button
      class="flex items-center gap-2 px-3 py-1.5 text-sm text-foreground/70 hover:text-primary hover:bg-primary/8 rounded-md transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
      @click="toggle"
    >
      <User class="h-4 w-4" />
      <span class="hidden sm:inline max-w-[120px] truncate">
        {{ authStore.currentUser?.displayName || authStore.currentUser?.email }}
      </span>
      <ChevronDown class="h-3.5 w-3.5 transition-transform duration-200" :class="open ? 'rotate-180' : ''" />
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open"
        class="absolute right-0 mt-2 w-56 rounded-lg border border-primary/10 bg-white shadow-lg py-1 z-50 origin-top-right"
      >
        <div class="px-3 py-2 border-b border-primary/10">
          <p class="text-sm font-medium text-foreground truncate">
            {{ authStore.currentUser?.displayName }}
          </p>
          <p class="text-xs text-foreground/50 truncate mt-0.5">
            {{ authStore.currentUser?.email }}
          </p>
        </div>

        <button
          class="w-full flex items-center gap-2 px-3 py-2 text-sm text-foreground/70 hover:text-primary hover:bg-primary/8 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          @click="handleSettings"
        >
          <Settings class="h-4 w-4" />
          Impostazioni
        </button>

        <div class="border-t border-primary/10 mt-1 pt-1">
          <button
            class="w-full flex items-center gap-2 px-3 py-2 text-sm text-danger hover:bg-danger/5 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            @click="handleLogout"
          >
            <LogOut class="h-4 w-4" />
            Esci
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
