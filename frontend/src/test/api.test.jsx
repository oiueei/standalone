import { describe, test, expect, vi, afterEach, beforeEach } from 'vitest';
import { apiFetch, extractApiError } from '../services/api';

// apiFetch is the security-load-bearing auth core: it injects the CSRF header on
// mutating requests, funnels concurrent 401s through one refresh, retries once on
// success, and logs the user out (clears userCode + redirects to /login) when the
// session is truly gone. These tests pin all of that behaviour.

describe('apiFetch', () => {
  const realFetch = globalThis.fetch;
  let originalLocation;

  beforeEach(() => {
    // Replace window.location with a plain object so setting `.href` records the
    // redirect target instead of triggering a jsdom navigation.
    originalLocation = window.location;
    Object.defineProperty(window, 'location', { configurable: true, value: { href: '' } });
    localStorage.clear();
    localStorage.setItem('userCode', 'USER01');
    document.cookie = 'csrftoken=tok-123';
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
    Object.defineProperty(window, 'location', { configurable: true, value: originalLocation });
    vi.restoreAllMocks();
  });

  test('a mutating request gets the CSRF header, JSON content-type and credentials', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200 }));

    await apiFetch('/api/v1/things/', { method: 'POST', body: JSON.stringify({ a: 1 }) });

    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['X-CSRFToken']).toBe('tok-123');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(opts.credentials).toBe('include');
  });

  test('a GET carries no CSRF header (safe method)', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200 }));

    await apiFetch('/api/v1/collections/');

    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['X-CSRFToken']).toBeUndefined();
  });

  test('a caller-supplied X-CSRFToken is not overwritten', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200 }));

    await apiFetch('/api/v1/things/', {
      method: 'DELETE',
      headers: { 'X-CSRFToken': 'explicit' },
    });

    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers['X-CSRFToken']).toBe('explicit');
  });

  test('concurrent 401s trigger a single shared refresh (single-flight)', async () => {
    let refreshCalls = 0;
    let refreshed = false;

    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('/auth/refresh/')) {
        refreshCalls += 1;
        refreshed = true;
        return Promise.resolve({ ok: true, status: 200 });
      }
      // Protected endpoints: 401 until the (single) refresh succeeds, then 200.
      return Promise.resolve({ ok: refreshed, status: refreshed ? 200 : 401 });
    });

    const [a, b, c] = await Promise.all([
      apiFetch('/api/v1/collections/'),
      apiFetch('/api/v1/invited-collections/'),
      apiFetch('/api/v1/my-bookings/'),
    ]);

    expect(refreshCalls).toBe(1);
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(c.status).toBe(200);
  });

  test('401 → refresh ok → retry ok returns the retried response and keeps the session', async () => {
    let protectedCalls = 0;
    globalThis.fetch = vi.fn((url) => {
      if (String(url).includes('/auth/refresh/')) return Promise.resolve({ ok: true, status: 200 });
      protectedCalls += 1;
      return Promise.resolve({ ok: protectedCalls > 1, status: protectedCalls > 1 ? 200 : 401 });
    });

    const res = await apiFetch('/api/v1/collections/');

    expect(res.status).toBe(200);
    expect(localStorage.getItem('userCode')).toBe('USER01');
    expect(window.location.href).toBe('');
  });

  test('401 → refresh ok → retry still 401 logs out and redirects', async () => {
    globalThis.fetch = vi.fn((url) =>
      String(url).includes('/auth/refresh/')
        ? Promise.resolve({ ok: true, status: 200 })
        : Promise.resolve({ ok: false, status: 401 })
    );

    await expect(apiFetch('/api/v1/collections/')).rejects.toThrow('Unauthorised');
    expect(localStorage.getItem('userCode')).toBeNull();
    expect(window.location.href).toBe('/login');
  });

  test('401 → refresh fails logs out and redirects', async () => {
    globalThis.fetch = vi.fn((url) =>
      String(url).includes('/auth/refresh/')
        ? Promise.resolve({ ok: false, status: 401 })
        : Promise.resolve({ ok: false, status: 401 })
    );

    await expect(
      apiFetch('/api/v1/things/', { method: 'POST', body: '{}' })
    ).rejects.toThrow('Unauthorised');
    expect(localStorage.getItem('userCode')).toBeNull();
    expect(window.location.href).toBe('/login');
  });
});

describe('extractApiError — message precedence', () => {
  const body = (data) => ({ json: () => Promise.resolve(data) });

  test('prefers DRF `detail`', async () => {
    expect(await extractApiError(body({ detail: 'D', error: 'E' }))).toBe('D');
  });

  test('falls back to `error`', async () => {
    expect(await extractApiError(body({ error: 'E' }))).toBe('E');
  });

  test('then `non_field_errors`', async () => {
    expect(await extractApiError(body({ non_field_errors: ['NFE'] }))).toBe('NFE');
  });

  test('then the first field error', async () => {
    expect(await extractApiError(body({ email: ['bad email'] }))).toBe('bad email');
  });

  test('returns null on an empty body or unparseable JSON', async () => {
    expect(await extractApiError(body({}))).toBeNull();
    expect(await extractApiError({ json: () => Promise.reject(new Error('x')) })).toBeNull();
  });
});
