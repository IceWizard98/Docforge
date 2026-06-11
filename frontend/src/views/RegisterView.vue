<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/api/authStore'
import { Loader2 } from '@lucide/vue'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const displayName = ref('')
const tenantSlug = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function handleSubmit() {
  if (!email.value.trim() || !password.value.trim() || !displayName.value.trim()) return

  loading.value = true
  error.value = null

  try {
    await authStore.register(
      email.value,
      password.value,
      displayName.value,
      tenantSlug.value || 'default',
    )
    router.push('/workspace/default')
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e.message || 'Registrazione fallita'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-screen w-screen flex items-center justify-center bg-surface">
    <div class="w-full max-w-sm mx-auto px-6">
      <div class="bg-white rounded-lg border border-primary/10 p-8">
        <h1 class="text-xl font-bold text-foreground mb-1">Registrati</h1>
        <p class="text-sm text-foreground/50 mb-6">Crea il tuo account per iniziare</p>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="displayName">
              Nome
            </label>
            <input
              id="displayName"
              v-model="displayName"
              type="text"
              class="w-full px-3 py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="Mario Rossi"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="reg-email">
              Email
            </label>
            <input
              id="reg-email"
              v-model="email"
              type="email"
              class="w-full px-3 py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="nome@esempio.com"
              autocomplete="email"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="reg-password">
              Password
            </label>
            <input
              id="reg-password"
              v-model="password"
              type="password"
              class="w-full px-3 py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="••••••••"
              autocomplete="new-password"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="tenantSlug">
              Tenant (opzionale)
            </label>
            <input
              id="tenantSlug"
              v-model="tenantSlug"
              type="text"
              class="w-full px-3 py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="default"
            />
          </div>

          <div
            v-if="error"
            class="text-sm text-danger bg-danger/5 border border-danger/20 rounded-md px-3 py-2"
          >
            {{ error }}
          </div>

          <button
            type="submit"
            class="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            :disabled="loading || !email.trim() || !password.trim() || !displayName.trim()"
          >
            <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
            {{ loading ? 'Registrazione in corso...' : 'Registrati' }}
          </button>
        </form>

        <p class="mt-4 text-xs text-foreground/40 text-center">
          Hai già un account?
          <router-link to="/login" class="text-primary hover:text-primary-light font-medium">
            Accedi
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>
