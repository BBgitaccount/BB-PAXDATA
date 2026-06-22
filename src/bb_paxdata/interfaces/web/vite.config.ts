import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const apiUrl = process.env.VITE_API_URL || 'http://localhost:8000';
const wsUrl = apiUrl.replace('http://', 'ws://').replace('https://', 'wss://');

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api/ws': { target: wsUrl, ws: true, changeOrigin: true },
      '/api': { target: apiUrl, changeOrigin: true },
      '/ws': { target: wsUrl, ws: true, changeOrigin: true },
    },
  },
});
