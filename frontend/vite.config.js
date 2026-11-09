import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === 'production' ? '/static/' : '/',
  build: {
    // vendor-hds is ~623 kB raw but only ~161 kB gzipped (under our 200 kB-gz
    // bar) — it's the hds-react we actually use, shared and long-cached.
    // Raising the limit keeps the build green; the per-language i18n locales are
    // now code-split (see src/i18n/index.js).
    //
    // Tree-shaking is **not** an outstanding win here, though this comment used
    // to say it was. Measured at the 2026-08 pre-release frontend review by
    // grepping the built chunk for the marker strings of components we never
    // import — CookieConsent, Header, Footer, Search, Stepper, Pagination,
    // SideNavigation, PhoneInput, PasswordInput, Breadcrumb, Card, Tabs, Hero,
    // Logo — and none of them is in it. What is left is the ~30 components,
    // their shared internals and the 24 icons this app really renders. Switching
    // the imports to `hds-react/components/*` subpaths would buy nothing, and
    // the icons have no subpath export to switch to.
    //
    // The number is a tripwire, not a budget: it sits just above the current
    // chunk so the next HDS minor that grows it materially says so out loud.
    // Raise it deliberately, after checking the gzipped figure — that is the
    // one that governs the 4G mid-range Android target in DESIGN §7. Bumped
    // 600 → 650 on the 6.0.4 → 6.0.5 upgrade (585 → 614 kB raw).
    chunkSizeWarningLimit: 650,
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
        // `src/i18n/locales/**` is data, not logic — three JSON catalogues whose
        // parity is pinned by `i18nParity.test.js`. `src/i18n/index.js` itself is
        // measured: it stopped being pure configuration when the deployment
        // bundles and the lazy-locale map landed there, and while the whole
        // directory was excluded a real bug in it (a deployment's copy
        // suppressing its own language chunk) was invisible to both the suite
        // and the ratchet.
        'src/i18n/locales/**',
        // `src/legal/*.js` is the legal text in three languages, Markdown in a
        // template string: data like the locales. A deployment replaces these files
        // with its own, so counting them would move the ratchet with whoever edits
        // a paragraph. What reads them is `LegalPage`, which is measured.
        'src/legal/*.js',
      ],
      // Ratchet floor: set ~2-3 points below the suite's current coverage so it
      // guards against regression without blocking. Raise it as coverage grows,
      // once the slack on any metric drifts past ~3 points — a band wider than
      // that lets a regression delete a chunk of the guard and still go green.
      // Raise only on two agreeing runs: a metric that wobbles between runs is
      // not a baseline.
      //
      // Coverage is a floor detector, not a bug detector: tests that pin
      // behaviour whose lines were already executed (a serializer's field list
      // pinned as a set instead of one forbidden name, the CSRF header on the
      // silent token refresh) close real gaps and move no metric.
      //
      // Mirrored in CLAUDE.md, which quotes these numbers — they move together or
      // the doc starts lying.
      //
      // The floor is not the goal — it only catches a drop. New code still owes
      // tests that name a behaviour; a change that lands under this line means
      // the code needs covering, never that the line needs lowering.
      thresholds: {
        statements: 93,
        branches: 90,
        functions: 90,
        lines: 95,
      },
    },
  },
  resolve: {
    alias: {
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
      postcss: path.resolve(__dirname, 'src/stubs/postcss.js'),
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
      allow: [path.resolve(__dirname, '..')],
    },
  },
}));
