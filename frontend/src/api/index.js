import axios from 'axios'

// 自动推断API地址：如果是通过域名/IP访问，就用当前域名；开发环境用localhost
const BASE = window.location.origin + '/api/v2'

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

api.interceptors.response.use(response => {
  // Keep legacy views working while they are migrated to the v2 envelope.
  if (response.data && Object.prototype.hasOwnProperty.call(response.data, 'data') && !Object.prototype.hasOwnProperty.call(response.data, 'code')) {
    response.data.code = 200
    response.data.msg = ''
  }
  return response
}, async error => {
  const original = error.config
  const refreshToken = localStorage.getItem('refresh_token')
  if (error.response?.status === 401 && refreshToken && !original?._retried && !original?.url?.includes('/auth/refresh')) {
    original._retried = true
    try {
      const response = await axios.post(BASE + '/auth/refresh', { refresh_token: refreshToken })
      const tokens = response.data.data
      localStorage.setItem('token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
      original.headers.Authorization = `Bearer ${tokens.access_token}`
      return api(original)
    } catch (_) {
      localStorage.clear()
      window.location.href = '/login'
    }
  }
  const message = error.response?.data?.error?.message
  if (message && error.response.data.msg === undefined) error.response.data.msg = message
  return Promise.reject(error)
})

export default api

// ─── 认证 ───
export const auth = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  uploadCookie: (data) => api.post('/auth/cookie', { cookie: data.cookie }),
  cookieStatus: () => api.get('/auth/cookie'),
  refreshCookie: (data) => api.post('/auth/cookie/refresh-auto', { phone: data.phone, password: data.password }),
  me: () => api.get('/auth/me'),
}

// ─── 课程 ───
export const course = {
  create: (data) => api.post('/courses', data),
  join: (data) => api.post('/courses/join', { course_id: data.course_id }),
  list: (_uid, weekday) => api.get('/courses', { params: { weekday } }),
  update: (data) => api.patch(`/courses/${data.course_id}`, data),
  delete: (data) => api.delete(`/courses/${data.course_id}`),
  leave: (data) => api.delete(`/courses/${data.course_id}/membership`),
}

// ─── 生产者 ───
export const producer = {
  claim: (data) => api.post('/producer/claim', { course_id: Number(data.course_id) }),
  heartbeat: (data) => api.post('/producer/heartbeat', { course_id: Number(data.course_id) }),
  pushEnc: (data) => api.post('/producer/events', {
    course_id: Number(data.course_id), source_course_id: data.source_course_id,
    external_active_id: data.active_id, enc: data.enc,
    latitude: data.latitude || null, longitude: data.longitude || null,
    observed_at: new Date().toISOString(),
  }),
}

// ─── 消费者 ───
export const consumer = {
  tasks: () => api.get('/tasks/me'),
}
