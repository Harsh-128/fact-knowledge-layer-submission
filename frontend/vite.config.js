import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',
  },
  build: {
    // Generate source maps for easier debugging in production
    sourcemap: false,
    // Increase chunk size warning limit slightly for the app size
    chunkSizeWarningLimit: 1000,
  },
});
