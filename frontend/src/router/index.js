import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/kanban' },
  { path: '/login', component: () => import('../views/Login.vue') },
  { path: '/kanban', component: () => import('../views/KanbanBoard.vue') },
  { path: '/import', component: () => import('../views/MeetingImport.vue') },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/actions/:id', component: () => import('../views/ActionDetail.vue') },
  { path: '/meeting-edit/:id', component: () => import('../views/MeetingEdit.vue') },
  { path: '/meetings/:id/review', component: () => import('../views/MeetingReview.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
