/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  test: {
    // Unit tests sit beside their source; a hook's test opts into jsdom with a
    // `@vitest-environment jsdom` comment at its top
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'node',
  },
  server: {
    proxy: {
      // The API has no /api prefix of its own, so the prefix is stripped here.
      // Same origin in the browser means the session cookie needs no CORS.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ''),
      },
    },
  },
})
