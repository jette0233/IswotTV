import axios from 'axios'

// 自动推断API地址：如果是通过域名/IP访问，就用当前域名；开发环境用localhost
const BASE = window.location.origin + '/api'

const api = axios.create({
  baseURL: BASE,
  timeout: 10000,
})

// 请求拦截器 - 自动带token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export default api

// ─── 认证 ───
export const auth = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  uploadCookie: (data) => api.post('/auth/cookie/upload', data),
  cookieStatus: (uid) => api.get('/auth/cookie/status', { params: { uid } }),
  refreshCookie: (data) => api.post('/auth/cookie/refresh-auto', data),
}

// ─── 课程 ───
export const course = {
  create: (data) => api.post('/course/create', data),
  join: (data) => api.post('/course/join', data),
  list: (uid, weekday) => api.get('/course/list', { params: { uid, weekday } }),
  detail: (courseId) => api.get('/course/detail', { params: { course_id: courseId } }),
  update: (data) => api.post('/course/update', data),
  delete: (data) => api.post('/course/delete', data),
  leave: (data) => api.post('/course/leave', data),
}

// ─── 生产者 ───
export const producer = {
  claim: (data) => api.post('/producer/claim', data),
  heartbeat: (data) => api.post('/producer/heartbeat', data),
  pushEnc: (data) => api.post('/producer/push-enc', data),
  status: (courseId) => api.get('/producer/status', { params: { course_id: courseId } }),
}

// ─── 消费者 ───
export const consumer = {
  checkSign: (courseId, uid) => api.get('/consumer/check-sign', { params: { course_id: courseId, uid } }),
  doSign: (data) => api.post('/consumer/do-sign', data),
  signLog: (uid, courseId) => api.get('/consumer/sign-log', { params: { uid, course_id: courseId } }),
  pendingCourses: (uid) => api.get('/consumer/pending-courses', { params: { uid } }),
}
