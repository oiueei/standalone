import '@testing-library/jest-dom';
import './i18n-mock';

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
