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
    // The jest-axe smoke tests on the heaviest form pages take ~4-6 s on a shared
    // CI runner once V8 coverage instrumentation is on (the suite runs 2× slower
    // there than locally) — the 5 s vitest default made them flake. Passing tests
    // don't wait, so the higher ceiling costs nothing.
    testTimeout: 20000,
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
      // Bumped after the 2026-07 full-suite audit (login/report/join/prefs/
      // request/tags/invites/wishes tests) lifted coverage to
      // ~78.3 / 68.8 / 66.1 / 82.2.
      thresholds: {
        statements: 76,
        branches: 66,
        functions: 63,
        lines: 80,
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
