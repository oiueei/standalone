import { describe, test, expect, vi, afterEach } from 'vitest';
import { apiFetch } from '../services/api';

describe('apiFetch — 401 refresh', () => {
  const realFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = realFetch;
    vi.restoreAllMocks();
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

    // Three simultaneous 401s, but only ONE refresh POST.
    expect(refreshCalls).toBe(1);
    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    expect(c.status).toBe(200);
  });
});
