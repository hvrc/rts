import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  define: {
    'process.env.API_URL': mode === 'production' 
      ? JSON.stringify('https://backend-dot-rts0-462101.ue.r.appspot.com')
      : JSON.stringify('http://localhost:5000')
  },
  server: {
    port: 5001,
    proxy: {
      '/api': {
        target: mode === 'production'
          ? 'https://backend-dot-rts0-462101.ue.r.appspot.com'
          : 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
}))
