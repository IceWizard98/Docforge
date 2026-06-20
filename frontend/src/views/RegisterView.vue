<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/api/authStore'
import { Loader2 } from '@lucide/vue'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const displayName = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const emailValid = computed(() => emailPattern.test(email.value.trim()))
const passwordMinLength = computed(() => password.value.length >= 8)
const passwordsMatch = computed(() => password.value === passwordConfirm.value)
const formValid = computed(() => emailValid.value && passwordMinLength.value && passwordsMatch.value && displayName.value.trim().length > 0)

async function handleSubmit() {
  if (!formValid.value) return

  loading.value = true
  error.value = null

  try {
    await authStore.register(
      email.value,
      password.value,
      displayName.value,
    )
    router.push('/workspace/default')
  } catch (e: unknown) {
    if (axios.isAxiosError(e)) {
      error.value = e.response?.data?.detail || e.message || 'Registrazione fallita'
    } else if (e instanceof Error) {
      error.value = e.message
    } else {
      error.value = 'Registrazione fallita'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-screen w-screen flex items-center justify-center bg-surface">
    <div class="w-full max-w-sm mx-auto px-6">
      <div class="bg-card rounded-lg border border-primary/10 p-8">
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
              class="w-full px-3 py-2 text-sm bg-card border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
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
              class="w-full px-3 py-2 text-sm bg-card border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
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
              class="w-full px-3 py-2 text-sm bg-card border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="Almeno 8 caratteri"
              autocomplete="new-password"
            />
            <p v-if="password && !passwordMinLength" class="mt-1 text-xs text-danger">
              Minimo 8 caratteri
            </p>
          </div>

          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="reg-password-confirm">
              Conferma Password
            </label>
            <input
              id="reg-password-confirm"
              v-model="passwordConfirm"
              type="password"
              class="w-full px-3 py-2 text-sm bg-card border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="Ripeti la password"
              autocomplete="new-password"
            />
            <p v-if="passwordConfirm && !passwordsMatch" class="mt-1 text-xs text-danger">
              Le password non coincidono
            </p>
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
            :disabled="loading || !formValid"
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
