<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/api/authStore'
import { useThemeStore, type Theme } from '@/stores/themeStore'
import { updateProfile } from '@/api/client'
import { useToast } from '@/composables/useToast'
import { Save, Lock, Sun, Moon, Monitor } from '@lucide/vue'

const authStore = useAuthStore()
const themeStore = useThemeStore()
const toast = useToast()
const displayName = ref(authStore.currentUser?.displayName || '')
const email = ref(authStore.currentUser?.email || '')
const saved = ref(false)
const saving = ref(false)

const themes: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Chiaro', icon: Sun },
  { value: 'dark', label: 'Scuro', icon: Moon },
  { value: 'system', label: 'Sistema', icon: Monitor },
]

async function handleSave() {
  if (saving.value) return
  saving.value = true
  try {
    const updated = await updateProfile(displayName.value.trim())
    authStore.setDisplayName(updated.displayName)
    displayName.value = updated.displayName
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } catch {
    toast.error('Salvataggio impostazioni fallito')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto p-6">
    <div class="max-w-lg mx-auto pt-8">
      <h1 class="text-xl font-bold text-foreground mb-6">Impostazioni</h1>

      <div class="space-y-6">
        <!-- Profilo -->
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
            :disabled="saving"
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

        <!-- Aspetto -->
        <div>
          <h2 class="text-sm font-medium text-foreground mb-3">Aspetto</h2>
          <div class="flex gap-3">
            <button
              v-for="mode in themes"
              :key="mode.value"
              @click="themeStore.setTheme(mode.value)"
              class="flex-1 px-4 py-3 rounded-lg border text-sm text-center transition-all cursor-pointer"
              :class="themeStore.theme === mode.value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-primary/10 text-foreground/70 hover:border-primary/30 hover:bg-primary/5'"
            >
              <component :is="mode.icon" class="w-5 h-5 mx-auto mb-1" />
              {{ mode.label }}
            </button>
          </div>
        </div>

        <hr class="border-primary/10" />

        <!-- Selezione lingua nascosta: i18n incompleto — la UI è tutta in
             italiano hardcoded. Riattivare quando le stringhe sono estratte. -->

        <!-- Password -->
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
