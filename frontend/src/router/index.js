import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Courses from '../views/Courses.vue'
import Producer from '../views/Producer.vue'
import Consumer from '../views/Consumer.vue'
import Admin from '../views/Admin.vue'

const routes = [
  { path: '/', redirect: '/courses' },
  { path: '/login', name: 'Login', component: Login },
  { path: '/courses', name: 'Courses', component: Courses, meta: { requiresAuth: true } },
  { path: '/producer/:courseId', name: 'Producer', component: Producer, meta: { requiresAuth: true }, props: true },
  { path: '/consumer', name: 'Consumer', component: Consumer, meta: { requiresAuth: true } },
  { path: '/txjadmin', name: 'Admin', component: Admin },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
