import { createRouter, createWebHistory } from 'vue-router'

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
  },
  {
    path: '/documents/:id',
    name: 'document',
    component: () => import('@/views/DocumentView.vue'),
  },
  {
    path: '/documents/:id/compare/:v1/:v2',
    name: 'document-compare',
    component: () => import('@/views/DocumentView.vue'),
  },
  {
    path: '/documents/:id/review',
    name: 'document-review',
    component: () => import('@/views/DocumentView.vue'),
  },
  {
    path: '/documents/:id/diff/:v1/:v2',
    name: 'document-diff',
    component: () => import('@/views/DocumentView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
