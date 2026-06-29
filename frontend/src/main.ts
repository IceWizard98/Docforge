import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
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
}

app.use(router)
app.mount('#app')
