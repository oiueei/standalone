import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/static/' : '/',
  build: {
    // vendor-hds is ~575 kB raw but only ~152 kB gzipped (under our 200 kB-gz
    // bar) — it's the irreducible hds-react library, shared and long-cached.
    // Raising the limit keeps the build green; the per-language i18n locales are
    // now code-split (see src/i18n/index.js), so the remaining win (HDS v6
    // tree-shaking) is tracked separately.
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
      // Ratchet floor: set ~2-3 points below the suite's current coverage so it
      // guards against regression without blocking. Raise it as coverage grows.
      // Bumped after the rental / a11y / palette tests (O3/O4) and the CSV-options
      // tests lifted coverage to ~57.5 / 50.8 / 44.3 / 60.7.
      thresholds: {
        statements: 55,
        branches: 48,
        functions: 42,
        lines: 58,
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
