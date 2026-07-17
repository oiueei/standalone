import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
import nodeConsole from 'node:console';
import './i18n-mock';

// findBy*/waitFor default to 1s, which pages with chained async fetches
// (ThingPage → WishResponsesList → responses) can exceed under CI CPU load —
// the thingWishConfirm flake. 5s only delays genuine failures, never passes.
configure({ asyncUtilTimeout: 5000 });

// Minimal localStorage mock for jsdom
const store = {};
const localStorageMock = {
  getItem: (key) => store[key] ?? null,
  setItem: (key, value) => { store[key] = String(value); },
  removeItem: (key) => { delete store[key]; },
  clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
};
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock });

// Suppress CSS.supports errors from HDS in jsdom
if (!globalThis.CSS) {
  globalThis.CSS = { supports: () => false };
}

// HDS components (Select, TextArea) require ResizeObserver
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom can't parse HDS's CSS and logs this on every stylesheet import —
// harmless, but it buries real failures in CI output. Drop only this
// message; everything else still reaches console.error. jsdom's
// VirtualConsole forwards to the *original* node:console object it was
// handed at environment setup, ahead of Vitest's own console wrapper, so
// that's the object that actually needs patching (patching globalThis.console
// alone leaves this one call site un-intercepted).
function withoutCssParseNoise(original) {
  return (...args) => {
    if (typeof args[0] === 'string' && args[0].includes('Could not parse CSS stylesheet')) {
      return;
    }
    original(...args);
  };
}
nodeConsole.error = withoutCssParseNoise(nodeConsole.error);
console.error = withoutCssParseNoise(console.error);
