import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: process.env.VITE_API_PROXY || env.VITE_API_PROXY || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  };
});
