import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '@/router'
import apiClient, { login as apiLogin, register as apiRegister } from './client'
import type { AuthResponse } from './client'

interface User {
  id: string
  email: string
  displayName: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))

  let parsedUser: User | null = null
  const userStr = localStorage.getItem('auth_user')
  if (userStr) {
    try {
      parsedUser = JSON.parse(userStr)
    } catch {
      localStorage.removeItem('auth_user')
      parsedUser = null
    }
  }
  const currentUser = ref<User | null>(parsedUser)

  const initialized = ref(false)
  const isAuthenticated = computed(() => !!token.value)

  function setAuth(data: AuthResponse) {
    token.value = data.token
    currentUser.value = data.user
    localStorage.setItem('auth_token', data.token)
    localStorage.setItem('auth_user', JSON.stringify(data.user))
    apiClient.defaults.headers.Authorization = `Bearer ${data.token}`
  }

  function clearAuth() {
    token.value = null
    currentUser.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
    localStorage.removeItem('refresh_token')
    delete apiClient.defaults.headers.Authorization
  }

  async function login(email: string, password: string) {
    const response = await apiLogin(email, password)
    setAuth(response)
    return response
  }

  async function register(
    email: string,
    password: string,
    displayName: string,
    tenantSlug: string,
  ) {
    const response = await apiRegister(email, password, displayName, tenantSlug)
    setAuth(response)
    return response
  }

  function logout() {
    clearAuth()
    router.push('/login')
  }

  function checkToken() {
    const stored = localStorage.getItem('auth_token')
    if (stored) {
      token.value = stored
      apiClient.defaults.headers.Authorization = `Bearer ${stored}`
      const userData = localStorage.getItem('auth_user')
      if (userData) {
        try {
          currentUser.value = JSON.parse(userData)
        } catch {
          localStorage.removeItem('auth_user')
          currentUser.value = null
        }
      }
    }
    initialized.value = true
  }

  return {
    token,
    currentUser,
    initialized,
    isAuthenticated,
    login,
    register,
    logout,
    checkToken,
  }
})
