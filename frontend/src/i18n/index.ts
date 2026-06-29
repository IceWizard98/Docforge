import { createI18n } from 'vue-i18n'
import it from './locales/it.json'
import en from './locales/en.json'

export const SUPPORTED_LOCALES = ['it', 'en'] as const
export type AppLocale = (typeof SUPPORTED_LOCALES)[number]

const STORAGE_KEY = 'docforge-locale'

function resolveInitialLocale(): AppLocale {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
    return stored as AppLocale
  }
  const nav = (navigator.language || 'it').slice(0, 2).toLowerCase()
  return (SUPPORTED_LOCALES as readonly string[]).includes(nav) ? (nav as AppLocale) : 'it'
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: resolveInitialLocale(),
  fallbackLocale: 'it',
  messages: { it, en },
  // Our catalogs are static strings (no interpolation/plurals). Resolve them
  // directly instead of letting vue-i18n compile messages at runtime — the
  // runtime compiler uses `new Function`, which the app's CSP (`script-src
  // 'self'`, no 'unsafe-eval') blocks, blanking any view that calls t().
  messageCompiler: (message) => () => (typeof message === 'string' ? message : String(message)),
})

export function setLocale(locale: AppLocale) {
  i18n.global.locale.value = locale
  localStorage.setItem(STORAGE_KEY, locale)
  document.documentElement.setAttribute('lang', locale)
}
