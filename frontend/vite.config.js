import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // GitHub Pages serves the dashboard under /Good-Neighbor-Triage/app/ (set VITE_BASE when building for it)
  base: process.env.VITE_BASE || '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/openapi.json': 'http://127.0.0.1:8000', // used to detect which backend endpoints exist yet
    },
  },
})
