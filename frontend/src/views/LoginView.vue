<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/api/authStore'
import { Loader2 } from '@lucide/vue'
import axios from 'axios'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const emailValid = computed(() => emailPattern.test(email.value.trim()))

async function handleSubmit() {
  if (!email.value.trim() || !password.value.trim() || !emailValid.value) return

  loading.value = true
  error.value = null

  try {
    await authStore.login(email.value, password.value)
    const redirect = (route.query.redirect as string) || '/workspace/default'
    router.push(redirect)
  } catch (e: unknown) {
    if (axios.isAxiosError(e)) {
      error.value = e.response?.data?.detail || e.message || 'Credenziali non valide'
    } else if (e instanceof Error) {
      error.value = e.message
    } else {
      error.value = 'Credenziali non valide'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="h-screen w-screen flex items-center justify-center bg-surface">
    <div class="w-full max-w-sm mx-auto px-6">
      <div class="bg-white rounded-lg border border-primary/10 p-8">
        <h1 class="text-xl font-bold text-foreground mb-1">Accedi</h1>
        <p class="text-sm text-foreground/50 mb-6">Inserisci le tue credenziali per continuare</p>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="email">
              Email
            </label>
            <input
              id="email"
              v-model="email"
              type="email"
              class="w-full px-3 py-3 md:py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="nome@esempio.com"
              autocomplete="email"
            />
          </div>

          <div>
            <label class="block text-xs font-medium text-foreground/60 mb-1" for="password">
              Password
            </label>
            <input
              id="password"
              v-model="password"
              type="password"
              class="w-full px-3 py-3 md:py-2 text-sm bg-white border border-primary/10 rounded-md text-foreground placeholder-foreground/40 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-colors duration-150"
              placeholder="••••••••"
              autocomplete="current-password"
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
            class="w-full flex items-center justify-center gap-2 px-3 py-3 md:py-2 text-sm font-medium rounded-md bg-primary text-white hover:bg-primary-light transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
            :disabled="loading || !email.trim() || !password.trim() || !emailValid"
          >
            <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
            {{ loading ? 'Accesso in corso...' : 'Accedi' }}
          </button>
        </form>

        <p class="mt-4 text-xs text-foreground/40 text-center">
          Non hai un account?
          <router-link to="/register" class="text-primary hover:text-primary-light font-medium">
            Registrati
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>
