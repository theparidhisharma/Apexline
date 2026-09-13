import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// L2 (frontend) talks to L1 (API) over LAN: set VITE_API in web/.env.local,
// e.g. VITE_API=http://192.168.1.42:8000
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: {
    '/api': { target: process.env.VITE_API || 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
    '/clips': { target: process.env.VITE_API || 'http://localhost:8000', changeOrigin: true },
    '/media': { target: process.env.VITE_API || 'http://localhost:8000', changeOrigin: true },
  } }
})
