import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const https = env.VITE_HTTPS_KEY && env.VITE_HTTPS_CERT
    ? {
        key: fs.readFileSync(env.VITE_HTTPS_KEY),
        cert: fs.readFileSync(env.VITE_HTTPS_CERT),
      }
    : false

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      host: '0.0.0.0',
      https,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY || 'http://localhost:5000',
          changeOrigin: true,
        },
      },
    },
  }
})
