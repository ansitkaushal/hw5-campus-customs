import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev server on http://localhost:5173 (the origin the backend allows via CORS).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
