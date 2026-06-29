import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/static/' : '/',
  build: {
    // vendor-hds is ~575 kB raw but only ~152 kB gzipped (under our 200 kB-gz
    // bar) — it's the irreducible hds-react library, shared and long-cached.
    // Raising the limit keeps the build green; further wins (lazy per-language
    // i18n locales, the HDS v6 tree-shaking) are tracked separately.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Split the rarely-changing vendor libraries from app code so a page
        // edit doesn't bust the (large, cacheable) React/HDS chunks. Pages are
        // already route-split via React.lazy in App.jsx.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (/[\\/]react(-dom)?[\\/]|[\\/]scheduler[\\/]/.test(id)) return 'vendor-react';
          if (id.includes('hds-react') || id.includes('hds-core')) return 'vendor-hds';
          return undefined;
        },
      },
    },
  },
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
      // against regression without blocking. Raise it as coverage grows. Bumped
      // after the characterisation tests lifted coverage to ~51/44/38/54.
      thresholds: {
        statements: 48,
        branches: 40,
        functions: 35,
        lines: 50,
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
