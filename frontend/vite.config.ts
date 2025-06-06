import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  define: {
    'process.env.API_URL': JSON.stringify('https://backend-dot-rts0-462101.ue.r.appspot.com')
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://backend-dot-rts0-462101.ue.r.appspot.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
