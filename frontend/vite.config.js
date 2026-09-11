import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Dev-only proxy so the frontend can call relative /api/... paths --
  // avoids CORS entirely and means a single tunnel (ngrok, etc.) exposing
  // just the frontend port is enough for a public demo. Override the
  // backend location with VITE_BACKEND_URL in .env if it's not on :8000.
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': backendUrl,
      },
      allowedHosts: true,
    },
  }
})
