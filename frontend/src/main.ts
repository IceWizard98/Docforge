import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router, { recoverFromChunkError } from './router'
import App from './App.vue'
// Self-hosted fonts (bundled by Vite -> served from /assets) so no external
// request to fonts.googleapis.com, which the strict CSP blocks.
import '@fontsource-variable/lexend'
import '@fontsource-variable/source-sans-3'
import './assets/main.css'
import { useAuthStore } from './api/authStore'
import { i18n } from './i18n'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(i18n)

const authStore = useAuthStore()
authStore.checkToken()

app.config.errorHandler = (err, _instance, info) => {
  console.error('Global error:', err, info)
  recoverFromChunkError(err)
}

// Vite fires this when a dynamically imported chunk fails to load (stale build
// after a redeploy). Prevent the default uncaught rejection and reload once to
// fetch the fresh build.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault()
  recoverFromChunkError(
    (event as Event & { payload?: unknown }).payload ??
      new Error('Failed to fetch dynamically imported module'),
  )
})

app.use(router)
app.mount('#app')
