import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    include: ['mapbox-gl'],
    esbuildOptions: {
      target: 'es2020',
    },
  },
  define: {
    // Fix for Mapbox worker
    global: 'globalThis',
  },
  build: {
    commonjsOptions: {
      include: [/mapbox-gl/, /node_modules/],
      transformMixedEsModules: true,
    },
  },
})

