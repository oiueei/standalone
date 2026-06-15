import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/static/' : '/',
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'html'],
      all: true,
      include: ['src/**/*.{js,jsx}'],
      exclude: [
        'src/main.jsx',
        'src/test/**',
        'src/**/*.test.{js,jsx}',
        'src/stubs/**',
        'src/i18n/**',
      ],
      // Ratchet floor: set just below the suite's current coverage so it guards
      // against regression without blocking. Raise it as coverage grows.
      thresholds: {
        statements: 40,
        branches: 28,
        functions: 30,
        lines: 42,
      },
    },
  },
  resolve: {
    alias: {
      'react': path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      'postcss': path.resolve(__dirname, 'src/stubs/postcss.js'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
    fs: {
      allow: [
        path.resolve(__dirname, '..'),
      ],
    },
  },
}))
