import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// VITE_API_BASE_URL points at the FastAPI backend (e.g. http://localhost:8000).
// Empty string = same origin (works when served behind a reverse proxy).
// base must match the repo name for GitHub Pages (https://vizdumb2005.github.io/test/).
export default defineConfig({
  base: '/test/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/search': 'http://localhost:8000',
      '/query': 'http://localhost:8000',
      '/debug': 'http://localhost:8000',
      '/evaluate': 'http://localhost:8000',
      '/evaluation': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
