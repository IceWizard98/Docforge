import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/api/authStore'

const routes = [
  {
    path: '/',
    redirect: '/workspace/default',
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { layout: false },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { layout: false },
  },
  {
    path: '/workspace/:id',
    name: 'workspace',
    component: () => import('@/views/WorkspaceView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents/:id',
    name: 'document',
    component: () => import('@/views/DocumentView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents/:id/compare/:v1/:v2',
    name: 'document-compare',
    component: () => import('@/views/DocumentView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents/:id/review',
    name: 'document-review',
    component: () => import('@/views/DocumentView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/documents/:id/diff/:v1/:v2',
    name: 'document-diff',
    component: () => import('@/views/DocumentView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/templates',
    name: 'templates',
    component: () => import('@/views/TemplatesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/sources',
    name: 'sources',
    component: () => import('@/views/SourceLibraryView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// After a redeploy the served index.html references new hashed chunks; a tab
// still running the old build requests a chunk that now 404s, so a dynamic
// import rejects ("Failed to fetch dynamically imported module"). Recover by
// reloading to pull the fresh index.html (served no-store) and its new chunk
// hashes. A time-based guard prevents an infinite reload loop: if a chunk error
// recurs within the cooldown (the chunk is genuinely gone, not just stale), we
// don't reload again. The window of time, not navigation success, is the guard,
// so this stays loop-safe even for non-router dynamic imports.
const CHUNK_ERROR_RE =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module/i
const CHUNK_RELOAD_COOLDOWN_MS = 10000

export function recoverFromChunkError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err)
  if (!CHUNK_ERROR_RE.test(msg)) return false
  const last = Number(sessionStorage.getItem('chunk-reload-at') || 0)
  if (Date.now() - last < CHUNK_RELOAD_COOLDOWN_MS) return false
  sessionStorage.setItem('chunk-reload-at', String(Date.now()))
  window.location.reload()
  return true
}

router.onError((err) => {
  recoverFromChunkError(err)
})

router.beforeEach((to, _from, next) => {
  const publicPages = ['login', 'register']
  if (!publicPages.includes(to.name as string)) {
    const authStore = useAuthStore()
    if (!authStore.initialized) {
      authStore.checkToken()
    }
    if (!authStore.isAuthenticated) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
  }
  next()
})

export default router
