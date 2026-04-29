import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // In local dev (npm run dev), proxy /api/ to the FastAPI backend.
    // In Docker, nginx handles this same proxy instead.
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
