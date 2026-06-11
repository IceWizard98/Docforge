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
