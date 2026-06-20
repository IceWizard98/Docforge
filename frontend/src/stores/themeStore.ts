import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { usePreferredDark, useStorage } from '@vueuse/core'

export type Theme = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const theme = useStorage<Theme>('docforge-theme', 'system')
  const systemDark = usePreferredDark()

  const isDark = computed(() => {
    if (theme.value === 'system') return systemDark.value
    return theme.value === 'dark'
  })

  const resolvedTheme = computed(() => {
    return isDark.value ? 'dark' : 'light'
  })

  watch(isDark, (dark) => {
    if (typeof document !== 'undefined') {
      document.documentElement.classList.toggle('dark', dark)
    }
  }, { immediate: true })

  function setTheme(mode: Theme) {
    theme.value = mode
  }

  function toggle() {
    const next: Record<Theme, Theme> = {
      light: 'dark',
      dark: 'system',
      system: 'light',
    }
    theme.value = next[theme.value] || 'light'
  }

  return {
    theme,
    isDark,
    resolvedTheme,
    setTheme,
    toggle,
  }
})
