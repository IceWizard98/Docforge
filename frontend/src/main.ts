import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './assets/main.css'
import { useAuthStore } from './api/authStore'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

const authStore = useAuthStore()
authStore.checkToken()

app.config.errorHandler = (err, _instance, info) => {
  console.error('Global error:', err, info)
}

app.use(router)
app.mount('#app')
