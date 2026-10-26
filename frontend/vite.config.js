import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In production (`vite preview` on Railway) /api is proxied to the backend service via API_URL.
const api = globalThis.process?.env.API_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  preview: { host: '0.0.0.0', allowedHosts: true, proxy: { '/api': { target: api, changeOrigin: true } } },
})
