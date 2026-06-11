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
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
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
    path: '/:pathMatch(.*)*',
    redirect: '/workspace/default',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const publicPages = ['login', 'register']
  if (!publicPages.includes(to.name as string)) {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
  }
  next()
})

export default router
