<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/api/authStore'
import { Save, Lock } from '@lucide/vue'

const authStore = useAuthStore()
const displayName = ref(authStore.currentUser?.displayName || '')
const email = ref(authStore.currentUser?.email || '')
const saved = ref(false)

function handleSave() {
  saved.value = true
  setTimeout(() => { saved.value = false }, 2000)
}
</script>

<template>
  <div class="h-full overflow-y-auto p-6">
    <div class="max-w-lg mx-auto pt-8">
      <h1 class="text-xl font-bold text-foreground mb-6">Impostazioni</h1>

      <div class="space-y-6">
        <div>
          <label class="block text-xs font-medium text-foreground/60 mb-1">Email</label>
          <input
            :value="email"
            type="email"
            readonly
            class="w-full px-3 py-2 text-sm bg-primary/5 border border-primary/10 rounded-md text-foreground/50 cursor-not-allowed focus-visible:outline-none"
          />
          <p class="text-xs text-foreground/40 mt-1">L'email non può essere modificata</p>
        </div>

        <div>
          <label class="block text-xs font-medium text-foreground/60 mb-1" for="displayName">
            Nome visualizzato
          </label>
          <input
            id="displayName"
            v-model="displayName"
            type="text"
            class="w-full px-3 py-2 text-sm bg-surface border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
          />
        </div>

        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            @click="handleSave"
          >
            <Save class="h-4 w-4" />
            Salva
          </button>
          <span
            v-if="saved"
            class="text-xs text-cta transition-opacity duration-200"
          >
            Modifiche salvate
          </span>
        </div>

        <hr class="border-primary/10" />

        <div>
          <h2 class="text-sm font-medium text-foreground mb-3">Password</h2>
          <button
            disabled
            class="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md border border-primary/10 text-foreground/40 cursor-not-allowed"
          >
            <Lock class="h-4 w-4" />
            Cambia password
          </button>
          <p class="text-xs text-foreground/40 mt-1">Disponibile in un aggiornamento futuro</p>
        </div>
      </div>
    </div>
  </div>
</template>
