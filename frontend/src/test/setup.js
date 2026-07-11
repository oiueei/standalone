import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';
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
