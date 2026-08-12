import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  scenarios: {
    reads: { executor: 'constant-vus', vus: 200, duration: '60s' },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.01'],
  },
}

export default function () {
  const token = __ENV.ACCESS_TOKEN
  const response = http.get(`${__ENV.BASE_URL}/api/v2/courses`, { headers: { Authorization: `Bearer ${token}` } })
  check(response, { 'status is 200': (r) => r.status === 200 })
  sleep(1)
}
